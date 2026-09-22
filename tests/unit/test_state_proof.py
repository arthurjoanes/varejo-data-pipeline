"""Contratos de host: não iniciam Docker, Spark, JVM ou browser."""

import csv
import importlib.util
import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPTS = Path(__file__).parents[2] / "scripts"
IMAGE = "sha256:" + "a" * 64


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + ".py"))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def contracts(monkeypatch):
    module = load_script("proof_contracts")
    monkeypatch.setitem(sys.modules, "proof_contracts", module)
    return module


@pytest.fixture
def runner_module(contracts):
    return load_script("prove_state")


def archive_fixture(tmp_path, contracts):
    source = tmp_path / "source"
    (source / "state/tables/history/_delta_log").mkdir(parents=True)
    (source / "state/tables/history/_delta_log/000.json").write_bytes(b'{"version":0}\n')
    (source / "state/bytes").write_bytes(bytes(range(256)))
    archive = tmp_path / "state.tar"
    manifest = contracts.make_archive(source, archive, internal_root="/data/proof")
    return source, archive, manifest


def test_archive_roundtrip_is_byte_identical_without_changing_source(tmp_path, contracts):
    source, archive, manifest = archive_fixture(tmp_path, contracts)
    target = tmp_path / "target"
    contracts.restore_archive(archive, target, manifest, internal_root="/data/proof")
    assert contracts.inventory(source) == contracts.inventory(target) == manifest["files"]
    assert manifest["archive_sha256"] == contracts.digest(archive)


@pytest.mark.parametrize("kind", ["corrupted", "occupied", "internal_root", "inside_source"])
def test_archive_refusal_preserves_existing_bytes(tmp_path, contracts, kind):
    source, archive, manifest = archive_fixture(tmp_path, contracts)
    before = contracts.inventory(source)
    target = tmp_path / "target"
    if kind == "corrupted":
        with archive.open("r+b") as handle:
            handle.write(b"corrupted")
    elif kind == "occupied":
        target.mkdir()
        (target / "keep").write_bytes(b"existing")
    elif kind == "internal_root":
        manifest["internal_root"] = "/different"
    with pytest.raises(ValueError):
        if kind == "inside_source":
            contracts.make_archive(source, source / "inside.tar", internal_root="/data/proof")
        else:
            contracts.restore_archive(archive, target, manifest, internal_root="/data/proof")
    assert contracts.inventory(source) == before
    if kind == "occupied":
        assert contracts.inventory(target) == {
            "keep": {"bytes": 8, "sha256": contracts.digest(target / "keep")}
        }
    else:
        assert not target.exists()


@pytest.mark.parametrize("name", ["../escape", "/absolute", "C:/drive", "a\\b", "a/./b"])
def test_archive_paths_never_escape(tmp_path, contracts, name):
    archive = tmp_path / "unsafe.tar"
    with tarfile.open(archive, "w") as output:
        info = tarfile.TarInfo(name)
        info.size = 1
        output.addfile(info, io.BytesIO(b"x"))
    with pytest.raises(ValueError):
        contracts.inspect_archive(archive)


def test_archive_rejects_duplicate_and_link_entries(tmp_path, contracts):
    for kind in ("duplicate", "link"):
        archive = tmp_path / (kind + ".tar")
        with tarfile.open(archive, "w") as output:
            info = tarfile.TarInfo("first")
            output.addfile(info, io.BytesIO(b""))
            if kind == "link":
                info = tarfile.TarInfo("linked")
                info.type = tarfile.SYMTYPE
                info.linkname = "first"
            output.addfile(info)
        with pytest.raises(ValueError):
            contracts.inspect_archive(archive)


def test_inventory_rejects_reparse_point_before_reading(contracts, tmp_path, monkeypatch):
    root = tmp_path / "root"
    root.mkdir()
    (root / "external").mkdir()
    original = Path.lstat
    original_walk = contracts.os.walk
    visited = []

    def lstat(path):
        if path == root / "external":
            info = original(path)
            return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=1024)
        return original(path)

    def walk(*args, **kwargs):
        for item in original_walk(*args, **kwargs):
            visited.append(item[0])
            yield item

    monkeypatch.setattr(contracts.stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024, raising=False)
    monkeypatch.setattr(Path, "lstat", lstat)
    monkeypatch.setattr(contracts.os, "walk", walk)
    with pytest.raises(ValueError, match="junctions"):
        contracts.inventory(root)
    assert visited == [str(root)]


def test_inventory_limits_are_enforced_during_enumeration(tmp_path, contracts, monkeypatch):
    root = tmp_path / "root"
    root.mkdir()
    (root / "a").write_bytes(b"1234")
    (root / "b").mkdir()
    monkeypatch.setattr(contracts, "MAX_BYTES", 3)
    monkeypatch.setattr(
        contracts, "digest", lambda *args: pytest.fail("Não ler conteúdo acima do limite")
    )
    with pytest.raises(ValueError, match="limite"):
        contracts.inventory(root)
    monkeypatch.setattr(contracts, "MAX_FILES", 0)
    monkeypatch.setattr(contracts, "MAX_BYTES", 100)
    with pytest.raises(ValueError, match="entradas"):
        contracts.inventory(root)


def test_normalized_member_also_refuses_internal_ancestor_link(tmp_path, contracts, monkeypatch):
    root = tmp_path / "state"
    linked = root / "linked"
    linked.mkdir(parents=True)
    (linked / "file").write_bytes(b"internal")
    original = Path.lstat

    def lstat(path):
        if path == linked:
            return SimpleNamespace(st_mode=original(path).st_mode, st_file_attributes=1024)
        if path == linked / "file":
            pytest.fail("Ancestral deve ser recusado antes do acesso ao descendente")
        return original(path)

    monkeypatch.setattr(contracts.stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024, raising=False)
    monkeypatch.setattr(Path, "lstat", lstat)
    with pytest.raises(ValueError, match="junctions"):
        contracts.normalized_member(root, "linked/file")


def publication_fixture(tmp_path, contracts):
    root = tmp_path / "state"
    for path in (
        "tables/history",
        "tables/silver",
        "tables/gold_store_day",
        "tables/gold_product_day",
        "runs/r1/bronze",
        "runs/r2/bronze",
    ):
        (root / path).mkdir(parents=True)
        (root / path / "old-version-file").write_bytes(b"retained")
    publications = []
    for index in (1, 2):
        value = {
            "publication_id": f"p{index}",
            "tables": {
                name: {"path": str(root / "tables" / name), "version": index - 1}
                for name in ("history", "silver", "gold_store_day", "gold_product_day")
            },
            "accepted_batches": [f"b{item}" for item in range(1, index + 1)],
            "sources": [
                {
                    "batch_id": f"b{item}",
                    "bronze_path": str(root / f"runs/r{item}/bronze"),
                    "bronze_version": 0,
                }
                for item in range(1, index + 1)
            ],
        }
        value["tables"]["bronze"] = {"path": str(root / f"runs/r{index}/bronze"), "version": 0}
        publications.append(value)
        contracts.write_json(root / "publications" / f"p{index}.json", value)
    contracts.write_json(root / "publication.json", publications[-1])
    return root, publications


def test_retention_preserves_previous_current_bronze_and_individual_old_files(tmp_path, contracts):
    root, _ = publication_fixture(tmp_path, contracts)
    contract = contracts.retention_contract(root)
    assert [value["publication_id"] for value in contract["publications"]] == ["p1", "p2"]
    assert {"runs/r1/bronze", "runs/r2/bronze"}.issubset(contract["protected_paths"])
    for proposal in (
        "tables",
        "tables/history/old-version-file",
        "runs/r1/bronze",
        "publications/p1.json",
        ".",
    ):
        with pytest.raises(ValueError, match="referenciada"):
            contracts.reject_referenced_removal(root, contract, [proposal])


def test_retention_refuses_outside_reference_before_reading_its_content(tmp_path, contracts):
    root, publications = publication_fixture(tmp_path, contracts)
    outside = tmp_path / "state-neighbor"
    outside.mkdir()
    publications[0]["sources"][0]["bronze_path"] = str(outside)
    (root / "publications/p1.json").write_text(json.dumps(publications[0]), encoding="utf-8")
    with pytest.raises(ValueError, match="fora do estado"):
        contracts.retention_contract(root)
    with pytest.raises(ValueError, match="fora do estado"):
        contracts.normalized_member(root, "../state-neighbor")


def test_retention_rejects_missing_previous_reference_or_pointer_mismatch(tmp_path, contracts):
    root, publications = publication_fixture(tmp_path, contracts)
    publications[-1]["tables"]["history"]["version"] = 9
    (root / "publication.json").write_text(json.dumps(publications[-1]), encoding="utf-8")
    with pytest.raises(ValueError, match="Ponteiro"):
        contracts.retention_contract(root)


def test_oracle_uses_exact_cents_and_refuses_duplicate_keys(tmp_path, contracts):
    row = {
        "source_system": "source",
        "store_id": "S01",
        "sale_id": "A1",
        "line_id": "1",
        "revision": "1",
        "operation": "UPSERT",
        "sold_at": "2026-01-02T02:00:00Z",
        "quantity": "2",
        "unit_price_brl": "10.00",
        "line_discount_brl": "1.00",
    }
    path = tmp_path / "S01.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row), lineterminator="\n")
        writer.writeheader()
        writer.writerows(
            [
                row,
                {
                    **row,
                    "line_id": "2",
                    "quantity": "1",
                    "unit_price_brl": "5.00",
                    "line_discount_brl": "0.00",
                },
            ]
        )
    oracle = contracts.csv_oracle([tmp_path])
    assert oracle == {
        "received_rows": 2,
        "net_revenue_cents": 2400,
        "rows": [
            {
                "business_date": "2026-01-01",
                "store_id": "S01",
                "net_revenue_cents": 2400,
                "units": 3,
                "item_lines": 2,
                "sales_count": 1,
            }
        ],
    }
    with pytest.raises(ValueError, match="disjuntas"):
        contracts.csv_oracle([tmp_path, tmp_path])


def test_distribution_retains_censored_samples_without_inventing_p95(contracts):
    result = contracts.distribution(
        [
            {"status": "passed", "pipeline_seconds": 7},
            {"status": "censored_timeout"},
            {"status": "not_executed"},
        ]
    )
    assert result["planned"] == 3
    assert result["completed"] == 1
    assert result["censored_or_failed"] == 2
    assert result["median_completed_only_seconds"] == 7
    assert result["p95"] is None
    with pytest.raises(ValueError):
        contracts.distribution([{"status": "passed", "pipeline_seconds": float("nan")}])


def test_runner_requires_immutable_image_own_volume_and_relative_artifact(tmp_path, runner_module):
    with pytest.raises(ValueError):
        runner_module.Runner("latest", tmp_path)
    runner = runner_module.Runner(IMAGE, tmp_path)
    with pytest.raises(ValueError, match="criado"):
        runner.phase("shared-existing", "observe", "out.json")
    runner.volumes.append("owned")
    with pytest.raises(ValueError, match="relativo"):
        runner.phase("owned", "observe", "../out.json")
    command = runner.runtime_command("owned-container", "owned", "observe", "out.json", [])
    assert command[0] == "create" and "build" not in command
    assert command[command.index("--network") + 1] == "none"
    assert command[command.index("--memory") + 1] == str(3 * 1024**3)
    assert command[command.index("--cpus") + 1] == "2"
    assert any(value.endswith("target=/app,readonly") for value in command)


def test_command_budget_caps_child_and_reserves_cleanup(tmp_path, runner_module, monkeypatch):
    runner = runner_module.Runner(IMAGE, tmp_path)
    runner.active_deadline = 105
    runner.cleanup_spent_seconds = 58
    monkeypatch.setattr(runner_module.time, "monotonic", lambda: 100)
    observed = []

    def execute(command, **kwargs):
        observed.append((command, kwargs["timeout"]))
        return SimpleNamespace(stdout="", returncode=0)

    monkeypatch.setattr(runner_module.subprocess, "run", execute)
    runner.docker(["inspect", "own"], timeout=30)
    runner.docker(["rm", "--force", "own"], timeout=30, cleanup=True)
    assert [item[1] for item in observed] == [5, 2]
    runner.active_deadline = 99
    with pytest.raises(subprocess.TimeoutExpired):
        runner.docker(["inspect", "own"])
    assert len(observed) == 2


def test_phase_timeout_removes_only_created_container_and_keeps_observation(
    tmp_path, runner_module, monkeypatch
):
    runner = runner_module.Runner(IMAGE, tmp_path)
    runner.volumes.append("own-volume")
    calls = []

    def docker(arguments, **kwargs):
        calls.append(arguments)
        return SimpleNamespace(stdout="", returncode=0)

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("mock attach", 1)

    monkeypatch.setattr(runner, "docker", docker)
    monkeypatch.setattr(runner, "verify_container", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner_module.subprocess, "run", timeout)
    with pytest.raises(runner_module.PhaseFailure) as failure:
        runner.phase("own-volume", "measure", "sample.json", timeout=1)
    assert failure.value.record["status"] == "censored_timeout"
    assert failure.value.record["container_removed"] is True
    assert calls[-1] == ["rm", "--force", runner.run_id + "-0"]
    assert not any("volume" == item for command in calls for item in command)


@pytest.mark.parametrize("bad_field", [None, "Memory", "ReadonlyRootfs", "NanoCpus", "NetworkMode"])
def test_container_is_checked_before_workload(tmp_path, runner_module, monkeypatch, bad_field):
    runner = runner_module.Runner(IMAGE, tmp_path)
    details = {
        "Image": IMAGE,
        "Config": {
            "Labels": {runner_module.LABEL: runner.run_id},
            "Env": [key + "=" + value for key, value in runner_module.TEMP_ENV.items()],
        },
        "HostConfig": {
            "NetworkMode": "none",
            "ReadonlyRootfs": True,
            "Memory": 3 * 1024**3,
            "NanoCpus": 2_000_000_000,
            "PidsLimit": runner_module.MEASUREMENT_PLAN["pids_limit"],
            "Privileged": False,
            "CapDrop": ["ALL"],
            "CapAdd": ["DAC_OVERRIDE"],
            "SecurityOpt": ["no-new-privileges:true"],
        },
        "Mounts": [
            {"Destination": "/app", "Type": "bind", "RW": False},
            {"Destination": "/evidence", "Type": "bind", "RW": True},
            {"Destination": "/data", "Type": "volume", "Name": "own"},
        ],
    }
    if bad_field is not None:
        details["HostConfig"][bad_field] = 0
    monkeypatch.setattr(
        runner, "docker", lambda *args, **kwargs: SimpleNamespace(stdout=json.dumps([details]))
    )
    if bad_field is None:
        assert runner.verify_container("created", "own", timeout=1) == details
    else:
        with pytest.raises(ValueError, match="Runtime diverge"):
            runner.verify_container("created", "own", timeout=1)


def test_snapshot_ignores_only_owned_resources_and_unstable_age(
    tmp_path, runner_module, monkeypatch
):
    runner = runner_module.Runner(IMAGE, tmp_path)
    runner.containers.append("own-container")
    runner.volumes.append("own-volume")
    rows = [
        {
            "ID": "existing-id",
            "Names": "existing",
            "Image": "original",
            "State": "running",
            "Status": "Up 1 minute",
        },
        {"ID": "own-id", "Names": "own-container", "Image": IMAGE, "State": "exited"},
    ]
    volumes = [{"Name": "existing-volume"}, {"Name": "own-volume"}]
    monkeypatch.setattr(
        runner,
        "docker",
        lambda args, **kwargs: SimpleNamespace(
            stdout="\n".join(json.dumps(row) for row in (rows if args[0] == "ps" else volumes))
        ),
    )
    assert runner.snapshot() == {
        "containers": [
            {"ID": "existing-id", "Names": "existing", "Image": "original", "State": "running"}
        ],
        "volumes": ["existing-volume"],
    }


@pytest.mark.parametrize(
    "failure_status,expected", [("censored_timeout", "inconclusive"), ("failed", "failed")]
)
def test_measurement_preserves_all_samples_and_distinguishes_functional_failure(
    tmp_path, runner_module, monkeypatch, failure_status, expected
):
    runner = runner_module.Runner(IMAGE, tmp_path)
    monkeypatch.setattr(runner, "volume", lambda role: role)

    def phase(volume, kind, output, **kwargs):
        if kind == "measure-seed":
            return {"generation_seconds": 1, "baseline_pipeline_seconds": 2}
        if kind == "measure":
            raise runner_module.PhaseFailure({"status": failure_status, "phase": "measure"})
        return {}

    monkeypatch.setattr(runner, "phase", phase)
    result = runner_module.prove_measurement(runner)
    assert result["status"] == expected
    assert len(result["samples"]) == 6
    assert all(item["status"] == failure_status for item in result["samples"])
    assert all(item["completed"] == 0 for item in result["distribution_by_history_rows"].values())


def test_overall_deadline_keeps_unexecuted_samples(tmp_path, runner_module, monkeypatch):
    runner = runner_module.Runner(IMAGE, tmp_path)
    clock = iter([0, 1801])
    monkeypatch.setattr(runner_module.time, "monotonic", lambda: next(clock, 1801))
    monkeypatch.setattr(runner, "volume", lambda *args: pytest.fail("Não criar volume após prazo"))
    result = runner_module.prove_measurement(runner)
    assert result["status"] == "inconclusive"
    assert len(result["samples"]) == 6
    assert all(
        item["status"] == "not_executed" and item["reason"] == "overall_deadline"
        for item in result["samples"]
    )


def test_cleanup_failure_stops_next_samples_but_preserves_them(
    tmp_path, runner_module, monkeypatch
):
    runner = runner_module.Runner(IMAGE, tmp_path)
    monkeypatch.setattr(runner, "volume", lambda role: role)

    def failed(*args, **kwargs):
        raise runner_module.PhaseFailure({"status": "failed_cleanup", "phase": "measure-seed"})

    monkeypatch.setattr(runner, "phase", failed)
    with pytest.raises(runner_module.PhaseFailure):
        runner_module.prove_measurement(runner)
    assert len(runner.measurement["samples"]) == 6
    assert all(item["status"] == "not_executed" for item in runner.measurement["samples"])


def test_no_execute_flag_cannot_reach_docker(tmp_path, runner_module, monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["prove_state.py", "restore", "--image", IMAGE, "--output", str(tmp_path / "private")],
    )
    monkeypatch.setattr(
        runner_module.subprocess,
        "run",
        lambda *args, **kwargs: pytest.fail("Runtime não autorizado"),
    )
    with pytest.raises(SystemExit) as error:
        runner_module.main()
    assert error.value.code == 2
    assert not (tmp_path / "private").exists()


def test_cleanup_uses_valid_scoped_label_filter(tmp_path, runner_module, monkeypatch):
    runner = runner_module.Runner(IMAGE, tmp_path)
    calls = []

    def docker(arguments, **kwargs):
        calls.append(arguments)
        return SimpleNamespace(stdout="", returncode=0)

    monkeypatch.setattr(runner, "docker", docker)
    assert runner.cleanup()["containers_removed"]
    assert len(calls) == 2
    assert all(
        command[-1] == "label=" + runner_module.LABEL + "=" + runner.run_id for command in calls
    )

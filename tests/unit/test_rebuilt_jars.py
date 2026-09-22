import hashlib
import json
import runpy
import warnings
import zipfile
from pathlib import Path

import pytest

installer = runpy.run_path(str(Path(__file__).parents[2] / "scripts/install_rebuilt_jars.py"))
load_manifest = installer["load_manifest"]
install = installer["install_rebuilt_jars"]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def prepare(tmp_path, *, components=1, entries=None, provenance=b'{"patch":"local-v1"}'):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    rebuilt = tmp_path / "rebuilt"
    records = []
    for index in range(components):
        component = f"component-{index}"
        original = runtime / f"upstream-{index}.jar"
        original.write_bytes(b"original component")
        target = f"component-{index}-local.jar"
        candidate = rebuilt / component / target
        candidate.parent.mkdir(parents=True)
        with warnings.catch_warnings(), zipfile.ZipFile(candidate, "w") as archive:
            warnings.simplefilter("ignore", UserWarning)
            for name, content in entries or [
                ("example/Component.class", b"class bytes"),
                ("META-INF/maven/example/component/pom.properties", b"version=1.0\n"),
                ("META-INF/LICENSE.txt", b"original license"),
            ]:
                archive.writestr(name, content)
            archive.writestr("META-INF/local-build.json", provenance)
        records.append(
            {
                "component": component,
                "source": original.name,
                "source_sha256": digest(original.read_bytes()),
                "target": target,
                "sha256": digest(candidate.read_bytes()),
                "provenance_path": "META-INF/local-build.json",
                "provenance_sha256": digest(provenance),
            }
        )
    manifest = tmp_path / "lock.json"
    manifest.write_text(json.dumps({"rebuilt_components": records}), encoding="utf-8")
    return manifest, runtime, rebuilt, tmp_path / "evidence", records


def test_install_preserves_complete_jar_and_publishes_pinned_provenance(tmp_path):
    manifest, runtime, rebuilt, evidence, records = prepare(tmp_path, components=2)
    install(load_manifest(manifest), runtime, rebuilt, evidence)
    for record in records:
        target = runtime / record["target"]
        assert digest(target.read_bytes()) == record["sha256"]
        assert not (runtime / record["source"]).exists()
        assert (
            digest((evidence / f"{record['component']}.json").read_bytes())
            == record["provenance_sha256"]
        )
        with zipfile.ZipFile(target) as archive:
            assert (
                archive.read("META-INF/maven/example/component/pom.properties") == b"version=1.0\n"
            )
            assert archive.read("META-INF/LICENSE.txt") == b"original license"


@pytest.mark.parametrize("tamper", ["upstream", "rebuilt", "provenance", "existing_target"])
def test_entire_preflight_finishes_before_any_runtime_mutation(tmp_path, tamper):
    manifest, runtime, rebuilt, evidence, records = prepare(tmp_path, components=2)
    last = records[-1]
    if tamper == "upstream":
        (runtime / last["source"]).write_bytes(b"unexpected upstream update")
    elif tamper == "rebuilt":
        (rebuilt / last["component"] / last["target"]).write_bytes(b"tampered build")
    elif tamper == "provenance":
        last["provenance_sha256"] = "0" * 64
        manifest.write_text(json.dumps({"rebuilt_components": records}), encoding="utf-8")
    else:
        (runtime / last["target"]).write_bytes(b"conflicting runtime component")
    before = {item.name: item.read_bytes() for item in runtime.iterdir()}
    with pytest.raises(ValueError):
        install(load_manifest(manifest), runtime, rebuilt, evidence)
    assert {item.name: item.read_bytes() for item in runtime.iterdir()} == before
    assert not evidence.exists()


@pytest.mark.parametrize(
    ("entries", "message"),
    [
        ([("example/Component.class", b"class")], "retain Maven"),
        ([("META-INF/maven/example/a/pom.properties", b"version=1.0")], "no executable"),
        (
            [("example/Component.class", b"first"), ("example/Component.class", b"second")],
            "Duplicate ZIP",
        ),
    ],
)
def test_rejects_incomplete_or_ambiguous_archive_even_with_matching_hash(
    tmp_path, entries, message
):
    manifest, runtime, rebuilt, evidence, _ = prepare(tmp_path, entries=entries)
    with pytest.raises(ValueError, match=message):
        install(load_manifest(manifest), runtime, rebuilt, evidence)
    assert (runtime / "upstream-0.jar").exists()
    assert not evidence.exists()


@pytest.mark.parametrize("provenance", [b"[]", b" " * (1024 * 1024 + 1)])
def test_rejects_unusable_provenance_before_copy(tmp_path, provenance):
    manifest, runtime, rebuilt, evidence, _ = prepare(tmp_path, provenance=provenance)
    with pytest.raises(ValueError):
        install(load_manifest(manifest), runtime, rebuilt, evidence)
    assert (runtime / "upstream-0.jar").exists()
    assert not evidence.exists()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("component", "../outside"),
        ("source", "../upstream.jar"),
        ("target", "/outside.jar"),
        ("target", "upstream-0.jar"),
        ("source_sha256", "not-a-hash"),
        ("provenance_path", "META-INF/../outside.json"),
    ],
)
def test_manifest_cannot_redirect_component_paths(tmp_path, field, value):
    manifest, _, _, _, records = prepare(tmp_path)
    records[0][field] = value
    manifest.write_text(json.dumps({"rebuilt_components": records}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_manifest(manifest)


def test_manifest_cannot_replace_another_declared_source(tmp_path):
    manifest, _, _, _, records = prepare(tmp_path, components=2)
    records[0]["target"] = records[1]["source"]
    manifest.write_text(json.dumps({"rebuilt_components": records}), encoding="utf-8")
    with pytest.raises(ValueError, match="shadow"):
        load_manifest(manifest)

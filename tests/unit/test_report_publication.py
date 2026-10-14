import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from retail_pipeline import reporting


def test_attempt_order_survives_restore_and_ignores_file_times(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "proof_contracts", Path(__file__).parents[2] / "scripts/proof_contracts.py"
    )
    contracts = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(contracts)
    source = tmp_path / "source"
    for run_id, started, state in [
        ("z-old", "2026-10-12T11:00:00+00:00", "BLOCKED"),
        ("a-new", "2026-10-13T08:00:00-03:00", "PUBLISHED"),
        ("b-tie", "2026-10-13T11:00:00+00:00", "PUBLISHED"),
    ]:
        path = source / "runs" / run_id / "attempt.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(dict(run_id=run_id, started_at=started, state=state)))
        os.utime(path, (1, 1))
    before = reporting._read_attempts(source)
    assert before[0]["run_id"] == "b-tie"
    assert before[1]["run_id"] == "z-old"
    archive = tmp_path / "copy.tar"
    manifest = contracts.make_archive(source, archive, internal_root="/data/test")
    restored = tmp_path / "restored"
    contracts.restore_archive(archive, restored, manifest, internal_root="/data/test")
    assert reporting._read_attempts(restored) == before


@pytest.mark.parametrize("started", [None, "invalid", "2026-10-13T11:00:00"])
def test_attempts_reject_missing_invalid_or_naive_chronology(tmp_path, started):
    path = tmp_path / "runs/legacy/attempt.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(dict(run_id="legacy", started_at=started, state="BLOCKED")))
    with pytest.raises(ValueError, match="Cronologia"):
        reporting._read_attempts(tmp_path)


def test_html_preserves_previous_document_on_replace_failure(tmp_path, monkeypatch):
    target = tmp_path / "report.html"
    target.write_bytes(b"previous complete document")

    def failed_replace(*args):
        raise OSError("simulated disk failure")

    monkeypatch.setattr(reporting.os, "replace", failed_replace)
    with pytest.raises(OSError, match="simulated"):
        reporting._publish_html(target, "new complete document")
    assert target.read_bytes() == b"previous complete document"
    assert list(tmp_path.iterdir()) == [target]


def test_html_keeps_existing_reader_snapshot_and_mode(tmp_path):
    target = tmp_path / "report.html"
    reporting._publish_html(target, "old document")
    if os.name != "nt":
        assert stat.S_IMODE(target.stat().st_mode) == 0o644
        target.chmod(0o640)
        with target.open() as reader:
            reporting._publish_html(target, "new document")
            assert reader.read() == "old document"
        assert stat.S_IMODE(target.stat().st_mode) == 0o640
    else:
        reporting._publish_html(target, "new document")
    assert target.read_text() == "new document"


@pytest.fixture
def report_permission_controls():
    if os.environ.get("RETAIL_REPORT_PERMISSION_TESTS") != "1":
        pytest.skip("run python scripts/check_report_permissions.py in its isolated test container")
    if os.name != "posix" or os.geteuid() != 0:
        pytest.fail("permission checks require the isolated Linux root test container")


@pytest.mark.report_permissions
def test_new_report_is_readable_by_report_server_uid(report_permission_controls):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        root.chmod(0o755)
        target = root / "report.html"
        reporting._publish_html(target, "complete report")
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import os,sys; os.setgroups([]); os.setgid(65534); os.setuid(65534); print(open(sys.argv[1]).read())",
                str(target),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        assert result.stdout.strip() == "complete report"


@pytest.mark.report_permissions
def test_existing_report_preserves_host_owner_and_group(tmp_path, report_permission_controls):
    target = tmp_path / "report.html"
    target.write_text("old document")
    os.chown(target, 1000, 1001)
    target.chmod(0o640)
    reporting._publish_html(target, "new document")
    result = target.stat()
    assert (result.st_uid, result.st_gid, stat.S_IMODE(result.st_mode)) == (1000, 1001, 0o640)
    assert target.read_text() == "new document"


@pytest.mark.report_permissions
def test_owner_preservation_failure_keeps_previous_report(
    tmp_path, monkeypatch, report_permission_controls
):
    target = tmp_path / "report.html"
    target.write_text("old document")
    os.chown(target, 1000, 1001)

    def failed_chown(*args):
        raise PermissionError("cannot preserve ownership")

    monkeypatch.setattr(reporting.os, "fchown", failed_chown)
    with pytest.raises(PermissionError, match="ownership"):
        reporting._publish_html(target, "new document")
    assert target.read_text() == "old document"
    assert (target.stat().st_uid, target.stat().st_gid) == (1000, 1001)
    assert list(tmp_path.iterdir()) == [target]

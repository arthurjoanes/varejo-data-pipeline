import json
from pathlib import Path

import pytest

from retail_pipeline.lineage import export_lineage
from retail_pipeline.publication import WriterBusy, atomic_json, writer_lock


@pytest.mark.integration
def test_export_refuses_active_writer_without_terminating_its_attempt(tmp_path: Path) -> None:
    root = tmp_path / "state"
    attempt = root / "runs" / ("a" * 32) / "attempt.json"
    atomic_json(attempt, {"run_id": "a" * 32, "state": "RUNNING", "issues": []})
    original = attempt.read_bytes()
    with writer_lock(root), pytest.raises(WriterBusy):
        export_lineage(root)
    assert attempt.read_bytes() == original
    assert json.loads(attempt.read_text())["state"] == "RUNNING"
    assert not (root / "lineage").exists()

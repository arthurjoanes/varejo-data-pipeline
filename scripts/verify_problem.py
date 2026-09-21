"""Roda os testes em temporários novos e registra o hash das fontes."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path


def fingerprint(root: Path) -> dict[str, str]:
    paths = [
        path
        for directory in ("src", "tests", "scripts", "data/operator", "data/samples")
        for path in (root / directory).rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    ]
    paths.extend(root / name for name in ("pyproject.toml", "requirements.lock", "compose.yaml"))
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(paths)
    }


def git_commit(root: Path) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    commit = completed.stdout.strip()
    return commit if completed.returncode == 0 and commit else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("/app/artifacts/verification"))
    parser.add_argument("--thesis-only", action="store_true")
    arguments = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = arguments.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    before = fingerprint(root)
    environment = dict(os.environ, RETAIL_THESIS_EVIDENCE_DIR=str(output))
    # Pytest escolhe tmp_path novo; nunca usa o estado nem os relatórios da demo.
    command = [
        sys.executable,
        "-m",
        "pytest",
        "tests/integration/test_business_thesis.py" if arguments.thesis_only else "tests",
        "-q",
        "--durations=10",
        f"--junitxml={output / 'tests.xml'}",
    ]
    started_at = datetime.now(UTC).isoformat()
    started = time.perf_counter()
    with (output / "pytest.log").open("w", encoding="utf-8") as log:
        process = subprocess.run(
            command, cwd=root, env=environment, stdout=log, stderr=subprocess.STDOUT, check=False
        )
    unchanged = before == fingerprint(root)
    suites = ET.parse(output / "tests.xml").getroot() if (output / "tests.xml").exists() else None
    suite = suites.find("testsuite") if suites is not None else None
    result = {
        "status": "passed" if process.returncode == 0 and unchanged else "failed",
        "started_at": started_at,
        "duration_seconds": round(time.perf_counter() - started, 3),
        "command": command,
        "exit_code": process.returncode,
        "source_unchanged": unchanged,
        "source_sha256": before,
        "runtime": {
            "python": platform.python_version(),
            **{
                name: importlib.metadata.version(name)
                for name in ("pyspark", "delta-spark", "pytest")
            },
        },
        "pytest": dict(suite.attrib) if suite is not None else None,
        "scope": "Spark e Delta reais locais; temporários isolados; nenhuma API paga ou throughput de produção.",
    }
    commit = git_commit(root)
    if commit:
        result["git_commit"] = commit
    (output / "verification.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print((output / "pytest.log").read_text(encoding="utf-8"))
    print(json.dumps({"status": result["status"], "output": str(output)}, ensure_ascii=False))
    return process.returncode if process.returncode else (0 if unchanged else 1)


if __name__ == "__main__":
    raise SystemExit(main())

import os
import subprocess
import sys
from pathlib import Path


def test_business_timezone_is_available_without_system_database() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from datetime import datetime; "
            "from retail_pipeline.contracts import BUSINESS_ZONE; "
            "print(datetime(2026, 1, 1, tzinfo=BUSINESS_ZONE).utcoffset().total_seconds())",
        ],
        env={
            **os.environ,
            "PYTHONPATH": str(Path(__file__).resolve().parents[2] / "src"),
            "PYTHONTZPATH": "",
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "-10800.0"

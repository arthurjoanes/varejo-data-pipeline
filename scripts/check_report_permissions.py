"""Run report ownership checks without adding capabilities to the batch runtime."""

import argparse
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="pf-varejo-data:local")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    command = [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--read-only",
        "--user",
        "0:0",
        "--security-opt",
        "no-new-privileges:true",
        "--cap-drop",
        "ALL",
    ]
    for capability in ("CHOWN", "FOWNER", "SETGID", "SETUID", "DAC_OVERRIDE"):
        command.extend(["--cap-add", capability])
    command.extend(
        [
            "--tmpfs",
            "/tmp:rw,nosuid,nodev,size=64m",
            "--mount",
            f"type=bind,source={root},target=/app,readonly",
            "--workdir",
            "/app",
            "--env",
            "TMPDIR=/tmp",
            "--env",
            "PYTHONDONTWRITEBYTECODE=1",
            "--env",
            "RETAIL_REPORT_PERMISSION_TESTS=1",
            "--entrypoint",
            "python",
            args.image,
            "-m",
            "pytest",
            "tests/unit/test_report_publication.py",
            "-m",
            "report_permissions",
            "-q",
            "-p",
            "no:cacheprovider",
        ]
    )
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())

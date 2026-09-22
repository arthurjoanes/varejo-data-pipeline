"""Build the bounded Spark core candidate from a hash-pinned official source archive."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from urllib.request import urlopen


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    recipe = root / "vendor/spark-core"
    provenance = json.loads((recipe / "provenance.json").read_text(encoding="utf-8"))
    output = root / "artifacts/spark-core"
    output.mkdir(parents=True, exist_ok=True)
    archive = output / "spark-4.2.0.tgz"
    if not archive.exists():
        with urlopen(provenance["source_url"], timeout=120) as response:
            with archive.open("wb") as handle:
                while block := response.read(1024 * 1024):
                    handle.write(block)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != provenance["source_sha256"]:
        raise RuntimeError("Unexpected Spark source archive SHA-256")
    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--name",
            "fix-varejo-spark-core-build",
            "--cpus",
            "1",
            "--memory",
            "4g",
            "--pids-limit",
            "512",
            "-v",
            f"{recipe}:/recipe:ro",
            "-v",
            f"{output}:/input:ro",
            "-v",
            f"{output}:/output",
            "-v",
            "fix-varejo-spark-build:/build",
            "--entrypoint",
            "sh",
            provenance["builder_image"],
            "/recipe/build.sh",
        ],
        check=True,
    )


if __name__ == "__main__":
    main()

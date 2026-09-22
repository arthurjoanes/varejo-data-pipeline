"""Install explicitly identified local backports after verifying every artifact.

This runs only while building the image. It never downloads code, rewrites Maven
coordinates or modifies an existing JAR's contents. A failed preflight leaves the
original runtime untouched.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RebuiltJar:
    component: str
    source: str
    source_sha256: str
    target: str
    sha256: str
    provenance_path: str
    provenance_sha256: str


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(path: Path) -> list[RebuiltJar]:
    document = json.loads(path.read_text(encoding="utf-8"))
    result = []
    for item in document["rebuilt_components"]:
        artifact = RebuiltJar(**item)
        for name in (artifact.component, artifact.source, artifact.target):
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name):
                raise ValueError(f"Invalid component or JAR name: {name}")
        if not artifact.source.endswith(".jar") or not artifact.target.endswith(".jar"):
            raise ValueError("Runtime replacements must be complete JARs")
        if artifact.source == artifact.target:
            raise ValueError("A local rebuild must have a distinct filename")
        for digest in (
            artifact.source_sha256,
            artifact.sha256,
            artifact.provenance_sha256,
        ):
            if not re.fullmatch(r"[a-f0-9]{64}", digest):
                raise ValueError("Expected a pinned SHA-256 digest")
        parts = artifact.provenance_path.split("/")
        if (
            not artifact.provenance_path.startswith("META-INF/")
            or "\\" in artifact.provenance_path
            or any(part in ("", ".", "..") for part in parts)
            or not artifact.provenance_path.endswith(".json")
        ):
            raise ValueError("Expected an explicit provenance JSON inside META-INF")
        result.append(artifact)
    if not result:
        raise ValueError("No rebuilt components were declared")
    for field in ("component", "source", "target"):
        values = [getattr(item, field) for item in result]
        if len(set(values)) != len(values):
            raise ValueError(f"Duplicate {field} in rebuilt component manifest")
    if {item.source for item in result} & {item.target for item in result}:
        raise ValueError("A replacement cannot shadow another source component")
    return result


def install_rebuilt_jars(
    artifacts: list[RebuiltJar],
    runtime: Path,
    rebuilt: Path,
    evidence: Path,
) -> None:
    records = []
    # Validate the complete set before touching the runtime. ZIP entries are read
    # by exact name; nothing from the archive is extracted into the filesystem.
    for artifact in artifacts:
        original = runtime / artifact.source
        candidate = rebuilt / artifact.component / artifact.target
        target = runtime / artifact.target
        if original.is_symlink() or candidate.is_symlink():
            raise ValueError("Runtime components must be regular files, not links")
        if not original.is_file() or not candidate.is_file():
            raise ValueError(f"Missing source or rebuilt JAR: {artifact.component}")
        if target.exists() or target.is_symlink():
            raise ValueError(f"Duplicate target JAR: {artifact.target}")
        if sha256(original) != artifact.source_sha256:
            raise ValueError(f"Unexpected upstream JAR: {artifact.source}")
        if sha256(candidate) != artifact.sha256:
            raise ValueError(f"Unexpected rebuilt JAR: {artifact.target}")
        with zipfile.ZipFile(candidate) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                raise ValueError("Duplicate ZIP entries in rebuilt JAR")
            if not any(name.endswith(".class") for name in names):
                raise ValueError("Rebuilt JAR has no executable classes")
            if not any(
                name.startswith("META-INF/maven/") and name.endswith("pom.properties")
                for name in names
            ):
                raise ValueError("Rebuilt JAR must retain Maven component metadata")
            info = archive.getinfo(artifact.provenance_path)
            if info.file_size > 1024 * 1024:
                raise ValueError("Oversized rebuild provenance")
            provenance = archive.read(info)
            if hashlib.sha256(provenance).hexdigest() != artifact.provenance_sha256:
                raise ValueError("Rebuild provenance differs from the pinned manifest")
            if not isinstance(json.loads(provenance), dict):
                raise ValueError("Rebuild provenance must be a JSON object")
        records.append((artifact, candidate, provenance))
    evidence.mkdir(parents=True, exist_ok=True)
    for artifact, candidate, provenance in records:
        target = runtime / artifact.target
        shutil.copyfile(candidate, target)
        if sha256(target) != artifact.sha256:
            raise RuntimeError(f"Runtime copy differs from verified JAR: {target.name}")
        (runtime / artifact.source).unlink()
        (evidence / f"{artifact.component}.json").write_bytes(provenance)
        print(f"{artifact.source} -> {artifact.target} ({artifact.sha256})", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("rebuilt", type=Path)
    parser.add_argument("evidence", type=Path)
    args = parser.parse_args()
    import pyspark

    runtime = Path(pyspark.__file__).parent / "jars"
    install_rebuilt_jars(load_manifest(args.manifest), runtime, args.rebuilt, args.evidence)


if __name__ == "__main__":
    main()

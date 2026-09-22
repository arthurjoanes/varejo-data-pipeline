"""Build the custom Hadoop assembly with pinned inputs and an offline replay."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import zipfile
from pathlib import Path
from urllib.request import urlopen

IMAGE = "maven:3.9.11-eclipse-temurin-17@sha256:e4a7ace3dc0d645ed97f8d9ad0b0d3f0b14fa8d150138f27f116d7105a639b82"
SOURCE_DATE_EPOCH = "1790035200"
CENTRAL = "https://repo.maven.apache.org/maven2/"
ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "vendor/hadoop-runtime"
CACHE = ROOT / "artifacts/hadoop-runtime/m2"
LOCK = PROJECT / "inputs.lock.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def maven(arguments: list[str], *, offline: bool) -> None:
    command = [
        "docker",
        "run",
        "--rm",
        "--name",
        "fix-hadoop-residual-assembly",
        "--cpus",
        "1",
        "--memory",
        "1536m",
        "-e",
        "MAVEN_OPTS=-Xmx1024m",
        "-e",
        f"SOURCE_DATE_EPOCH={SOURCE_DATE_EPOCH}",
        "-v",
        f"{PROJECT}:/work",
        "-v",
        f"{CACHE}:/root/.m2/repository",
        "-w",
        "/work",
    ]
    if offline:
        command += ["--network", "none"]
    command += [IMAGE, "mvn", "-B", "-ntp", "-C", "-s", "/work/settings.xml"]
    if offline:
        command.append("-o")
    command += arguments
    print("Running:", " ".join(command), flush=True)
    subprocess.run(command, check=True)


def restore_and_verify() -> None:
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    if lock["toolchain"] != IMAGE or lock["pom_sha256"] != digest(PROJECT / "pom.xml"):
        raise RuntimeError("Build definition changed; reviewed lock regeneration is required")
    for item in lock["maven_inputs"]:
        path = CACHE / item["path"]
        if not path.resolve().is_relative_to(CACHE.resolve()):
            raise ValueError("Invalid locked path")
        if not path.exists():
            with urlopen(CENTRAL + item["path"], timeout=120) as response:
                content = response.read()
            if hashlib.sha256(content).hexdigest() != item["sha256"]:
                raise RuntimeError(f"Unexpected input: {item['path']}")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        if digest(path) != item["sha256"]:
            raise RuntimeError(f"Unexpected cached input: {item['path']}")


def collect_legal_materials() -> None:
    destination = PROJECT / "src/main/resources/META-INF/third-party"
    if destination.exists():
        if not destination.resolve().is_relative_to(PROJECT.resolve()):
            raise ValueError("Generated legal directory escaped the project")
        shutil.rmtree(destination)
    destination.mkdir(parents=True, exist_ok=True)
    classes = PROJECT / "target/classes"
    if classes.exists():
        if not classes.resolve().is_relative_to(PROJECT.resolve()):
            raise ValueError("Generated classes directory escaped the project")
        shutil.rmtree(classes)
    entries = []
    for jar in sorted((PROJECT / "target/dependency").glob("*.jar")):
        materials = []
        with zipfile.ZipFile(jar) as archive:
            for member in archive.namelist():
                name = Path(member).name.lower()
                if (
                    member.endswith("/")
                    or name.endswith((".class", ".jar", ".java", ".so", ".dll", ".dylib"))
                    or not re.search(r"(^|[-_.])(license|notice|copying)($|[-_.])", name)
                ):
                    continue
                output = destination / jar.name / member
                if not output.resolve().is_relative_to(destination.resolve()):
                    raise ValueError("Invalid ZIP member")
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(archive.read(member))
                materials.append(member)
        entries.append({"artifact": jar.name, "sha256": digest(jar), "legal_materials": materials})
    (destination.parent / "retail-build-inputs.json").write_text(
        json.dumps(
            {
                "scope": "Resolved graph, including whole artifacts excluded by the upstream/local shade rules",
                "artifacts": entries,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    upstream = json.loads((PROJECT / "upstream-sources.json").read_text(encoding="utf-8"))
    provenance = {
        "upstream": "org.apache.hadoop:hadoop-client-runtime:3.5.0",
        "custom_build": "retail-security.1 (not an Apache release)",
        "api": "Unmodified published org.apache.hadoop:hadoop-client-api:3.5.0",
        "toolchain": IMAGE,
        "source_date_epoch": SOURCE_DATE_EPOCH,
        "pom_sha256": digest(PROJECT / "pom.xml"),
        "upstream_sources": upstream,
        "changes": [
            "Jackson core/databind/annotations/JAXB/JAX-RS: 2.18.11",
            "JLine: 3.30.17; Commons Configuration: 2.15.1",
            "Commons Lang3: 3.20.0; Text: 1.15.0; IO: 2.22.0; external Logging: 1.3.6",
            "Whole org.eclipse.jetty and org.eclipse.jetty.websocket artifacts excluded",
            "All other upstream shading filters, relocations, and service transformers retained",
        ],
    }
    (destination.parent / "varejo-hadoop-runtime.json").write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    # Preserve upstream identity as well as the custom assembly's own metadata.
    # Using Hadoop coordinates for this project would match the upstream filter
    # that removes all org.apache.hadoop artifacts, including these resources.
    origin = destination.parent / "maven/org.apache.hadoop/hadoop-client-runtime"
    origin.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(PROJECT / "upstream/runtime.pom.xml", origin / "pom.xml")
    (origin / "pom.properties").write_text(
        "# Upstream identity; custom assembly details: META-INF/varejo-hadoop-runtime.json\n"
        "groupId=org.apache.hadoop\nartifactId=hadoop-client-runtime\nversion=3.5.0\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bootstrap-lock",
        action="store_true",
        help="Review-only: resolve inputs and create a new lock",
    )
    args = parser.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)
    source_lock = json.loads((PROJECT / "upstream-sources.json").read_text(encoding="utf-8"))
    for item in source_lock["sources"]:
        if digest(PROJECT / item["path"]) != item["sha256"]:
            raise RuntimeError(f"Upstream source changed: {item['path']}")
    if not args.bootstrap_lock:
        restore_and_verify()
    maven(
        [
            "org.apache.maven.plugins:maven-dependency-plugin:3.8.1:copy-dependencies",
            "-DincludeScope=runtime",
            "-DoutputDirectory=target/dependency",
            "org.apache.maven.plugins:maven-dependency-plugin:3.8.1:tree",
            "-DoutputFile=target/dependency-tree.txt",
        ],
        offline=not args.bootstrap_lock,
    )
    collect_legal_materials()
    maven(["package"], offline=not args.bootstrap_lock)
    if args.bootstrap_lock:
        inputs = [
            {"path": p.relative_to(CACHE).as_posix(), "sha256": digest(p)}
            for p in sorted(CACHE.rglob("*"))
            if p.is_file() and p.suffix in {".jar", ".pom"}
        ]
        LOCK.write_text(
            json.dumps(
                {
                    "toolchain": IMAGE,
                    "repository": CENTRAL,
                    "pom_sha256": digest(PROJECT / "pom.xml"),
                    "maven_inputs": inputs,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
    jar = PROJECT / "target/hadoop-client-runtime-3.5.0-retail-security.1.jar"
    output_lock = PROJECT / "output.sha256"
    if not args.bootstrap_lock and output_lock.exists():
        expected = output_lock.read_text(encoding="utf-8").split()[0]
        if digest(jar) != expected:
            raise RuntimeError("Built artifact differs from the reviewed output SHA-256")
    print(json.dumps({"artifact": str(jar), "sha256": digest(jar)}), flush=True)


if __name__ == "__main__":
    main()

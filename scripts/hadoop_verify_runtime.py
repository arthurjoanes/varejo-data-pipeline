"""Inspect and exercise the custom assembly against the unmodified Hadoop API."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import zipfile
from pathlib import Path
from urllib.request import urlopen

from hadoop_build_runtime import IMAGE, PROJECT, ROOT, SOURCE_DATE_EPOCH


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    jar = PROJECT / "target/hadoop-client-runtime-3.5.0-retail-security.1.jar"
    out = ROOT / "artifacts/hadoop-runtime/out"
    out.mkdir(parents=True, exist_ok=True)
    packages = []
    with zipfile.ZipFile(jar) as archive:
        names = archive.namelist()
        assert not any("/eclipse/jetty/" in name and name.endswith(".class") for name in names)
        assert not any(name.startswith("META-INF/maven/org.eclipse.jetty") for name in names)
        assert not any(
            name.startswith("META-INF/third-party/") and name.endswith((".class", ".jar"))
            for name in names
        )
        assert "META-INF/varejo-hadoop-runtime.json" in names
        assert "META-INF/LICENSE.txt" in names
        assert "META-INF/NOTICE.txt" in names
        assert "META-INF/maven/org.apache.hadoop/hadoop-client-runtime/pom.properties" in names
        provider_relocations = json.loads(
            (PROJECT / "jline-resource-relocations.json").read_text(encoding="utf-8")
        )
        for item in provider_relocations:
            assert (
                hashlib.sha256(archive.read(item["resource"])).hexdigest()
                == item["relocated_sha256"]
            )
        for name in names:
            if name.endswith("/pom.properties"):
                props = {}
                for line in archive.read(name).decode("utf-8").splitlines():
                    if "=" in line and not line.startswith("#"):
                        key, value = line.split("=", 1)
                        props[key] = value
                packages.append(props)
        expected = {
            "jackson-core": "2.18.11",
            "jackson-databind": "2.18.11",
            "jackson-annotations": "2.18.11",
            "jackson-module-jaxb-annotations": "2.18.11",
            "jackson-jaxrs-base": "2.18.11",
            "jackson-jaxrs-json-provider": "2.18.11",
            "jline": "3.30.17",
            "commons-configuration2": "2.15.1",
            "commons-lang3": "3.20.0",
            "commons-text": "1.15.0",
            "commons-io": "2.22.0",
        }
        for name, version in expected.items():
            matches = [p for p in packages if p.get("artifactId") == name]
            assert matches and all(p.get("version") == version for p in matches), (name, matches)
        services = sorted(n for n in names if n.startswith("META-INF/services/"))
        legal_count = sum(
            n.startswith("META-INF/third-party/") and not n.endswith("/") for n in names
        )

    probe_lock = json.loads((PROJECT / "probe-dependencies.lock.json").read_text(encoding="utf-8"))
    external_names = [item["artifact"] for item in probe_lock["artifacts"]]
    external = [PROJECT / "target/spark-external" / name for name in external_names]
    for path, item in zip(external, probe_lock["artifacts"], strict=True):
        if not path.exists():
            with urlopen(item["url"], timeout=120) as response:
                content = response.read()
            assert hashlib.sha256(content).hexdigest() == item["sha256"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        assert sha256(path) == item["sha256"]
    classpath = ":".join(
        ["/work/target/" + jar.name]
        + ["/work/target/spark-external/" + name for name in external_names]
    )
    command = [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--name",
        "fix-hadoop-component-tests",
        "--cpus",
        "1",
        "--memory",
        "512m",
        "-v",
        f"{PROJECT}:/work",
        "-w",
        "/work",
        IMAGE,
        "sh",
        "-c",
        f"mkdir -p target/probe && javac --release 17 -cp '{classpath}' -d target/probe ComponentSmoke.java && timeout 45s java -Xmx256m -Xss256k -cp 'target/probe:{classpath}' ComponentSmoke",
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    (out / "component-tests.log").write_text(
        result.stdout + result.stderr, encoding="utf-8", newline="\n"
    )
    if result.returncode:
        print(result.stdout + result.stderr)
        raise RuntimeError("Hadoop component checks failed")
    assert "PASS local-fs" in result.stdout
    tests = {
        "returncode": result.returncode,
        "network": "none",
        "memory_limit_mib": 512,
        "stdout": result.stdout,
        "source_sha256": sha256(PROJECT / "ComponentSmoke.java"),
        "external_dependencies": probe_lock,
    }
    (out / "component-tests.json").write_text(
        json.dumps(tests, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    shutil.copyfile(jar, out / jar.name)
    shutil.copyfile(PROJECT / "target/dependency-tree.txt", out / "dependency-tree.txt")
    manifest = {
        "upstream": "org.apache.hadoop:hadoop-client-runtime:3.5.0",
        "source_artifact": {
            "file": "hadoop-client-runtime-3.5.0.jar",
            "sha256": "b7db3e60c5df1cd37c2995b3e0142e57487260706834e5325bbe0a5e683eedf1",
        },
        "custom_build": "retail-security.1; not an Apache release",
        "artifact": jar.name,
        "sha256": sha256(jar),
        "bytes": jar.stat().st_size,
        "toolchain": IMAGE,
        "source_date_epoch": SOURCE_DATE_EPOCH,
        "upstream_sources": json.loads(
            (PROJECT / "upstream-sources.json").read_text(encoding="utf-8")
        ),
        "build_definition": {
            name: sha256(PROJECT / name) for name in ["pom.xml", "settings.xml", "inputs.lock.json"]
        },
        "changes": "See embedded META-INF/varejo-hadoop-runtime.json and reviewed pom.xml against upstream/runtime.pom.xml",
        "whole_components_excluded": ["org.eclipse.jetty:*", "org.eclipse.jetty.websocket:*"],
        "jline_provider_resource_relocations": provider_relocations,
        "external_runtime_dependencies_used_in_probe": [
            {"artifact": p.name, "sha256": sha256(p)} for p in external
        ],
        "maven_packages_in_jar": packages,
        "services": services,
        "retained_legal_materials": legal_count,
        "component_checks": tests,
        "scope": "Component checks only. Full Spark/Delta pipeline, migration, publication and image scan are integration gates outside this artifact.",
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(
        json.dumps(
            {
                "artifact": str(out / jar.name),
                "sha256": manifest["sha256"],
                "component_checks": "PASS",
            }
        )
    )


if __name__ == "__main__":
    main()

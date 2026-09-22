"""Verify the actual shaded candidate, its preserved metadata, and a regression control."""

from __future__ import annotations

import hashlib
import json
import subprocess
import zipfile
from pathlib import Path
from urllib.request import urlopen


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def properties(data: bytes) -> dict[str, str]:
    return dict(
        line.split("=", 1)
        for line in data.decode().splitlines()
        if "=" in line and not line.startswith("#")
    )


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    recipe = root / "vendor/spark-core"
    output = root / "artifacts/spark-core"
    provenance = json.loads((recipe / "provenance.json").read_text(encoding="utf-8"))
    assert sha256(recipe / "inputs.sha256") == provenance["maven_inputs"]["sha256"]
    for name, expected in provenance["recipe_sha256"].items():
        assert sha256(recipe / name) == expected, name
    stock = output / "spark-core_2.13-4.2.0-upstream.jar"
    slf4j = output / "slf4j-api-2.0.17.jar"
    inputs = [
        (
            stock,
            "org/apache/spark/spark-core_2.13/4.2.0/spark-core_2.13-4.2.0.jar",
            "8e0a03b66338a4a38c9089d9f798ab6a6c6583aefe93f910311704a5ec90ffc4",
        ),
        (
            slf4j,
            "org/slf4j/slf4j-api/2.0.17/slf4j-api-2.0.17.jar",
            "7b751d952061954d5abfed7181c1f645d336091b679891591d63329c622eb832",
        ),
    ]
    for path, coordinate, expected in inputs:
        if not path.exists():
            with urlopen(
                f"https://repo.maven.apache.org/maven2/{coordinate}", timeout=60
            ) as response:
                path.write_bytes(response.read())
        if sha256(path) != expected:
            raise RuntimeError(f"Unexpected validation input: {path.name}")
    candidate = output / "spark-core_2.13-4.2.0-retail-jetty-12.1.13.jar"
    proof: dict[str, object] = {
        "component": "spark-core",
        "source": "spark-core_2.13-4.2.0.jar",
        "source_sha256": sha256(stock),
        "target": candidate.name,
        "sha256": sha256(candidate),
        "provenance_path": "META-INF/varejo-spark-core.json",
        "provenance": provenance,
    }
    with zipfile.ZipFile(candidate) as rebuilt, zipfile.ZipFile(stock) as original:
        embedded = rebuilt.read("META-INF/varejo-spark-core.json")
        assert json.loads(embedded) == provenance
        proof["provenance_sha256"] = hashlib.sha256(embedded).hexdigest()
        base = properties(
            rebuilt.read("META-INF/maven/org.apache.spark/spark-core_2.13/pom.properties")
        )
        assert base["version"] == "4.2.0" and base["groupId"] == "org.apache.spark"
        jetty = {
            name: properties(rebuilt.read(name))
            for name in rebuilt.namelist()
            if name.startswith("META-INF/maven/org.eclipse.jetty")
            and name.endswith("pom.properties")
        }
        assert len(jetty) >= 10, jetty
        assert {entry["version"] for entry in jetty.values()} == {"12.1.13"}
        assert any("LICENSE" in name for name in rebuilt.namelist())
        assert any("NOTICE" in name for name in rebuilt.namelist())
        proof["jetty_maven_metadata"] = jetty
        original_classes = {
            name
            for name in original.namelist()
            if name.startswith("org/apache/spark/") and name.endswith(".class")
        }
        rebuilt_classes = {
            name
            for name in rebuilt.namelist()
            if name.startswith("org/apache/spark/") and name.endswith(".class")
        }
        assert original_classes == rebuilt_classes
        proof["spark_class_inventory"] = {
            "upstream_count": len(original_classes),
            "rebuilt_count": len(rebuilt_classes),
            "missing": sorted(original_classes - rebuilt_classes),
            "added": sorted(rebuilt_classes - original_classes),
        }
        classes = [
            "security/authentication/DigestAuthenticator.class",
            "server/internal/HttpConnection$RequestHandler.class",
            "server/internal/HttpChannelState.class",
            "util/URIUtil.class",
        ]
        changes = {}
        for name in classes:
            path = f"org/sparkproject/jetty/{name}"
            old_hash = hashlib.sha256(original.read(path)).hexdigest()
            new_hash = hashlib.sha256(rebuilt.read(path)).hexdigest()
            assert old_hash != new_hash, name
            changes[path] = {"original_sha256": old_hash, "rebuilt_sha256": new_hash}
        proof["changed_security_relevant_classes"] = changes
    command = (
        "mkdir -p /output/component-classes; "
        "javac -d /output/component-classes "
        "-cp /output/spark-core_2.13-4.2.0-upstream.jar:/output/slf4j-api-2.0.17.jar "
        "/recipe/JettyComponentCheck.java; "
        "java -Xmx128m -cp /output/component-classes:"
        "/output/spark-core_2.13-4.2.0-upstream.jar:/output/slf4j-api-2.0.17.jar "
        "JettyComponentCheck false; "
        "java -Xmx128m -cp /output/component-classes:"
        "/output/spark-core_2.13-4.2.0-retail-jetty-12.1.13.jar:/output/slf4j-api-2.0.17.jar "
        "JettyComponentCheck true"
    )
    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--name",
            "fix-varejo-jetty-component",
            "--network",
            "none",
            "--memory",
            "512m",
            "--cpus",
            "0.5",
            "-v",
            f"{recipe}:/recipe:ro",
            "-v",
            f"{output}:/output",
            "--entrypoint",
            "sh",
            provenance["builder_image"],
            "-ec",
            command,
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    proof["component_tests"] = [
        json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")
    ]
    proof["limits"] = (
        "No Spark/Delta integration suite in this component check. No network listener."
    )
    (output / "manifest.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(proof["component_tests"]))


if __name__ == "__main__":
    main()

"""Instala artefatos upstream completos, fixados por hash, antes dos testes de integração."""

import hashlib
import json
import sys
from pathlib import Path
from urllib.request import urlopen

import pyspark


def main() -> None:
    manifest = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    target = Path(pyspark.__file__).parent / "jars"
    for artifact in manifest["removed_optional_components"]:
        original = target / artifact["path"]
        if hashlib.sha256(original.read_bytes()).hexdigest() != artifact["sha256"]:
            raise RuntimeError(f"Componente opcional inesperado: {original.name}")
        original.unlink()
        print(f"Removido: {artifact['path']}; {artifact['reason']}", flush=True)
    for artifact in manifest["replacements"]:
        original = target / artifact["source"]
        replacement = target / artifact["target"]
        # An upstream repack or an inconsistent family must stop the build.
        if hashlib.sha256(original.read_bytes()).hexdigest() != artifact["source_sha256"]:
            raise RuntimeError(f"JAR original inesperado: {original.name}")
        with urlopen(artifact["url"], timeout=120) as response:
            content = response.read()
        if hashlib.sha256(content).hexdigest() != artifact["sha256"]:
            raise RuntimeError(f"SHA-256 inválido: {replacement.name}")
        if replacement.exists():
            raise RuntimeError(f"JAR de destino duplicado: {replacement.name}")
        replacement.write_bytes(content)
        original.unlink()
        print(f"{original.name} -> {replacement.name}", flush=True)


if __name__ == "__main__":
    main()

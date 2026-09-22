"""Baixa os jars no build; a execução usa os arquivos da imagem."""

import hashlib
from pathlib import Path
from urllib.request import urlopen

MAVEN = "https://repo.maven.apache.org/maven2/io/delta"
JARS = {
    "delta-spark_4.2_2.13": "27d4fd8b1f879535c573ed1c718177d6a27f24d3e626ba02e216369725721ead",
    "delta-storage": "c46735481fa8e326b0957be02b4420cbcab4b325bb08009b7f2045a95133f1cc",
}


def main() -> None:
    target = Path("/opt/delta-jars")
    target.mkdir(parents=True, exist_ok=True)
    for artifact, expected in JARS.items():
        filename = f"{artifact}-4.4.0.jar"
        with urlopen(f"{MAVEN}/{artifact}/4.4.0/{filename}", timeout=120) as response:
            payload = response.read()
        if hashlib.sha256(payload).hexdigest() != expected:
            raise RuntimeError(f"SHA-256 inválido: {filename}")
        (target / filename).write_bytes(payload)


if __name__ == "__main__":
    main()

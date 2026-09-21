"""Baixa os jars no build; a execução usa os arquivos da imagem."""

import hashlib
from pathlib import Path
from urllib.request import urlopen

MAVEN = "https://repo.maven.apache.org/maven2/io/delta"
JARS = {
    "delta-spark_2.12": "088e187da689a347a6a8556dcb22318e3dfcfb995d807f5e2c19b4d0a7ee9499",
    "delta-storage": "4dcc179fc4076bda5060a4038f979c53e1f5916cf04971e28f9441db390763c7",
}


def main() -> None:
    target = Path("/opt/delta-jars")
    target.mkdir(parents=True, exist_ok=True)
    for artifact, expected in JARS.items():
        filename = f"{artifact}-3.2.1.jar"
        with urlopen(f"{MAVEN}/{artifact}/3.2.1/{filename}", timeout=120) as response:
            payload = response.read()
        if hashlib.sha256(payload).hexdigest() != expected:
            raise RuntimeError(f"SHA-256 inválido: {filename}")
        (target / filename).write_bytes(payload)


if __name__ == "__main__":
    main()

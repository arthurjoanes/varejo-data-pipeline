"""Mostra os últimos logs gravados."""

import os
from collections import deque
from pathlib import Path


def main() -> None:
    root = Path(os.environ.get("RETAIL_DATA_DIR", "/data"))
    paths = sorted(
        (path for path in root.glob("**/logs/*.jsonl") if not path.is_relative_to(root / "tmp")),
        key=lambda path: path.stat().st_mtime,
    )
    if not paths:
        print("Nenhum log persistido; execute um lote primeiro.")
    for path in paths[-5:]:
        print(f"\n{path}")
        with path.open(encoding="utf-8") as handle:
            print("".join(deque(handle, maxlen=30)), end="")


if __name__ == "__main__":
    main()

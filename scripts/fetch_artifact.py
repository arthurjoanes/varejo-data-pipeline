"""Download a pinned artifact, optionally reusing a verified SHA-256 cache."""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from pathlib import Path
from urllib.request import urlopen


def _verified(payload: bytes, expected: str, label: str) -> bytes:
    if hashlib.sha256(payload).hexdigest() != expected:
        raise RuntimeError(f"SHA-256 inválido: {label}")
    return payload


def _cached(path: Path, expected: str, label: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f"Entrada de cache inválida: {label}")
    return _verified(path.read_bytes(), expected, f"cache {label}")


def fetch_artifact(url: str, expected: str, label: str, *, timeout: int = 120) -> bytes:
    """Fail on corrupt cache entries; publish downloads only after hash validation.

    With VAREJO_JAR_CACHE unset/empty, this performs the original direct download
    and hash check. A cache entry is named by its expected digest, never by a URL.
    """
    if re.fullmatch(r"[a-f0-9]{64}", expected) is None:
        raise ValueError("Expected a pinned lowercase SHA-256 digest")
    cache_value = os.environ.get("VAREJO_JAR_CACHE")
    cache = Path(cache_value) if cache_value else None
    entry = cache / expected if cache is not None else None
    if entry is not None and (entry.exists() or entry.is_symlink()):
        return _cached(entry, expected, label)

    with urlopen(url, timeout=timeout) as response:
        payload = _verified(response.read(), expected, label)
    if cache is None or entry is None:
        return payload

    cache.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=cache, prefix=f".{expected}.", suffix=".tmp", delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        # Atomic create-if-absent also handles a producer winning the race.
        # Never overwrite an existing entry, even if it appeared after download.
        try:
            os.link(temporary, entry)
        except FileExistsError:
            _cached(entry, expected, label)
        return payload
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)

import hashlib
import importlib.util
import io
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "jar_cache_under_test", Path(__file__).parents[2] / "scripts/fetch_artifact.py"
)
assert SPEC is not None and SPEC.loader is not None
cache_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cache_module)

PAYLOAD = b"locked complete artifact bytes"
DIGEST = hashlib.sha256(PAYLOAD).hexdigest()
URL = "https://repo.maven.apache.org/example.jar"


def no_network(*args, **kwargs):
    pytest.fail("A cache hit or corrupt cache must not access the network")


def test_cache_hit_revalidates_bytes_without_network(tmp_path, monkeypatch):
    monkeypatch.setenv("VAREJO_JAR_CACHE", str(tmp_path))
    (tmp_path / DIGEST).write_bytes(PAYLOAD)
    monkeypatch.setattr(cache_module, "urlopen", no_network)
    assert cache_module.fetch_artifact(URL, DIGEST, "example.jar") == PAYLOAD

    (tmp_path / DIGEST).write_bytes(b"changed after the successful first use")
    with pytest.raises(RuntimeError, match="SHA-256 inválido: cache"):
        cache_module.fetch_artifact(URL, DIGEST, "example.jar")
    assert (tmp_path / DIGEST).read_bytes() != PAYLOAD


def test_download_mismatch_never_publishes_cache_entry(tmp_path, monkeypatch):
    monkeypatch.setenv("VAREJO_JAR_CACHE", str(tmp_path))
    monkeypatch.setattr(cache_module, "urlopen", lambda *a, **k: io.BytesIO(b"wrong artifact"))
    with pytest.raises(RuntimeError, match="SHA-256 inválido"):
        cache_module.fetch_artifact(URL, DIGEST, "example.jar")
    assert list(tmp_path.iterdir()) == []


def test_verified_download_is_published_atomically_then_reused(tmp_path, monkeypatch):
    monkeypatch.setenv("VAREJO_JAR_CACHE", str(tmp_path))
    monkeypatch.setattr(cache_module, "urlopen", lambda *a, **k: io.BytesIO(PAYLOAD))
    link = cache_module.os.link
    published = []

    def checked_link(source, destination):
        assert source.parent == tmp_path
        assert source.read_bytes() == PAYLOAD
        assert destination == tmp_path / DIGEST
        assert not destination.exists()
        link(source, destination)
        published.append(destination)

    monkeypatch.setattr(cache_module.os, "link", checked_link)
    assert cache_module.fetch_artifact(URL, DIGEST, "example.jar") == PAYLOAD
    assert published == [tmp_path / DIGEST]
    assert list(tmp_path.iterdir()) == published
    monkeypatch.setattr(cache_module, "urlopen", no_network)
    assert cache_module.fetch_artifact(URL, DIGEST, "example.jar") == PAYLOAD


def test_without_cache_downloads_and_verifies_without_cache_writes(tmp_path, monkeypatch):
    monkeypatch.delenv("VAREJO_JAR_CACHE", raising=False)
    monkeypatch.chdir(tmp_path)
    calls = []

    def download(url, *, timeout):
        calls.append((url, timeout))
        return io.BytesIO(PAYLOAD)

    monkeypatch.setattr(cache_module, "urlopen", download)
    assert cache_module.fetch_artifact(URL, DIGEST, "example.jar") == PAYLOAD
    assert calls == [(URL, 120)]
    assert list(tmp_path.iterdir()) == []


def test_bad_entry_created_during_download_is_not_overwritten(tmp_path, monkeypatch):
    monkeypatch.setenv("VAREJO_JAR_CACHE", str(tmp_path))

    def competing_download(*args, **kwargs):
        (tmp_path / DIGEST).write_bytes(b"concurrent corrupt entry")
        return io.BytesIO(PAYLOAD)

    monkeypatch.setattr(cache_module, "urlopen", competing_download)
    with pytest.raises(RuntimeError, match="SHA-256 inválido: cache"):
        cache_module.fetch_artifact(URL, DIGEST, "example.jar")
    assert (tmp_path / DIGEST).read_bytes() == b"concurrent corrupt entry"
    assert list(tmp_path.iterdir()) == [tmp_path / DIGEST]

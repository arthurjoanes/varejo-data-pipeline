import sys
from pathlib import Path

import pytest

from retail_pipeline import cli, spark


@pytest.mark.parametrize(
    "arguments,message",
    [
        (["explain", "--limit", "0"], "--limit"),
        (["explain", "--limit", "101"], "--limit"),
        (["explain", "--limit", "-1"], "--limit"),
        (["explain", "--limit", "1.5"], "invalid int"),
        (["explain", "--store-id", "../x"], "--store-id"),
        (["explain", "--store-id", ""], "--store-id"),
        (["explain", "--business-date", "2026-02-29"], "--business-date"),
        (["explain", "--business-date", "20260201"], "--business-date"),
        (["explain", "--business-date", "2026-W01-1"], "--business-date"),
        (["explain", "--business-date", "2026-01-01T00:00:00Z"], "--business-date"),
        (["generate", "--batch-id", "../input"], "--batch-id"),
        (["generate", "--batch-id", "a" * 65], "--batch-id"),
        (["generate", "--rows", "0"], "--rows"),
        (["generate", "--rows", "-10"], "--rows"),
        (["generate", "--size", "demo", "--scenario", "corrected"], "fixture"),
        (["run", "input", "--fail-at", "after_gold"], "--demo-mode"),
    ],
)
def test_cli_rejects_invalid_fields_without_starting_spark(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
    arguments: list[str],
    message: str,
) -> None:
    def forbidden():
        pytest.fail("Erro de uso iniciou Spark.")

    monkeypatch.setattr(spark, "create_spark", forbidden)
    monkeypatch.setattr(sys, "argv", ["varejo", "--data-dir", str(tmp_path / "state"), *arguments])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 2
    assert message in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == []


def test_generate_never_overwrites_an_existing_delivery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "input"
    source.mkdir()
    original = source / "S01.csv"
    original.write_bytes(b"original delivery\x00\xff")
    monkeypatch.setattr(sys, "argv", ["varejo", "generate", "--output", str(source)])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 2
    assert original.read_bytes() == b"original delivery\x00\xff"
    assert sorted(path.name for path in source.iterdir()) == ["S01.csv"]


@pytest.mark.parametrize("limit,business_date", [(1, "2024-02-29"), (100, "9999-12-31")])
def test_explain_accepts_canonical_boundary_fields(limit: int, business_date: str) -> None:
    command_parser = cli.parser()
    arguments = command_parser.parse_args(
        ["explain", "--limit", str(limit), "--business-date", business_date, "--store-id", "A" * 64]
    )
    cli.validate_arguments(arguments, command_parser)


def test_generate_accepts_empty_directory_without_engine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "input"
    output.mkdir()
    monkeypatch.setattr(spark, "create_spark", lambda: pytest.fail("Geração iniciou Spark."))
    monkeypatch.setattr(
        sys, "argv", ["varejo", "generate", "--output", str(output), "--batch-id", "A" * 64]
    )
    assert cli.main() == 0
    assert {p.name for p in output.iterdir()} == {
        "manifest.json",
        "catalog.json",
        "schedule.json",
        "S01.csv",
        "S02.csv",
    }

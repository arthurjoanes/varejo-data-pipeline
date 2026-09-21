from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from datetime import date
from pathlib import Path

from retail_pipeline.contracts import valid_identifier
from retail_pipeline.generation import SCENARIOS, generate_scenario
from retail_pipeline.publication import json_scalar


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Pipeline local de vendas em Delta Lake")
    result.add_argument(
        "--data-dir",
        type=Path,
        default=Path(os.getenv("RETAIL_DATA_DIR", "/data")),
        help="Pasta de dados e estado (padrão: /data)",
    )
    commands = result.add_subparsers(dest="command", required=True)
    configure = commands.add_parser("configure", help="Fixar referências aprovadas do operador")
    configure.add_argument("--catalog", type=Path, required=True)
    configure.add_argument("--schedule", type=Path, required=True)
    generate = commands.add_parser("generate", help="Gerar dados de teste")
    generate.add_argument("--output", type=Path, default=Path("/data/input"))
    generate.add_argument("--size", choices=("fixture", "demo", "scale"), default="fixture")
    generate.add_argument("--scenario", choices=SCENARIOS, default="valid")
    generate.add_argument("--batch-id", default="fixture-valid")
    generate.add_argument("--seed", type=int, default=42)
    generate.add_argument("--rows", type=int, default=30000)
    for name, description in (
        ("validate", "Validar sem publicar"),
        ("run", "Processar e publicar o lote"),
    ):
        command = commands.add_parser(name, help=description)
        command.add_argument("input", type=Path)
        if name == "run":
            command.add_argument(
                "--demo-mode",
                action="store_true",
                help="Permitir a falha de teste nesta execução",
            )
            command.add_argument(
                "--fail-at", choices=("after_ingestion", "after_gold", "before_publish")
            )
    report = commands.add_parser("report", help="Gerar relatório HTML")
    report.add_argument(
        "--output",
        type=Path,
        default=Path(os.getenv("RETAIL_EXPORT_DIR", "/app/artifacts")) / "report.html",
    )
    explain = commands.add_parser(
        "explain", help="Mostrar revisões e arquivos de uma amostra do indicador"
    )
    explain.add_argument("--store-id")
    explain.add_argument("--business-date")
    explain.add_argument("--limit", type=int, default=20)
    demo = commands.add_parser("demo", help="Executar a demo com falhas e recuperação")
    demo.add_argument(
        "--output", type=Path, default=Path(os.getenv("RETAIL_EXPORT_DIR", "/app/artifacts"))
    )
    return result


def validate_arguments(
    arguments: argparse.Namespace, command_parser: argparse.ArgumentParser
) -> None:
    """Erros de uso são resolvidos antes de abrir Spark ou escrever arquivos."""
    if arguments.command == "generate":
        if not valid_identifier(arguments.batch_id):
            command_parser.error(
                "--batch-id deve ser um identificador válido de até 64 caracteres."
            )
        if arguments.rows <= 0:
            command_parser.error("--rows deve ser um inteiro positivo.")
        if arguments.size != "fixture" and arguments.scenario not in {"valid", "missing"}:
            command_parser.error("Cenários de revisão exigem --size fixture.")
        output = arguments.output
        if output.is_symlink() or (
            output.exists() and (not output.is_dir() or any(output.iterdir()))
        ):
            command_parser.error("--output exige uma pasta nova ou vazia.")
    if arguments.command == "run" and arguments.fail_at and not arguments.demo_mode:
        command_parser.error("--fail-at exige --demo-mode.")
    if arguments.command == "explain":
        if not 1 <= arguments.limit <= 100:
            command_parser.error("--limit deve ficar entre 1 e 100.")
        if arguments.store_id is not None and not valid_identifier(arguments.store_id):
            command_parser.error("--store-id inválido.")
        if arguments.business_date is not None:
            try:
                parsed = date.fromisoformat(arguments.business_date)
                if parsed.isoformat() != arguments.business_date:
                    raise ValueError
            except ValueError:
                command_parser.error(
                    "--business-date deve ser uma data válida no formato AAAA-MM-DD."
                )


def main() -> int:
    command_parser = parser()
    arguments = command_parser.parse_args()
    validate_arguments(arguments, command_parser)
    spark = None
    try:
        if arguments.command == "configure":
            from retail_pipeline.ingestion import _read_json
            from retail_pipeline.references import configure_references

            issues: list[dict[str, object]] = []
            catalog = _read_json(arguments.catalog, issues, "CATALOG")
            schedule = _read_json(arguments.schedule, issues, "SCHEDULE")
            if issues:
                raise ValueError(f"Documentos de referência inválidos: {issues}")
            references = configure_references(arguments.data_dir, catalog, schedule)
            print(json.dumps({"state": "CONFIGURED", "reference_hash": references.digest}))
            return 0
        if arguments.command == "generate":
            output = generate_scenario(
                arguments.output,
                size=arguments.size,
                seed=arguments.seed,
                rows=arguments.rows,
                batch_id=arguments.batch_id,
                scenario=arguments.scenario,
            )
            print(f"Dados gerados: {output}")
            return 0
        from retail_pipeline.spark import create_spark

        spark = create_spark()
        if arguments.command in ("validate", "run"):
            from retail_pipeline.pipeline import process_batch

            outcome = process_batch(
                spark,
                arguments.data_dir,
                arguments.input,
                validate_only=arguments.command == "validate",
                fail_at=getattr(arguments, "fail_at", None),
                allow_failures=getattr(arguments, "demo_mode", False),
            )
            print(json.dumps(asdict(outcome), ensure_ascii=False, indent=2))
            return outcome.exit_code
        if arguments.command == "report":
            from retail_pipeline.reporting import generate_report

            print(
                f"Relatório gerado: {generate_report(spark, arguments.data_dir, arguments.output)}"
            )
        elif arguments.command == "explain":
            from retail_pipeline.reporting import explain_indicator

            print(
                json.dumps(
                    explain_indicator(
                        spark,
                        arguments.data_dir,
                        store_id=arguments.store_id,
                        business_date=arguments.business_date,
                        limit=arguments.limit,
                    ),
                    ensure_ascii=False,
                    indent=2,
                    default=json_scalar,
                )
            )
        elif arguments.command == "demo":
            from retail_pipeline.demo import run_demo

            run_demo(spark, arguments.data_dir, arguments.output)
        return 0
    except Exception as exc:
        print(json.dumps({"state": "TECHNICAL_FAILURE", "message": str(exc)}, ensure_ascii=False))
        return 3
    finally:
        if spark is not None:
            spark.stop()


if __name__ == "__main__":
    raise SystemExit(main())

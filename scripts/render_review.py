"""Reproduz a apresentação a partir de snapshots sintéticos, sem executar lotes.

--capture relê as publicações da demonstração histórica em um volume já existente.
Sem essa opção, apenas reprocessa os payloads versionados; não importa nem inicia Spark.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from contextlib import ExitStack
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from retail_pipeline.report_model import ReportPayload
from retail_pipeline.report_view import build_report_html


def capture(output: Path) -> None:
    from retail_pipeline import reporting
    from retail_pipeline.spark import create_spark

    project = Path(__file__).resolve().parents[1]
    demo_file = project / "docs/evidence/round-2/demo.json"
    benchmark_file = project / "docs/evidence/benchmark.json"
    demo = json.loads(demo_file.read_text(encoding="utf-8"))
    benchmark = json.loads(benchmark_file.read_text(encoding="utf-8"))
    demo_root = Path(demo["data_dir"])
    if not (demo_root / "publication.json").is_file():
        raise SystemExit(
            "Volume não contém a demonstração histórica indicada em round-2/demo.json."
        )
    payload_dir = output / "payloads"
    payload_dir.mkdir(parents=True, exist_ok=True)
    spark = create_spark()

    def render(name: str, root: Path, evidence: Path, *, snapshot=None, attempt=None) -> None:
        def captured(payload: ReportPayload) -> str:
            envelope = {
                "captured_at": datetime.now(UTC).isoformat(),
                "method": "Leitura Delta por versão; nenhum lote executado.",
                "selection": (
                    "Passo histórico reconstituído do manifesto imutável e da tentativa registrada."
                    if attempt is not None
                    else "Manifesto e registros presentes no volume histórico no momento da captura."
                ),
                "read_runtime": {"spark": spark.version},
                "source_evidence": str(evidence.relative_to(project)),
                "source_sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
                "payload": asdict(payload),
            }
            (payload_dir / f"{name}.json").write_text(
                json.dumps(envelope, ensure_ascii=False, indent=2, default=str) + "\n",
                encoding="utf-8",
            )
            return build_report_html(payload)

        with ExitStack() as stack:
            stack.enter_context(patch.object(reporting, "build_report_html", captured))
            if attempt is not None:
                # Reconstitui a leitura daquele passo usando o manifesto imutável
                # e o resultado registrado; o ponteiro no volume não é modificado.
                stack.enter_context(
                    patch("retail_pipeline.publication.load_snapshot", return_value=snapshot)
                )
                failed = attempt if attempt["state"] in {"BLOCKED", "TECHNICAL_FAILURE"} else None
                stack.enter_context(
                    patch.object(reporting, "_read_attempts", return_value=(attempt, failed))
                )
            reporting.generate_report(spark, root, output / f"{name}.html", synthetic_data=True)
        print(f"Capturado: {name}", flush=True)

    try:
        render("demo30k-report", Path(benchmark["data_dir"]), benchmark_file)
        render("report", demo_root, demo_file)
        previous_publication = None
        for step in demo["steps"]:
            result = step["result"]
            if result.get("publication_id"):
                previous_publication = json.loads(
                    (demo_root / "publications" / f"{result['publication_id']}.json").read_text(
                        encoding="utf-8"
                    )
                )
            names = {"missing-delivery": "blocked-report", "recoverable": "failure-report"}
            if step["step"] in names:
                render(
                    names[step["step"]],
                    demo_root,
                    demo_file,
                    snapshot=previous_publication,
                    attempt=result,
                )
        render("quality-review", demo_root, demo_file, attempt=demo["quality_check"])
    finally:
        spark.stop()


def replay(payload_dir: Path, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for path in sorted(payload_dir.glob("*.json")):
        payload = ReportPayload(**json.loads(path.read_text(encoding="utf-8"))["payload"])
        (output / f"{path.stem}.html").write_text(build_report_html(payload), encoding="utf-8")
    # Fixtures de renderização, não resultados de novas execuções do pipeline.
    baseline = ReportPayload(
        **json.loads((payload_dir / "report.json").read_text(encoding="utf-8"))["payload"]
    )
    fixtures = {
        "empty-fixture": ReportPayload(synthetic_data=True),
        "running-fixture": ReportPayload(
            synthetic_data=True, latest_attempt={"state": "RUNNING", "stats": {}}
        ),
        "audit-fixture": replace(
            baseline,
            latest_attempt={
                **(baseline.latest_attempt or {}),
                "state": "PUBLISHED",
                "audit_incomplete": True,
                "stats": {},
            },
        ),
        "long-fixture": replace(
            baseline,
            latest_attempt={
                "state": "BLOCKED",
                "batch_id": "lote-longo-" + "a" * 240,
                "run_id": "execucao-" + "b" * 240,
                "issues": [{"code": "CAMPO_" + "C" * 160, "message": "D" * 500}],
            },
        ),
    }
    for name, payload in fixtures.items():
        (output / f"{name}.html").write_text(build_report_html(payload), encoding="utf-8")
    print(f"Relatórios gerados em {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", action="store_true")
    parser.add_argument(
        "--payload-dir", type=Path, default=Path("docs/evidence/interface/payloads")
    )
    parser.add_argument("--output", type=Path, default=Path("artifacts/interface"))
    args = parser.parse_args()
    if args.capture:
        capture(args.output)
    else:
        replay(args.payload_dir, args.output)

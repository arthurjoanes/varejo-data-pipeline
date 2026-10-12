"""Renderiza payloads capturados, offline, sem executar Spark ou novas entregas."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import retail_pipeline
from retail_pipeline.report_model import ReportPayload
from retail_pipeline.report_view import build_report_html


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replay(inputs: Path, output: Path, phase: str) -> None:
    payloads = sorted(inputs.glob("*.json"))
    if not payloads:
        raise SystemExit("Nenhum payload JSON encontrado.")
    if output.exists():
        raise SystemExit("Use uma pasta de saída nova para preservar as capturas anteriores.")
    manifest_path = output.parent / f"corpus-{phase}.json"
    if manifest_path.exists():
        raise SystemExit("Manifesto já existe; escolha uma pasta-pai nova para esta captura.")
    output.mkdir(parents=True)
    records = []
    for path in payloads:
        envelope = json.loads(path.read_text(encoding="utf-8"))
        page = build_report_html(ReportPayload(**envelope["payload"]))
        if envelope.get("presentation_only"):
            page = page.replace(
                "Demonstração com dados sintéticos.",
                "Fixture de apresentação com dados sintéticos; nenhuma nova execução do pipeline.",
            )
        target = output / f"{path.stem}.html"
        target.write_bytes(page.encode("utf-8"))
        records.append(
            {
                "name": path.stem,
                "input_sha256": sha(path),
                "html_sha256": sha(target),
                "presentation_only": bool(envelope.get("presentation_only")),
                "method": envelope.get("method"),
            }
        )
    package = Path(retail_pipeline.__file__).parent
    renderer = {
        f"retail_pipeline/{path.relative_to(package).as_posix()}": sha(path)
        for path in sorted(package.rglob("*"))
        if path.is_file()
        and "__pycache__" not in path.parts
        and (path.name.startswith("report") or path.parent.name == "assets")
    }
    manifest = {
        "phase": phase,
        "captured_at": datetime.now(UTC).isoformat(),
        "spark_started": False,
        "new_batches": 0,
        "inputs": records,
        "script_sha256": sha(Path(__file__)),
        "renderer": renderer,
    }
    manifest_path.write_bytes(
        (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    )
    print(f"{phase}: {len(records)} payloads renderizados offline.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--phase", choices=["before", "after"], default="after")
    args = parser.parse_args()
    replay(args.inputs, args.output, args.phase)

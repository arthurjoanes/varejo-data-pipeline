"""Small reproducible fixtures for profile comparison and postcommit lineage recovery."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from retail_pipeline.generation import default_catalog, default_schedule, fixture_rows, write_batch
from retail_pipeline.lineage import canonical_run_id, export_lineage, validate_event
from retail_pipeline.pipeline import process_batch
from retail_pipeline.profiling import load_profile
from retail_pipeline.publication import atomic_json, load_snapshot
from retail_pipeline.references import configure_references
from retail_pipeline.reporting import generate_report
from retail_pipeline.spark import create_spark


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, default=Path("/data/evolution-demo"))
    parser.add_argument("--output", type=Path, default=Path("/app/artifacts/evolution-demo"))
    args = parser.parse_args()
    if args.state_dir.exists() or args.output.exists():
        parser.error("Use estado e diretório de saída novos para preservar evidências anteriores.")
    args.output.mkdir(parents=True)
    configure_references(args.state_dir, default_catalog(), default_schedule())
    engine = create_spark()
    steps = []
    try:
        cases = [("initial", fixture_rows(), None)]
        revised = fixture_rows()
        revised[0].update(revision="2", unit_price_brl="30.00")
        cases.append(("comparable", revised, "lineage_export"))
        moved = fixture_rows()
        for row in moved:
            row.update(
                revision="3",
                sold_at="2026-01-10T12:00:00-03:00",
                source_updated_at="2026-01-11T08:00:00-03:00",
            )
        cases.append(("incomparable", moved, None))
        for name, rows, failure in cases:
            source = write_batch(args.state_dir / "inputs" / name, rows, batch_id=name)
            result = process_batch(
                engine, args.state_dir, source, fail_at=failure, allow_failures=bool(failure)
            )
            if result.state != "PUBLISHED":
                raise ValueError(f"{name}: {result.state}: {result.issues}")
            snapshot = load_snapshot(args.state_dir)
            assert snapshot is not None
            read = load_profile(snapshot)
            assert read["status"] == "AVAILABLE" and read["profile"] is not None
            expected = {
                "initial": "NO_BASELINE",
                "comparable": "COMPARABLE",
                "incomparable": "NOT_COMPARABLE",
            }[name]
            assert read["profile"]["comparison"]["status"] == expected
            atomic_json(args.output / f"{name}-profile.json", read)
            atomic_json(args.output / f"{name}-publication.json", snapshot)
            generate_report(
                engine, args.state_dir, args.output / f"{name}.html", synthetic_data=True
            )
            if failure:
                terminal = (
                    args.state_dir
                    / "lineage/events"
                    / canonical_run_id(result.run_id)
                    / "terminal.json"
                )
                assert not terminal.exists()
                preserved = {
                    path: hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in [
                        args.state_dir / "publication.json",
                        Path(snapshot["profile"]["path"]),
                        *list((args.state_dir / "runs").rglob("evidence/raw/*")),
                    ]
                    if path.is_file()
                }
                exported = export_lineage(args.state_dir)
                assert exported["errors"] == []
                event = json.loads(terminal.read_text())
                validate_event(event)
                assert event["eventType"] == "COMPLETE"
                first_bytes = terminal.read_bytes()
                assert export_lineage(args.state_dir)["errors"] == []
                assert terminal.read_bytes() == first_bytes
                assert all(
                    hashlib.sha256(path.read_bytes()).hexdigest() == checksum
                    for path, checksum in preserved.items()
                )
                atomic_json(
                    args.output / "reexport.json",
                    {
                        "run_id": result.run_id,
                        "publication_preserved": True,
                        "evidence_bytes_preserved": True,
                        "terminal_bytes_idempotent": True,
                        "export": exported,
                    },
                )
                atomic_json(args.output / "reexport-terminal.json", event)
            steps.append(
                {
                    "scenario": name,
                    "outcome": asdict(result),
                    "comparison": read["profile"]["comparison"],
                    "profile_stage_seconds": result.stages.get("profile"),
                }
            )
        atomic_json(
            args.output / "execution.json",
            {
                "executed_at": datetime.now(UTC).isoformat(),
                "synthetic": True,
                "steps": steps,
                "limits": "Fixtures pequenas; duração observada inclui Spark e carga concorrente, sem benchmark pareado.",
            },
        )
    finally:
        engine.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

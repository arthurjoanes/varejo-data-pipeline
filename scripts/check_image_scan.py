"""Bloqueia achados graves novos; preserva a triagem explícita do batch local."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def finding_key(finding: dict) -> tuple[str, ...]:
    return tuple(
        str(finding.get(name, ""))
        for name in ("VulnerabilityID", "PkgName", "InstalledVersion", "PkgPath", "Severity")
    )


def unreviewed_findings(report: dict, review: dict) -> list[dict]:
    results = report.get("Results", [])
    scanned_types = {result.get("Type") for result in results}
    if not {"alpine", "jar", "python-pkg"} <= scanned_types:
        raise ValueError("O relatório deve incluir sistema Alpine, JVM e Python.")
    accepted = {
        finding_key(item)
        for item in review["findings"]
        if item.get("assessment") == "not_reachable_in_supported_local_batch"
        and item.get("rationale")
    }
    return [
        finding
        for result in results
        for finding in result.get("Vulnerabilities", [])
        if finding.get("Severity") in {"HIGH", "CRITICAL"}
        and (result.get("Type") != "jar" or finding_key(finding) not in accepted)
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--review", type=Path, default=Path("docs/evidence/security-triage.json"))
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    review = json.loads(args.review.read_text(encoding="utf-8"))
    unknown = unreviewed_findings(report, review)
    for item in unknown:
        print("Revisão necessária:", *finding_key(item))
    print(f"Achados HIGH/CRITICAL sem triagem aplicável: {len(unknown)}")
    return int(bool(unknown))


if __name__ == "__main__":
    raise SystemExit(main())

"""Bloqueia todos os achados HIGH/CRITICAL no inventário integral da imagem."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def finding_key(finding: dict) -> tuple[str, ...]:
    return tuple(
        str(finding.get(name, ""))
        for name in ("VulnerabilityID", "PkgName", "InstalledVersion", "PkgPath", "Severity")
    )


def severe_findings(report: dict) -> list[dict]:
    results = report.get("Results", [])
    scanned_types = {result.get("Type") for result in results}
    if not {"alpine", "jar", "python-pkg"} <= scanned_types:
        raise ValueError("O relatório deve incluir sistema Alpine, JVM e Python.")
    return [
        finding
        for result in results
        for finding in result.get("Vulnerabilities", [])
        if finding.get("Severity") in {"HIGH", "CRITICAL"}
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    unknown = severe_findings(report)
    for item in unknown:
        print("Revisão necessária:", *finding_key(item))
    print(f"Achados HIGH/CRITICAL: {len(unknown)}")
    return int(bool(unknown))


if __name__ == "__main__":
    raise SystemExit(main())

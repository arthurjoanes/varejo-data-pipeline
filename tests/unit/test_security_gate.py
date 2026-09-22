import runpy
from pathlib import Path

import pytest

check = runpy.run_path(str(Path(__file__).parents[2] / "scripts/check_image_scan.py"))[
    "severe_findings"
]


def test_scan_gate_blocks_every_high_and_critical_across_all_ecosystems():
    report = {"Results": []}
    for ecosystem in ("alpine", "jar", "python-pkg"):
        report["Results"].append(
            {
                "Type": ecosystem,
                "Vulnerabilities": [
                    {"VulnerabilityID": f"example-{ecosystem}-{severity}", "Severity": severity}
                    for severity in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
                ],
            }
        )
    blocked = check(report)
    assert len(blocked) == 6
    assert {item["Severity"] for item in blocked} == {"HIGH", "CRITICAL"}


def test_scan_gate_requires_inventory_of_all_three_ecosystems():
    report = {"Results": [{"Type": kind} for kind in ("alpine", "jar", "python-pkg")]}
    assert check(report) == []
    for index in range(3):
        incomplete = {"Results": report["Results"][:index] + report["Results"][index + 1 :]}
        with pytest.raises(ValueError, match="Alpine, JVM e Python"):
            check(incomplete)

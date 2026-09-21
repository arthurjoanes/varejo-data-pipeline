import copy
import runpy
from pathlib import Path

import pytest

check = runpy.run_path(str(Path(__file__).parents[2] / "scripts/check_image_scan.py"))[
    "unreviewed_findings"
]


def fixture():
    finding = {
        "VulnerabilityID": "CVE-2026-0000",
        "PkgName": "example:component",
        "InstalledVersion": "1.0",
        "PkgPath": "jars/component-1.0.jar",
        "Severity": "HIGH",
    }
    report = {
        "Results": [
            {"Type": "alpine"},
            {"Type": "python-pkg"},
            {"Type": "jar", "Vulnerabilities": [finding]},
        ]
    }
    review = {
        "findings": [
            {
                **finding,
                "assessment": "not_reachable_in_supported_local_batch",
                "rationale": "Exemplo sintético para testar a fronteira do verificador.",
            }
        ]
    }
    return report, review


def test_scan_gate_accepts_only_exact_reviewed_jvm_finding():
    report, review = fixture()
    assert check(report, review) == []
    changed = copy.deepcopy(report)
    changed["Results"][2]["Vulnerabilities"][0]["InstalledVersion"] = "2.0"
    assert len(check(changed, review)) == 1
    changed["Results"][2]["Type"] = "python-pkg"
    changed["Results"].append({"Type": "jar"})
    assert len(check(changed, review)) == 1


def test_scan_gate_rejects_new_cve_and_incomplete_inventory():
    report, review = fixture()
    report["Results"][2]["Vulnerabilities"][0]["VulnerabilityID"] = "CVE-2026-0001"
    assert len(check(report, review)) == 1
    report["Results"].pop(0)
    with pytest.raises(ValueError, match="Alpine, JVM e Python"):
        check(report, review)

"""Build and verify the narrowly scoped Commons Lang 2.6 upstream backport.

Run inside vendor/commons-lang/Builder.Dockerfile with --cpus=1 --memory=1g.
No Maven resolution, changes to upstream tests or removal of legacy classes.
The default gates cover the patched class and official regression/control.
--upstream-suite also runs the full historical suite and returns nonzero on
any failure, including baseline failures under this modern JDK.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import os
import shutil
import struct
import subprocess
import tarfile
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor" / "commons-lang"
CLASS = "org/apache/commons/lang/ClassUtils.class"
FIXED_TIME = (2025, 11, 13, 17, 0, 26)
FIXED_DATE = "2025-11-13T17:00:26Z"
UPSTREAM_EXCLUDES = {"EntitiesPerformanceTest.java", "RandomUtilsFreqTest.java"}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dump(data: object) -> bytes:
    return (json.dumps(data, sort_keys=True, indent=2) + "\n").encode()


def command(
    args: list[str], *, cwd: Path, log: Path, timeout: int = 180
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    log.write_text(result.stdout + result.stderr, encoding="utf-8")
    return result


def require(result: subprocess.CompletedProcess[str], stage: str) -> None:
    if result.returncode:
        raise RuntimeError(f"{stage} failed with exit {result.returncode}; see its preserved log")


def extract(source: Path, destination: Path) -> Path:
    with tarfile.open(source, "r:gz") as archive:
        for entry in archive.getmembers():
            if not (entry.isfile() or entry.isdir()):
                raise ValueError(f"Unsupported archive entry: {entry.name}")
            target = (destination / entry.name).resolve()
            if not target.is_relative_to(destination.resolve()):
                raise ValueError("Source archive escapes extraction directory")
        archive.extractall(destination, filter="data")
    children = list(destination.iterdir())
    if len(children) != 1 or not children[0].is_dir():
        raise ValueError("Expected one upstream source root")
    return children[0]


def zip_records(raw: bytes) -> tuple[list[tuple[zipfile.ZipInfo, bytes, bytes]], bytes]:
    """Retain every unchanged ZIP member's compressed local record and metadata."""
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        infos = archive.infolist()
        records = []
        central = archive.start_dir
        for index, item in enumerate(infos):
            if raw[central : central + 4] != b"PK\x01\x02":
                raise ValueError("Invalid central directory")
            name_len, extra_len, comment_len = struct.unpack_from("<HHH", raw, central + 28)
            size = 46 + name_len + extra_len + comment_len
            central_record = raw[central : central + size]
            end = infos[index + 1].header_offset if index + 1 < len(infos) else archive.start_dir
            records.append((item, raw[item.header_offset : end], central_record))
            central += size
        return records, archive.comment


def one_record(
    name: str, content: bytes, template: zipfile.ZipInfo | None = None
) -> tuple[zipfile.ZipInfo, bytes, bytes]:
    info = copy.copy(template) if template is not None else zipfile.ZipInfo(name, FIXED_TIME)
    if template is None:
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o100644 << 16
        info.create_system = 3
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.writestr(info, content, compresslevel=9)
    return zip_records(buffer.getvalue())[0][0]


def patched_jar(baseline: bytes, compiled: bytes, manifest: bytes, patch: bytes) -> bytes:
    original, comment = zip_records(baseline)
    local = bytearray()
    central = bytearray()
    found = False
    records = []
    for info, local_record, central_record in original:
        if info.filename == CLASS:
            info, local_record, central_record = one_record(CLASS, compiled, info)
            found = True
        records.append((info, local_record, central_record))
    if not found:
        raise ValueError("Baseline has no ClassUtils")
    records.extend(
        [
            one_record("META-INF/varejo-commons-lang.json", manifest),
            one_record("META-INF/varejo-commons-lang-CVE-2025-48924.patch", patch),
        ]
    )
    for _, local_record, central_record in records:
        offset = len(local)
        local.extend(local_record)
        updated = bytearray(central_record)
        struct.pack_into("<I", updated, 42, offset)
        central.extend(updated)
    end = struct.pack(
        "<4s4H2IH",
        b"PK\x05\x06",
        0,
        0,
        len(records),
        len(records),
        len(central),
        len(local),
        len(comment),
    )
    return bytes(local + central + end + comment)


def check_jar(baseline: bytes, patched: bytes) -> dict[str, object]:
    before, before_comment = zip_records(baseline)
    after, after_comment = zip_records(patched)
    old = {info.filename: (local, central) for info, local, central in before}
    new = {info.filename: (local, central) for info, local, central in after}
    additions = set(new) - set(old)
    if additions != {
        "META-INF/varejo-commons-lang.json",
        "META-INF/varejo-commons-lang-CVE-2025-48924.patch",
    }:
        raise ValueError("Unexpected added archive members")
    if set(old) - set(new) or before_comment != after_comment:
        raise ValueError("Archive members or comment removed")
    for name in set(old) - {CLASS}:
        a_local, a_central = old[name]
        b_local, b_central = new[name]
        # ZIP offsets necessarily move after the changed class; every other byte stays.
        if a_local != b_local or a_central[:42] + a_central[46:] != b_central[:42] + b_central[46:]:
            raise ValueError(f"Unrelated member changed: {name}")
    with zipfile.ZipFile(io.BytesIO(patched)) as archive:
        if archive.testzip() is not None:
            raise ValueError("Invalid ZIP CRC")
        metadata = archive.read("META-INF/MANIFEST.MF")
        if b"2.6" not in metadata:
            raise ValueError("Upstream version metadata missing")
        for name in ("META-INF/LICENSE.txt", "META-INF/NOTICE.txt"):
            archive.read(name)
    return {
        "original_entries": len(old),
        "unchanged_entries": len(old) - 1,
        "changed_class": CLASS,
        "added_entries": sorted(additions),
        "raw_compressed_members_and_metadata_preserved": True,
        "upstream_manifest_license_notice_preserved": True,
    }


def xml_result(path: Path) -> dict[str, object]:
    suite = ET.parse(path).getroot()
    problems = []
    for case in suite.findall("testcase"):
        for kind in ("failure", "error"):
            item = case.find(kind)
            if item is not None:
                problems.append({"test": case.get("name"), "kind": kind, "type": item.get("type")})
    return {
        "tests": int(suite.get("tests", "0")),
        "failures": int(suite.get("failures", "0")),
        "errors": int(suite.get("errors", "0")),
        "skipped": int(suite.get("skipped", "0")),
        "problems": problems,
    }


def build(args: argparse.Namespace) -> None:
    lock = json.loads((VENDOR / "source-lock.json").read_text())
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    downloads = args.downloads.resolve()
    downloads.mkdir(parents=True, exist_ok=True)
    artifacts: dict[str, Path] = {}
    for name, item in lock["artifacts"].items():
        path = downloads / item["filename"]
        if not path.exists() and args.fetch:
            with urllib.request.urlopen(item["url"], timeout=60) as response:
                path.write_bytes(response.read())
        data = path.read_bytes()
        if sha(data) != item["sha256"] or len(data) != item["size_bytes"]:
            raise ValueError(f"Locked input mismatch: {name}")
        artifacts[name] = path
    if (VENDOR / "CVE-2025-48924.patch").read_bytes() != artifacts["patch"].read_bytes():
        raise ValueError("Vendored patch differs from locked upstream patch")
    javac = command(["javac", "-version"], cwd=output, log=output / "javac-version.log")
    java = command(["java", "-version"], cwd=output, log=output / "java-version.log")
    require(javac, "javac version")
    require(java, "java version")
    if (
        javac.stdout + javac.stderr
    ).strip() != "javac 17.0.20" or 'version "17.0.20"' not in java.stderr:
        raise ValueError("Expected the locked JDK 17.0.20 toolchain")
    toolchain = {
        "base_image": "python:3.11.16-alpine3.24@sha256:cd04730b8511def3fbf14204d66a0c1536f290b8e896ed5a94cd64cb15ac1356",
        "jdk_package": "openjdk17-jdk=17.0.20_p8-r0",
        "javac": (javac.stdout + javac.stderr).strip(),
        "java": java.stderr.strip(),
        "javac_binary_sha256": sha(Path(shutil.which("javac") or "").resolve().read_bytes()),
        "compiler_modules_sha256": sha(
            (Path(os.environ["JAVA_HOME"]) / "lib/modules").read_bytes()
        ),
        "release": 8,
    }
    for name, expected in lock["toolchain_sha256"].items():
        if toolchain[name] != expected:
            raise ValueError(f"Locked toolchain mismatch: {name}")
    baseline = artifacts["baseline"].read_bytes()
    with tempfile.TemporaryDirectory(prefix="commons-lang-backport-") as temporary:
        work = Path(temporary)
        source_dir = work / "source"
        source_dir.mkdir()
        source = extract(artifacts["source"], source_dir)
        result = command(
            ["patch", "--batch", "--fuzz=0", "-p1", "-i", str(artifacts["patch"])],
            cwd=source,
            log=output / "apply-patch.log",
        )
        require(result, "upstream patch")
        for name, expected in lock["patched_source_sha256"].items():
            if sha((source / name).read_bytes()) != expected:
                actual = (source / name).read_bytes()
                (output / ("mismatch-" + Path(name).name)).write_bytes(actual)
                raise ValueError(
                    f"Patched source mismatch: {name}; expected={expected}; actual={sha(actual)}"
                )
        classes = work / "classes"
        classes.mkdir()
        result = command(
            [
                "javac",
                "--release",
                "8",
                "-encoding",
                "UTF-8",
                "-g",
                "-cp",
                str(artifacts["baseline"]),
                "-d",
                str(classes),
                str(source / "src/main/java/org/apache/commons/lang/ClassUtils.java"),
            ],
            cwd=source,
            log=output / "compile-class.log",
        )
        require(result, "ClassUtils compilation")
        if [path.relative_to(classes).as_posix() for path in classes.rglob("*.class")] != [CLASS]:
            raise ValueError("Compilation changed more than the one intended class")
        compiled = (classes / CLASS).read_bytes()
        metadata = {
            "schema_version": 1,
            "patch_identity": lock["patch_identity"],
            "cve": lock["cve"],
            "upstream_version": "2.6",
            "upstream_tag": lock["upstream_tag"],
            "upstream_commit": lock["upstream_commit"],
            "upstream_patch_commit": lock["upstream_patch_commit"],
            "fixed_timestamp": FIXED_DATE,
            "artifacts": lock["artifacts"],
            "patched_source_sha256": lock["patched_source_sha256"],
            "class_sha256": sha(compiled),
            "toolchain": toolchain,
            "scope": "Official ClassUtils.getClass recursion fix only; all other upstream members retained byte-for-byte.",
        }
        jar = patched_jar(baseline, compiled, dump(metadata), artifacts["patch"].read_bytes())
        jar_path = output / "commons-lang-2.6-retail-classutils-v1.jar"
        jar_path.write_bytes(jar)
        preservation = check_jar(baseline, jar)
        for name, jar_input in (("baseline", artifacts["baseline"]), ("patched", jar_path)):
            result = command(
                [
                    "javap",
                    "-protected",
                    "-classpath",
                    str(jar_input),
                    "org.apache.commons.lang.ClassUtils",
                ],
                cwd=source,
                log=output / f"public-api-{name}.txt",
            )
            require(result, "public API listing")
        if (output / "public-api-baseline.txt").read_bytes() != (
            output / "public-api-patched.txt"
        ).read_bytes():
            raise ValueError("Public/protected API changed")
        tests = sorted((source / "src/test/java").rglob("*.java"))
        test_classes = work / "test-classes"
        test_classes.mkdir()
        classpath = os.pathsep.join([str(jar_path), str(artifacts["junit"])])
        argument_file = work / "test-sources.txt"
        argument_file.write_text("\n".join(str(path) for path in tests) + "\n")
        # The upstream enum package is legal Java 1.4, not Java 5+ source.
        # Compile it unchanged with pinned ECJ; only the harness needs Java 8 syntax.
        result = command(
            [
                "java",
                "-Xmx512m",
                "-jar",
                str(artifacts["test_compiler"]),
                "-source",
                "1.4",
                "-target",
                "1.4",
                "-proc:none",
                "-encoding",
                "UTF-8",
                "-g",
                "-cp",
                classpath,
                "-d",
                str(test_classes),
                "@" + str(argument_file),
            ],
            cwd=source,
            log=output / "compile-tests.log",
        )
        require(result, "upstream test compilation")
        result = command(
            [
                "javac",
                "--release",
                "8",
                "-encoding",
                "UTF-8",
                "-cp",
                classpath,
                "-d",
                str(test_classes),
                str(VENDOR / "UpstreamTestRunner.java"),
            ],
            cwd=source,
            log=output / "compile-test-harness.log",
        )
        require(result, "JUnit harness compilation")
        names = [
            path.relative_to(source / "src/test/java").with_suffix("").as_posix().replace("/", ".")
            for path in tests
            if path.name.endswith("Test.java") and path.name not in UPSTREAM_EXCLUDES
        ]
        names_path = work / "test-names.txt"
        names_path.write_text("\n".join(names) + "\n")
        results = {}
        for variant, jar_input in (("baseline", artifacts["baseline"]), ("patched", jar_path)):
            for mode in (
                ("regression", "classutils", "all")
                if args.upstream_suite
                else ("regression", "classutils")
            ):
                label = variant + "-" + mode
                result = command(
                    [
                        "java",
                        "-Xmx512m",
                        "-Xss1m",
                        "-Duser.language=en",
                        "-Duser.country=US",
                        "-Duser.timezone=UTC",
                        "-cp",
                        os.pathsep.join(
                            [str(test_classes), str(jar_input), str(artifacts["junit"])]
                        ),
                        "UpstreamTestRunner",
                        mode,
                        str(names_path),
                        str(output / (label + ".xml")),
                    ],
                    cwd=source,
                    log=output / (label + ".log"),
                    timeout=300,
                )
                results[label] = {
                    "exit_code": result.returncode,
                    **xml_result(output / (label + ".xml")),
                }
                print(label, json.dumps(results[label]), flush=True)
        baseline_regression = results["baseline-regression"]
        negative_control = (
            baseline_regression["exit_code"] == 1
            and baseline_regression["tests"] == 1
            and baseline_regression["failures"] == 0
            and baseline_regression["errors"] == 1
            and baseline_regression["problems"][0]["type"] == "java.lang.StackOverflowError"
        )
        clean_regression = (
            results["patched-regression"]["exit_code"] == 0
            and results["patched-regression"]["tests"] == 1
        )
        classutils_control = (
            results["baseline-classutils"]["tests"] == 44
            and results["baseline-classutils"]["exit_code"] == 1
            and results["baseline-classutils"]["problems"] == baseline_regression["problems"]
        )
        classutils_passes = (
            results["patched-classutils"]["tests"] == 44
            and results["patched-classutils"]["exit_code"] == 0
            and not results["patched-classutils"]["problems"]
        )

        def problem_key(problem):
            return problem["test"], problem["kind"], problem["type"]

        unchanged_failures = None
        if args.upstream_suite:
            unchanged_failures = sorted(
                [
                    p
                    for p in results["baseline-all"]["problems"]
                    if "testGetClassSOE(" not in p["test"]
                ],
                key=problem_key,
            ) == sorted(results["patched-all"]["problems"], key=problem_key)
        scoped_gates_pass = (
            negative_control and clean_regression and classutils_control and classutils_passes
        )
        full_suite_pass = args.upstream_suite and results["patched-all"]["exit_code"] == 0
        # Artifact identity is deterministic; runtime timings remain in the separate logs.
        report = {
            **metadata,
            "output_jar_sha256": sha(jar),
            "output_jar_bytes": len(jar),
            "preservation": preservation,
            "public_protected_api_unchanged": True,
            "upstream_test_source_files": len(tests),
            "upstream_discovered_test_classes": len(names),
            "upstream_test_compiler": "ECJ 3.33.0, source/target 1.4; test sources unchanged except official regression",
            "test_order": "Stable alphabetical order of existing JUnit suite children; original test methods and assertions unchanged",
            "upstream_pom_excludes_preserved": sorted(UPSTREAM_EXCLUDES),
            "tests": results,
            "official_regression_baseline_fails_as_expected": negative_control,
            "official_regression_backport_passes": clean_regression,
            "classutils_baseline_has_only_official_regression_failure": classutils_control,
            "classutils_all_44_cases_pass": classutils_passes,
            "upstream_baseline_failure_set_unchanged_except_fixed_regression": unchanged_failures,
            "validation_scope": "full-upstream-suite"
            if args.upstream_suite
            else "patched-class-and-official-regression",
            "upstream_full_suite_status": ("passed" if full_suite_pass else "failed")
            if args.upstream_suite
            else "not-run",
            "scoped_backport_gates_pass": scoped_gates_pass,
            "builder_source_sha256": sha(Path(__file__).read_bytes()),
            "test_harness_sha256": sha((VENDOR / "UpstreamTestRunner.java").read_bytes()),
            "source_lock_sha256": sha((VENDOR / "source-lock.json").read_bytes()),
            "status": (
                "full-upstream-suite-passed"
                if args.upstream_suite
                else "scoped-backport-gates-passed"
            )
            if scoped_gates_pass and (not args.upstream_suite or full_suite_pass)
            else "requires-review",
        }
        (output / "build-manifest.json").write_bytes(dump(report))
        print(
            json.dumps({"artifact": str(jar_path), "sha256": sha(jar), "status": report["status"]}),
            flush=True,
        )
        if report["status"] == "requires-review":
            raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--downloads", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--fetch",
        action="store_true",
        help="Fetch missing locked inputs; builds/tests can run offline with prefilled inputs",
    )
    parser.add_argument(
        "--upstream-suite",
        action="store_true",
        help="Also run all upstream cases; retain every failure and exit nonzero if any fail",
    )
    build(parser.parse_args())


if __name__ == "__main__":
    main()

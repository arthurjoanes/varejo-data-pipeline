"""Capture fixed published reports. Read-only domain state; no batch execution."""
from __future__ import annotations

import hashlib
import json
import time
from contextlib import ExitStack
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from retail_pipeline import publication, reporting
from retail_pipeline.profiling import load_profile
from retail_pipeline.report_view import build_report_html
from retail_pipeline.spark import create_spark

ROOT = Path('/data/evolution-demo')
OUT = Path('/app/artifacts')
OLD = Path('/evolution-evidence')
IMAGE = 'sha256:e54034991f90d5fc612bb0ae3b4c9369e439d2fbcc06c0cf96185e370615ccb8'
STATES = ('initial', 'comparable', 'incomparable')


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(root: Path, *, domain: bool) -> dict[str, str]:
    files = {}
    paths = list(root.rglob('*')) if domain else [
        path for directory in ('src', 'tests', 'scripts')
        for path in root.joinpath(directory).rglob('*')
    ] + list(root.glob('*'))
    for path in sorted(paths):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if domain:
            if rel.parts[0] in {'tmp', 'cache'} or path.name.endswith('.lock'):
                continue
        elif rel.parts[0] not in {'src', 'tests', 'scripts'}:
            if len(rel.parts) != 1 or path.name not in {
                'compose.yaml', 'Dockerfile', 'pyproject.toml', 'uv.lock',
                'requirements.txt', 'requirements-dev.txt', '.dockerignore',
            }:
                continue
        elif any(part in {'__pycache__', 'varejo_data_pipeline.egg-info'} for part in rel.parts):
            continue
        files[str(rel)] = digest(path)
    return files


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True,
                  default=publication.json_scalar, allow_nan=False)
        handle.write('\n')


def main() -> None:
    start = time.perf_counter()
    if not ROOT.joinpath('publication.json').is_file():
        raise RuntimeError('Own demo state is absent.')
    source_before = inventory(Path('/app'), domain=False)
    domain_before = inventory(ROOT, domain=True)
    write_json(OUT / 'source-capture-before.json', source_before)
    write_json(OUT / 'domain-capture-before.json', domain_before)
    manifests = {state: json.loads((OLD / f'{state}-publication.json').read_text(encoding='utf-8'))
                 for state in STATES}
    snapshots = {}
    for state, snapshot in manifests.items():
        stored = ROOT / 'publications' / f"{snapshot['publication_id']}.json"
        if json.loads(stored.read_text(encoding='utf-8')) != snapshot:
            raise RuntimeError(f'Immutable publication differs: {state}')
        profile = load_profile(snapshot)
        if profile['status'] != 'AVAILABLE':
            raise RuntimeError(f'Profile is unavailable: {state}')
        snapshots[state] = (snapshot, json.loads(
            (ROOT / 'runs' / snapshot['run_id'] / 'attempt.json').read_text(encoding='utf-8')))
    outputs = []
    spark = create_spark()
    try:
        for state, (snapshot, attempt) in snapshots.items():
            captured = []

            def capture_payload(payload, *, state=state, snapshot=snapshot, attempt=attempt):
                envelope = {
                    'captured_at': datetime.now(UTC).isoformat(),
                    'method': 'Fixed immutable publication and original attempt; Delta versionAsOf reads; no batch execution.',
                    'selection': 'Original run attempt retained in own historical demo state; publication pointer unchanged.',
                    'source_evidence': f'artifacts/evolucao-20261012-a12e4a/evolution-demo/{state}-publication.json',
                    'source_sha256': digest(OLD / f'{state}-publication.json'),
                    'attempt_sha256': digest(ROOT / 'runs' / snapshot['run_id'] / 'attempt.json'),
                    'profile_reference': snapshot['profile'],
                    'read_runtime': {'spark': spark.version, 'image': IMAGE},
                    'payload': asdict(payload),
                }
                write_json(OUT / 'inputs' / f'actual-{state}.json', envelope)
                captured.append(envelope)
                return build_report_html(payload)

            failed = attempt if attempt.get('state') in {'BLOCKED', 'TECHNICAL_FAILURE'} else None
            with ExitStack() as stack:
                stack.enter_context(patch.object(publication, 'load_snapshot', return_value=snapshot))
                stack.enter_context(patch.object(reporting, '_read_attempts', return_value=(attempt, failed)))
                stack.enter_context(patch.object(reporting, 'build_report_html', capture_payload))
                reporting.generate_report(spark, ROOT, OUT / 'before' / f'actual-{state}.html', synthetic_data=True)
            if len(captured) != 1:
                raise RuntimeError('Unexpected renderer calls.')
            payload = captured[0]['payload']
            outputs.append({
                'state': state,
                'publication_id': snapshot['publication_id'], 'run_id': snapshot['run_id'],
                'delta_versions': {name: ref['version'] for name, ref in snapshot['tables'].items()},
                'profile_status': payload['profile_result']['status'],
                'comparison_status': payload['profile_result']['profile']['comparison']['status'],
                'summary': payload['summary'],
                'payload_sha256': digest(OUT / 'inputs' / f'actual-{state}.json'),
                'html_sha256': digest(OUT / 'before' / f'actual-{state}.html'),
            })
            print(f'Captured {state}: {outputs[-1]["comparison_status"]}', flush=True)
    finally:
        spark.stop()
    source_after = inventory(Path('/app'), domain=False)
    domain_after = inventory(ROOT, domain=True)
    write_json(OUT / 'source-capture-after.json', source_after)
    write_json(OUT / 'domain-capture-after.json', domain_after)
    if source_after != source_before or domain_after != domain_before:
        raise RuntimeError('Source or durable domain inventory changed.')
    write_json(OUT / 'capture-result.json', {
        'passed': True, 'elapsed_seconds': time.perf_counter() - start,
        'image': IMAGE, 'source_files': len(source_before), 'domain_files': len(domain_before),
        'sources_unchanged': True, 'domain_unchanged': True, 'outputs': outputs,
        'script_sha256': digest(Path(__file__)), 'new_batch_executions': 0,
        'temporary_spark_files_excluded': True,
    })
    print('Capture passed; durable domain state and source files unchanged.', flush=True)


if __name__ == '__main__':
    main()

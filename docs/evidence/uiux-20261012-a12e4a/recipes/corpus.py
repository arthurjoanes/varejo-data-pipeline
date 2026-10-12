"""Replay identical immutable report inputs; presentation fixtures do not run Spark."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import sys
from decimal import Decimal, localcontext
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze_renderer():
    target = HERE / 'renderer-before' / 'retail_pipeline'
    source = PROJECT / 'src' / 'retail_pipeline'
    files = ['__init__.py', 'report_model.py', 'report_view.py', 'report_assets.py', 'report.css', 'report.js']
    target.mkdir(parents=True, exist_ok=True)
    for name in files:
        if not target.joinpath(name).exists():
            shutil.copyfile(source / name, target / name)
    if not target.joinpath('assets').exists():
        shutil.copytree(source / 'assets', target / 'assets')


def write_envelope(name, payload, *, source, kind, detail):
    path = HERE / 'inputs' / f'{name}.json'
    if path.exists():
        return
    envelope = {'method': kind, 'source_evidence': str(source.relative_to(PROJECT)),
                'source_sha256': sha(source), 'presentation_only': kind == 'presentation_fixture',
                'selection': detail, 'payload': payload}
    path.write_text(json.dumps(envelope, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def prepare_inputs():
    from retail_pipeline.profiling import ProfileParameters, compare_metrics, validate_profile

    for path in sorted((PROJECT / 'docs/evidence/interface/payloads').glob('*.json')):
        envelope = json.loads(path.read_text(encoding='utf-8'))
        write_envelope('historical-' + path.stem, envelope['payload'], source=path,
                       kind='historical_payload_replay', detail='Previously captured real Delta report payload; no new domain execution.')
    source = HERE / 'inputs' / 'actual-comparable.json'
    baseline = json.loads(source.read_text(encoding='utf-8'))['payload']

    def fixture(name, payload, detail):
        write_envelope('fixture-' + name, payload, source=source, kind='presentation_fixture', detail=detail)

    for state in ('MISSING', 'INVALID'):
        payload = copy.deepcopy(baseline)
        payload['profile_result'] = {'status': state, 'profile': None,
                                     'reason': 'Cenário de apresentação: perfil referenciado ausente.' if state == 'MISSING'
                                     else 'Cenário de apresentação: hash ou contrato do perfil inválido.'}
        fixture(state.lower(), payload, 'Published figures and immutable identifiers preserved; only profile reader outcome simulated.')
    payload = copy.deepcopy(baseline)
    payload['snapshot'].pop('profile')
    payload['profile_result'] = {'status': 'LEGACY', 'profile': None, 'reason': None}
    fixture('legacy', payload, 'Same captured published metrics, profile reference removed only for legacy presentation.')
    payload = {'synthetic_data': True, 'snapshot': None, 'latest_attempt': None,
               'profile_result': {'status': 'NO_PUBLICATION', 'profile': None, 'reason': None}}
    fixture('no-publication', payload, 'No publication; no figures or financial zero invented.')
    payload = copy.deepcopy(payload)
    payload['latest_attempt'] = {'state': 'RUNNING', 'run_id': 'fixture-running', 'batch_id': 'fixture-batch', 'stats': {}}
    fixture('running', payload, 'No publication; running attempt is a rendering fixture, not an ongoing execution.')
    payload = copy.deepcopy(baseline)
    payload['latest_attempt']['audit_incomplete'] = True
    fixture('audit', payload, 'Same published metrics; published attempt audit flag simulated without changing the publication.')

    payload = copy.deepcopy(baseline)
    payload['latest_attempt'] = {
        'state': 'BLOCKED', 'run_id': 'fixture-run-' + 'b' * 240,
        'batch_id': 'fixture-batch-' + 'a' * 240,
        'issues': [{'code': 'CAMPO_' + 'C' * 160, 'message': 'D' * 500, 'severity': 'BLOCKER'}],
        'coverage': {'expected': ['S01', 'S02', 'S03'], 'received': ['S01', 'S03'], 'missing': ['S02'], 'zero_movement': ['S03']},
        'stats': {'received': 4, 'valid': 3, 'rejected': 1},
    }
    payload['last_failed_attempt'] = copy.deepcopy(payload['latest_attempt'])
    fixture('long', payload, 'Long unbroken identifiers and issue strings only for responsive layout; published figures and profile preserved.')

    payload = copy.deepcopy(baseline)
    payload['snapshot'].pop('profile')
    payload['profile_result'] = {'status': 'LEGACY', 'profile': None, 'reason': None}
    payload['summary'].update(net_revenue_brl='2.76', average_ticket_brl='0.92', first_date='2026-01-01', last_date='2026-01-03')
    payload['stores'] = [
        {'business_date': '2026-01-01', 'store_id': 'S01', 'net_revenue_brl': '0.00'},
        {'business_date': '2026-01-03', 'store_id': 'S01', 'net_revenue_brl': None},
        {'business_date': '2026-01-01', 'store_id': 'S02', 'net_revenue_brl': '15.10'},
        {'business_date': '2026-01-03', 'store_id': 'S02', 'net_revenue_brl': '-12.34'},
    ]
    payload['daily'] = [
        {'business_date': '2026-01-01', 'net_revenue_brl': '15.10'},
        {'business_date': '2026-01-02', 'net_revenue_brl': None},
        {'business_date': '2026-01-03', 'net_revenue_brl': '-12.34'},
    ]
    payload['products'] = []
    fixture('matrix', payload, 'Signed amounts, explicit zero, null and absent date/store cells simulated solely for table/heatmap presentation.')

    payload = copy.deepcopy(baseline)
    payload['snapshot'].pop('profile')
    payload['profile_result'] = {'status': 'LEGACY', 'profile': None, 'reason': None}
    amount = '1234567890123.45'
    with localcontext() as context:
        context.prec = 60
        ticket = str(Decimal(amount) / Decimal(payload['summary']['sales_count']))
    payload['summary'].update(net_revenue_brl=amount, average_ticket_brl=ticket)
    payload['daily'] = [{'business_date': '2026-01-01', 'net_revenue_brl': amount}]
    payload['stores'] = [{**payload['stores'][0], 'net_revenue_brl': amount, 'average_ticket_brl': ticket,
                          'units': payload['summary']['units'], 'item_lines': payload['summary']['item_lines'],
                          'sales_count': payload['summary']['sales_count']}]
    payload['products'] = []
    fixture('large-money', payload, 'Exact Decimal 1234567890123.45 and ticket divided by three; financial presentation fixture, no domain run or profile recalculation.')

    payload = copy.deepcopy(baseline)
    payload['profile_result']['profile']['comparison']['rules'][0]['metric'] = 'fixture_unknown_metric_<&>_"_label'
    fixture('unknown-metric', payload, 'Unknown metric marker fixture_unknown_metric_<&>_"_label checks safe literal fallback. This deliberately unsupported presentation input does not satisfy the profile reader contract.')

    payload = copy.deepcopy(baseline)
    payload['summary'] = {}
    fixture('missing-metrics', payload, 'Published summary fields absent in presentation input; renderer must show absence distinctly from confirmed zero.')

    payload = copy.deepcopy(baseline)
    profile = payload['profile_result']['profile']
    params = ProfileParameters(min_active_lines=5)
    profile['parameters'] = params.document()
    equivalent = profile['comparison']['equivalent_totals']
    profile['comparison'].update(compare_metrics(equivalent['previous'], equivalent['current'], params))
    validate_profile(profile)
    fixture('insufficient-sample', payload, 'Captured totals unchanged; demonstrative minimum raised to five lines. Pure Decimal comparison, no Spark.')

    payload = copy.deepcopy(baseline)
    profile = payload['profile_result']['profile']
    previous = profile['comparison']['equivalent_totals']['previous']
    previous.update(gross_revenue_brl='0.00', net_revenue_brl='0.00', discount_brl='0.00')
    profile['comparison']['original_totals']['previous'] = copy.deepcopy(previous)
    profile['comparison'].update(compare_metrics(previous, profile['comparison']['equivalent_totals']['current']))
    validate_profile(profile)
    fixture('zero-baseline', payload, 'Earlier free-sale totals simulated solely to exercise undefined relative price variation; captured current figures unchanged.')

    payload = copy.deepcopy(baseline)
    zero = {'active_lines': 0, 'units': 0, 'sales': 0, 'gross_revenue_brl': '0.00', 'net_revenue_brl': '0.00', 'discount_brl': '0.00'}
    profile = payload['profile_result']['profile']
    profile['active_state']['totals'] = copy.deepcopy(zero)
    for value in profile['active_state']['distributions'].values():
        value.update(min=None, max=None, mean=None, quantiles=[])
    for value in profile['active_state']['groups'].values():
        value.update(values=[], group_count=0, truncated=False)
    profile['comparison']['original_totals'] = {'previous': copy.deepcopy(zero), 'current': copy.deepcopy(zero)}
    profile['comparison']['equivalent_totals'] = {'previous': copy.deepcopy(zero), 'current': copy.deepcopy(zero)}
    profile['comparison'].update(compare_metrics(zero, zero))
    payload['summary'] = {'net_revenue_brl': '0.00', 'units': 0, 'item_lines': 0, 'sales_count': 0,
                          'average_ticket_brl': None, 'first_date': None, 'last_date': None}
    payload.update(daily=[], stores=[], products=[])
    validate_profile(profile)
    fixture('confirmed-empty', payload, 'Confirmed empty active publication is a presentation fixture. Active financial totals are exact zeros; average ticket undefined.')


def render(phase):
    from retail_pipeline.report_model import ReportPayload
    from retail_pipeline.report_view import build_report_html

    output = HERE / phase
    output.mkdir(parents=True, exist_ok=True)
    records = []
    for path in sorted(HERE.joinpath('inputs').glob('*.json')):
        envelope = json.loads(path.read_text(encoding='utf-8'))
        payload = ReportPayload(**envelope['payload'])
        page = build_report_html(payload)
        if envelope.get('presentation_only'):
            page = page.replace('Demonstração com dados sintéticos.',
                                'Fixture de apresentação com dados sintéticos; nenhuma nova execução do pipeline.')
        target = output / f'{path.stem}.html'
        if phase == 'before' and target.exists() and target.read_text(encoding='utf-8') != page:
            raise RuntimeError(f'Frozen HTML differs for {path.name}')
        target.write_bytes(page.encode('utf-8'))
        records.append({'name': path.stem, 'input_sha256': sha(path), 'html_sha256': sha(target),
                        'presentation_only': bool(envelope.get('presentation_only')), 'method': envelope.get('method')})
    manifest = {'phase': phase, 'spark_started': False, 'new_batches': 0, 'inputs': records,
                'script_sha256': sha(Path(__file__)),
                'renderer': {str(path.relative_to(HERE / 'renderer-before')): sha(path)
                             for path in (HERE / 'renderer-before').rglob('*') if path.is_file() and '__pycache__' not in path.parts}
                if phase == 'before' else
                {str(path.relative_to(PROJECT / 'src')): sha(path) for path in (PROJECT / 'src/retail_pipeline').rglob('*')
                 if path.is_file() and (path.name.startswith('report') or path.parent.name == 'assets') and '__pycache__' not in path.parts}}
    (HERE / f'corpus-{phase}.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(f'{phase}: {len(records)} immutable inputs rendered offline.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', choices=['before', 'after'], default='before')
    parser.add_argument('--prepare', action='store_true')
    args = parser.parse_args()
    sys.path.insert(0, str(PROJECT / 'src'))
    if args.prepare:
        prepare_inputs()
    freeze_renderer()
    # Reload the package itself so importlib.resources uses the frozen asset
    # loader/spec as well as the frozen Python modules.
    for key in list(sys.modules):
        if key == 'retail_pipeline' or key.startswith('retail_pipeline.'):
            del sys.modules[key]
    if args.phase == 'before':
        sys.path.insert(0, str(HERE / 'renderer-before'))
    render(args.phase)

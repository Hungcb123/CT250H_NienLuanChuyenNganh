"""Track already inspected VNINDEX labels; no model fitting or market-data mutation."""
import hashlib
import json
from pathlib import Path

import pandas as pd


def exposure_from_report(path):
    path = Path(path)
    report = json.loads(path.read_text(encoding='utf-8'))
    if report.get('mode') != 'final_holdout':
        return []
    exposures = []
    for horizon, result in report.get('best_per_horizon', {}).items():
        holdout = result.get('holdout')
        if isinstance(holdout, dict) and 'final_label_end' in holdout:
            exposures.append({
                'report': str(path.resolve()), 'report_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                'horizon': int(horizon), 'start': holdout['start'],
                'labels_observed_through': holdout['final_label_end'],
            })
    return exposures


def observed_exposure(registry_path, reports_dir):
    registry_path = Path(registry_path)
    entries = []
    if registry_path.exists():
        registry = json.loads(registry_path.read_text(encoding='utf-8'))
        if registry.get('schema_version') != 1:
            raise ValueError(f'{registry_path}: unsupported exposure registry')
        entries.extend(registry['exposures'])
    for path in sorted(Path(reports_dir).glob('*/regime_v2_report.json')):
        entries.extend(exposure_from_report(path))
    latest = max((pd.Timestamp(e['labels_observed_through']) for e in entries), default=None)
    return {'latest_observed_label_date': str(latest.date()) if latest is not None else None,
            'exposures': entries,
            'rule': 'A new final holdout must begin strictly after every previously observed label-end date.'}


def assert_unseen_holdout(start, exposure):
    latest = exposure['latest_observed_label_date']
    if latest and pd.Timestamp(start) <= pd.Timestamp(latest):
        raise ValueError(f'Holdout labels through {latest} have already been inspected. '
                         'Use --development-only for further experiments; a new final holdout '
                         'must start after that date and have fully matured labels.')


def record_exposure(registry_path, report_path, horizon, start, label_end):
    """Persist consumed periods even when an output directory is outside default reports."""
    path = Path(registry_path)
    registry = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'schema_version': 1, 'exposures': []}
    if registry.get('schema_version') != 1:
        raise ValueError(f'{path}: unsupported exposure registry')
    registry['exposures'].append({'report': str(Path(report_path).resolve()), 'horizon': int(horizon),
                                  'start': str(pd.Timestamp(start).date()),
                                  'labels_observed_through': str(pd.Timestamp(label_end).date())})
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(registry, indent=2), encoding='utf-8')
    temporary.replace(path)

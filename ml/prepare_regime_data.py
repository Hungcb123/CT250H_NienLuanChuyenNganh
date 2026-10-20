"""Download a separate VNINDEX research snapshot and cross-check broker closes.

No training, interpolation, silent source fallback, or overwrite of ml/data/raw. Broker chart
endpoints are public interfaces and may change; failures are explicit in manifest.json.
"""
import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
VCI_URL = 'https://trading.vietcap.com.vn/api/chart/OHLCChart/gap-chart'
KBS_URL = 'https://kbbuddywts.kbsec.com.vn/iis-server/investment'
VND_URL = 'https://dchart-api.vndirect.com.vn/dchart/history'
COLUMN_MAP = {'t': 'Date', 'o': 'Open', 'h': 'High', 'l': 'Low', 'c': 'Close', 'v': 'Volume'}


def normalize_response(payload, provider, symbol, start, end):
    """Keep provider prices as reported. Convert only daily timestamp representation."""
    if provider == 'kbs':
        if payload.get('symbol') != symbol or 'data_day' not in payload:
            raise ValueError(f'KBS: missing daily data or wrong symbol {symbol}')
        frame = pd.DataFrame(payload['data_day'])
    else:
        item = payload
        if provider == 'vci':
            if not isinstance(payload, list) or len(payload) != 1 or payload[0].get('symbol') != symbol:
                raise ValueError(f'VCI: expected one response for {symbol}')
            item = payload[0]
        if not isinstance(item, dict) or not all(k in item for k in COLUMN_MAP):
            raise ValueError(f'{provider}: missing OHLCV arrays')
        frame = pd.DataFrame({k: item[k] for k in COLUMN_MAP})
    if frame.empty or not all(k in frame for k in COLUMN_MAP):
        raise ValueError(f'{provider} {symbol}: empty or malformed OHLCV')
    frame = frame[list(COLUMN_MAP)].rename(columns=COLUMN_MAP)
    if provider == 'kbs':
        frame['Date'] = pd.to_datetime(frame['Date'], errors='raise').dt.normalize()
    else:
        timestamps = pd.to_numeric(frame['Date'], errors='raise')
        unit = 'ms' if timestamps.max() > 1e12 else 's'
        frame['Date'] = (pd.to_datetime(timestamps, unit=unit, utc=True).dt.tz_convert('Asia/Ho_Chi_Minh')
                         .dt.tz_localize(None).dt.normalize())
    if frame['Date'].isna().any() or frame['Date'].duplicated().any():
        raise ValueError(f'{provider} {symbol}: null or duplicate daily dates')
    frame = frame.loc[frame['Date'].between(pd.Timestamp(start), pd.Timestamp(end))].sort_values('Date').reset_index(drop=True)
    if frame.empty or (frame['Date'].dt.dayofweek >= 5).any():
        raise ValueError(f'{provider} {symbol}: empty date range or weekend observations')
    for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
        frame[col] = pd.to_numeric(frame[col], errors='raise')
        if not np.isfinite(frame[col]).all() or (frame[col] < 0).any() or (col != 'Volume' and (frame[col] == 0).any()):
            raise ValueError(f'{provider} {symbol}: invalid {col}')
    return frame


def download_broker(provider, symbol, start, end, sources_dir, timeout=25):
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    params = None
    body = None
    if provider == 'vci':
        # Estimate a generous number of bars; this is NOT used as an exchange calendar.
        count_back = int((end - start).days * 5 / 7) + 366
        body = {'timeFrame': 'ONE_DAY', 'symbols': [symbol],
                'to': int((end + pd.Timedelta(days=1)).tz_localize('Asia/Ho_Chi_Minh').timestamp()),
                'countBack': count_back}
        url = VCI_URL
    elif provider == 'kbs':
        group = 'index' if symbol == 'VNINDEX' else 'stocks'
        params = {'sdate': start.strftime('%d-%m-%Y'), 'edate': end.strftime('%d-%m-%Y')}
        url = f'{KBS_URL}/{group}/{symbol}/data_day'
    elif provider == 'vnd' and symbol == 'VNINDEX':
        params = {'resolution': 'D', 'symbol': symbol,
                  'from': int(start.tz_localize('Asia/Ho_Chi_Minh').timestamp()),
                  'to': int((end + pd.Timedelta(days=1)).tz_localize('Asia/Ho_Chi_Minh').timestamp())}
        url = VND_URL
    else:
        raise ValueError(f'Unsupported source {provider}/{symbol}')
    request_url = url + ('?' + urllib.parse.urlencode(params) if params else '')
    request = urllib.request.Request(request_url, data=json.dumps(body).encode() if body else None,
                                     headers={'User-Agent': 'Mozilla/5.0', 'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
    name = f'{provider}_{symbol}'
    raw_path = sources_dir / f'{name}.json'
    raw_path.write_bytes(raw)
    frame = normalize_response(json.loads(raw), provider, symbol, start, end)
    frame.to_csv(sources_dir / f'{name}.csv', index=False)
    bad_bounds = ((frame['High'] < frame[['Open', 'Close', 'Low']].max(axis=1)) |
                  (frame['Low'] > frame[['Open', 'Close', 'High']].min(axis=1)))
    metadata = {'provider': provider, 'symbol': symbol, 'url': url, 'params': params, 'body': body,
                'downloaded_at': datetime.now(timezone.utc).isoformat(), 'response': f'sources/{raw_path.name}',
                'response_sha256': hashlib.sha256(raw).hexdigest(), 'rows': len(frame),
                'start': str(frame['Date'].min().date()), 'end': str(frame['Date'].max().date()),
                'ohlc_bounds_conflicts': int(bad_bounds.sum()), 'zero_volume_rows': int((frame['Volume'] == 0).sum()),
                'price_basis': 'provider_reported_close; adjustment methodology not independently verified'}
    return frame, metadata


def compare_sources(primary, secondary, tolerance=0.011):
    joined = primary.set_index('Date').join(secondary.set_index('Date'), how='inner', lsuffix='_primary', rsuffix='_secondary')
    differences = (joined['Close_primary'] - joined['Close_secondary']).abs()
    mismatch = differences > tolerance
    return {
        'overlap_rows': len(joined), 'matching_close_rows': int((~mismatch).sum()),
        'close_tolerance': tolerance, 'close_conflicts': [
            {'date': str(date.date()), 'primary': float(row.Close_primary), 'secondary': float(row.Close_secondary)}
            for date, row in joined.loc[mismatch].iterrows()],
        'max_close_difference': float(differences.max()) if len(joined) else None,
        'primary_dates_missing_in_secondary': int((~primary['Date'].isin(secondary['Date'])).sum()),
        'secondary_dates_missing_in_primary': int((~secondary['Date'].isin(primary['Date'])).sum()),
        'other_field_mismatch_counts': {
            col: int(((joined[col + '_primary'] - joined[col + '_secondary']).abs() > tolerance).sum())
            for col in ['Open', 'High', 'Low', 'Volume'] if col in primary and col in secondary},
    }


def reconcile_index(frames, review):
    """Resolve Close conflicts with explicit votes/citations and preserve session positions."""
    if review.get('schema_version') != 1:
        raise ValueError('Unsupported source review schema')
    primary = frames['vci_VNINDEX'].set_index('Date').copy()
    providers = {key.split('_')[0]: frame.set_index('Date') for key, frame in frames.items()
                 if key.endswith('_VNINDEX')}
    exclusions = review['nontrading_dates']
    review_closes = review['reviewed_closes']
    decisions, unresolved = [], []
    for date in primary.index:
        day = str(date.date())
        votes = {name: float(frame.loc[date, 'Close']) for name, frame in providers.items() if date in frame.index}
        if day in exclusions:
            decisions.append({'Date': day, 'decision': 'excluded_nontrading_session', **votes,
                              'source': exclusions[day]['source']})
            continue
        if primary.loc[date, 'Volume'] <= 0:
            unresolved.append(f'{day}: unreviewed zero-volume index bar')
            continue
        selected = votes['vci']
        decision = 'single_source' if len(votes) == 1 else 'broker_agreement'
        cited_source = None
        if day in review_closes:
            selected = float(review_closes[day]['close'])
            if not any(abs(value - selected) <= .011 for value in votes.values()):
                unresolved.append(f'{day}: reviewed Close is unsupported by downloaded brokers')
                continue
            decision, cited_source = 'cited_daily_report', review_closes[day]['source']
        elif max(votes.values()) - min(votes.values()) > .011:
            clusters = {tuple(sorted(name for name, price in votes.items() if abs(price - value) <= .011))
                        for value in votes.values()}
            best = max(len(group) for group in clusters)
            winners = [group for group in clusters if len(group) == best]
            if best < 2 or len(winners) != 1:
                unresolved.append(f'{day}: unresolved broker Close conflict {votes}')
                continue
            agreeing = winners[0]
            selected = votes['vci'] if 'vci' in agreeing else votes[agreeing[0]]
            decision = 'broker_majority'
        primary.loc[date, 'Close'] = selected
        decisions.append({'Date': day, **votes, 'selected_close': selected, 'decision': decision,
                          'changed_primary': abs(selected - votes['vci']) > .011, 'source': cited_source})
    for name, secondary in providers.items():
        if name == 'vci':
            continue
        extra_dates = secondary.index.difference(primary.index)
        extra_dates = [str(day.date()) for day in extra_dates if str(day.date()) not in exclusions]
        if extra_dates:
            unresolved.append(f'{name}: dates outside primary calendar require review: {extra_dates}')
    if unresolved:
        raise ValueError('; '.join(unresolved))
    primary = primary.loc[~primary.index.isin(pd.to_datetime(list(exclusions)))].reset_index()
    return primary, decisions


def load_saved_broker(snapshot, provider, symbol, start, end, sources_dir):
    snapshot = Path(snapshot)
    manifest = json.loads((snapshot / 'manifest.json').read_text(encoding='utf-8'))
    if pd.Timestamp(start) < pd.Timestamp(manifest['requested_start']) or pd.Timestamp(end) > pd.Timestamp(manifest['requested_end']):
        raise ValueError('Saved snapshot cannot expand the original requested range')
    evidence = dict(manifest['sources'][f'{provider}_{symbol}'])
    raw_path = snapshot / evidence['response']
    raw = raw_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != evidence['response_sha256']:
        raise ValueError(f'{raw_path}: saved response hash mismatch')
    frame = normalize_response(json.loads(raw), provider, symbol, start, end)
    name = f'{provider}_{symbol}'
    (sources_dir / f'{name}.json').write_bytes(raw)
    frame.to_csv(sources_dir / f'{name}.csv', index=False)
    evidence.update(replayed_from=str(raw_path.resolve()), rows=len(frame),
                    start=str(frame['Date'].min().date()), end=str(frame['Date'].max().date()))
    return frame, evidence


def write_canonical(path, frame, symbol, sources, comparisons, excluded_dates=None, reconciliation=None):
    columns = ['Date', 'Close'] + (['Volume'] if symbol != 'VNINDEX' else [])
    canonical = frame.loc[~frame['Date'].isin(pd.to_datetime(excluded_dates or [])), columns].copy()
    canonical.to_csv(path, index=False)
    provenance = {'schema_version': 1, 'symbol': symbol, 'asset_type': 'index' if symbol == 'VNINDEX' else 'etf',
                  'csv_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                  'primary_provider': 'vci', 'sources': sources, 'comparisons': comparisons,
                  'excluded_source_conflict_dates': excluded_dates or [],
                  'normalization': 'daily date conversion, requested-range filtering, and recorded source reconciliation; no price filling',
                  'reconciliation': reconciliation,
                  'columns': columns, 'source_provenance': 'saved_broker_responses_with_partial_cross_source_close_checks',
                  'adjustment_status': 'price_index_points' if symbol == 'VNINDEX' else 'provider_reported_etf_price_adjustments_unverified',
                  'calendar_status': 'broker_index_session_dates_crosschecked_on_overlap; not an official exchange calendar'}
    path.with_suffix('.provenance.json').write_text(json.dumps(provenance, indent=2), encoding='utf-8')
    return provenance


def prepare_snapshot(start, end, output_dir, local_dir=ROOT / 'data' / 'raw', source_snapshot=None):
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    today = pd.Timestamp(datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).date())
    if start > end or end >= today:
        raise ValueError('Require start <= end and end before today (completed sessions only)')
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    sources_dir = output_dir / 'sources'
    sources_dir.mkdir()
    manifest = {'requested_start': str(start.date()), 'requested_end': str(end.date()),
                'sources': {}, 'source_errors': {}, 'comparisons': {}, 'canonical': {}}
    frames = {}
    for symbol, providers in [('VNINDEX', ['vci', 'kbs', 'vnd']), ('E1VFVN30', ['vci', 'kbs'])]:
        for provider in providers:
            key = f'{provider}_{symbol}'
            try:
                if source_snapshot:
                    frame, evidence = load_saved_broker(source_snapshot, provider, symbol, start, end, sources_dir)
                else:
                    frame, evidence = download_broker(provider, symbol, start, end, sources_dir)
                frames[key] = frame
                manifest['sources'][key] = evidence
                print(f"{key}: {len(frame)} rows ({evidence['start']} -> {evidence['end']})", flush=True)
            except Exception as exc:
                manifest['source_errors'][key] = str(exc)
                print(f'{key}: ERROR {exc}', flush=True)
    errors = []
    for symbol in ['VNINDEX', 'E1VFVN30']:
        primary = frames.get(f'vci_{symbol}')
        if primary is None:
            errors.append(f'Missing VCI primary for {symbol}; no fallback data substituted')
            continue
        checks = {}
        conflict_dates = set()
        for provider in ['kbs', 'vnd']:
            secondary = frames.get(f'{provider}_{symbol}')
            if secondary is not None:
                checks[provider] = compare_sources(primary, secondary)
                conflict_dates.update(row['date'] for row in checks[provider]['close_conflicts'])
        local_path = Path(local_dir) / f'{symbol}.csv'
        if local_path.exists():
            local = pd.read_csv(local_path, parse_dates=['Date'])
            local = local.loc[local['Date'].between(start, end)]
            checks['existing_local_csv'] = compare_sources(primary, local)
            checks['existing_local_csv']['sha256'] = hashlib.sha256(local_path.read_bytes()).hexdigest()
        manifest['comparisons'][symbol] = checks
        if not any(c['overlap_rows'] >= 100 for key, c in checks.items() if key != 'existing_local_csv'):
            errors.append(f'{symbol}: require >=100 common observations from a second broker')
            continue
        reconciliation = None
        if symbol == 'VNINDEX':
            if primary['Date'].min() > start + pd.Timedelta(days=14):
                errors.append('VNINDEX primary has insufficient requested historical coverage')
                continue
            review_path = ROOT / 'vnindex_source_review.json'
            review = json.loads(review_path.read_text(encoding='utf-8'))
            try:
                primary, decisions = reconcile_index(frames, review)
            except ValueError as exc:
                errors.append(str(exc))
                continue
            pd.DataFrame(decisions).to_csv(output_dir / 'index_source_decisions.csv', index=False)
            reconciliation = {'review': review, 'review_sha256': hashlib.sha256(review_path.read_bytes()).hexdigest(),
                              'decision_file': 'index_source_decisions.csv',
                              'changed_primary_closes': sum(bool(d.get('changed_primary')) for d in decisions),
                              'single_source_sessions': sum(d['decision'] == 'single_source' for d in decisions),
                              'removed_nontrading_dates': [d['Date'] for d in decisions if d['decision'] == 'excluded_nontrading_session']}
            conflict_dates = set()  # All conflicts were resolved or reconciliation raised above.
        # Conservative ETF exclusion: keep the full index calendar and leave disagreement dates unobserved.
        canonical = write_canonical(output_dir / f'{symbol}.csv', primary, symbol,
                                    {key: value for key, value in manifest['sources'].items() if value['symbol'] == symbol},
                                    checks, sorted(conflict_dates), reconciliation)
        manifest['canonical'][symbol] = {'rows': len(primary) - len(conflict_dates),
                                         'sha256': canonical['csv_sha256'], 'excluded_conflict_dates': sorted(conflict_dates)}
    manifest['errors'] = errors
    (output_dir / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    if errors:
        raise ValueError('Snapshot incomplete; see manifest.json. ' + '; '.join(errors))
    print(f'Snapshot ready: {output_dir.resolve()}. Original CSVs and models were not changed.')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start', default='2010-01-01')
    parser.add_argument('--end', default=str((datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).date() - timedelta(days=1))))
    parser.add_argument('--output-dir', type=Path, required=True, help='New directory; must not already exist')
    parser.add_argument('--local-dir', type=Path, default=ROOT / 'data' / 'raw')
    parser.add_argument('--from-snapshot', type=Path, help='Replay saved, hash-checked broker responses instead of downloading')
    args = parser.parse_args()
    prepare_snapshot(args.start, args.end, args.output_dir, args.local_dir, args.from_snapshot)


if __name__ == '__main__':
    main()

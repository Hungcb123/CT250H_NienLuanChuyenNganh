"""Append-only live inputs. Frozen research datasets and feature code stay untouched.

DNSE supplies VNINDEX OHLCV/ETF/VN30. Supplemental group indices use VND when
DNSE has no symbol; unavailable optional fields stay missing as in training.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time, timedelta
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

TZ = ZoneInfo('Asia/Ho_Chi_Minh')
ROOT = Path(__file__).resolve().parent
DNSE = 'https://services.entrade.com.vn/chart-api/v2'
CBOE = 'https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv'
SOURCE_POLICY = 'dnse-append-close-v1'


def completed_session(now=None):
    now = (now or datetime.now(TZ)).astimezone(TZ)
    session = now.date()
    if now.time() < time(15, 30):
        session -= timedelta(days=1)
    while session.weekday() >= 5:
        session -= timedelta(days=1)
    return session


def download(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 EquiFolio/1.0', 'Accept': '*/*'})
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read()


def dnse_bars(symbol, start, end, fetch=download):
    kind = 'stock' if symbol == 'E1VFVN30' else 'index'
    params = dict(symbol=symbol, resolution='1D', **{
        'from': int(datetime.combine(start, time.min, TZ).timestamp()),
        'to': int(datetime.combine(end + timedelta(days=1), time.min, TZ).timestamp())})
    url = DNSE + '/ohlcs/' + kind + '?' + urllib.parse.urlencode(params)
    raw = fetch(url)
    payload = json.loads(raw)
    keys = dict(t='Date', o='Open', h='High', l='Low', c='Close', v='Volume')
    if not isinstance(payload, dict) or any(not isinstance(payload.get(k), list) for k in keys):
        raise ValueError('INVALID_DNSE_RESPONSE:' + symbol)
    lengths = {len(payload[k]) for k in keys}
    if len(lengths) != 1 or not payload['t']:
        raise ValueError('EMPTY_DNSE_RESPONSE:' + symbol)
    frame = pd.DataFrame({name: payload[key] for key, name in keys.items()})
    frame['Date'] = pd.to_datetime(pd.to_numeric(frame.Date), unit='s', utc=True).dt.tz_convert(TZ).dt.tz_localize(None).dt.normalize()
    # Stock chart prices are in thousand VND; index levels are points.
    for name in ['Open', 'High', 'Low', 'Close', 'Volume']:
        frame[name] = pd.to_numeric(frame[name], errors='raise')
    if symbol == 'E1VFVN30':
        frame[['Open', 'High', 'Low', 'Close']] *= 1000
    frame = frame.loc[frame.Date.between(pd.Timestamp(start), pd.Timestamp(end))].sort_values('Date').reset_index(drop=True)
    if frame.empty or frame.Date.duplicated().any() or (frame.Date.dt.weekday >= 5).any():
        raise ValueError('INVALID_DNSE_CALENDAR:' + symbol)
    values = frame[['Open', 'High', 'Low', 'Close', 'Volume']].to_numpy()
    if not np.isfinite(values).all() or (values[:, :4] <= 0).any() or (values[:, 4] < 0).any():
        raise ValueError('INVALID_DNSE_VALUES:' + symbol)
    if ((frame.High < frame[['Open', 'Close', 'Low']].max(axis=1)) |
            (frame.Low > frame[['Open', 'Close', 'High']].min(axis=1))).any():
        raise ValueError('INVALID_DNSE_OHLC:' + symbol)
    return frame, dict(provider='DNSE', url=url, sha256=hashlib.sha256(raw).hexdigest())


def append_frame(base, incoming, columns=None):
    """No overwrites or filling; reject revisions in the requested overlap."""
    base = base.copy()
    incoming = incoming.copy()
    base['Date'] = pd.to_datetime(base.Date)
    incoming['Date'] = pd.to_datetime(incoming.Date)
    if base.Date.duplicated().any() or incoming.Date.duplicated().any():
        raise ValueError('DUPLICATE_SOURCE_SESSION')
    fields = columns or ['Close']
    overlap = base.merge(incoming, on='Date', suffixes=('_old', '_new'))
    for field in fields:
        if not np.allclose(overlap[field + '_old'], overlap[field + '_new'], rtol=0, atol=.011, equal_nan=True):
            raise ValueError('HISTORICAL_REVISION:' + field)
    extension = incoming.loc[incoming.Date > base.Date.max()]
    return pd.concat([base, extension], ignore_index=True).sort_values('Date').reset_index(drop=True)


class LiveDataStore:
    def __init__(self, seed_dir, directory, fetch=download):
        self.seed_dir, self.directory, self.fetch = Path(seed_dir), Path(directory), fetch
        self.directory.mkdir(parents=True, exist_ok=True)

    def latest(self):
        pointer = self.directory / 'latest.json'
        if not pointer.exists():
            return None
        name = json.loads(pointer.read_text())['snapshot']
        path = (self.directory / name).resolve()
        if path.parent != self.directory.resolve() or not path.is_dir():
            raise ValueError('INVALID_LIVE_SNAPSHOT')
        manifest = json.loads((path / 'manifest.json').read_text())
        for filename, digest in manifest['files'].items():
            target = (path / filename).resolve()
            if target.parent != path or hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                raise ValueError('LIVE_SNAPSHOT_CHECKSUM_MISMATCH')
        return path

    def sync(self, expected):
        previous = self.latest()
        source = previous or self.seed_dir
        base = pd.read_csv(source / 'VNINDEX.csv', parse_dates=['Date'])
        etf = pd.read_csv(source / 'E1VFVN30.csv', parse_dates=['Date'])
        if base.Date.max().date() > expected:
            raise ValueError('LIVE_DATA_AHEAD_OF_COMPLETED_SESSION')
        if previous and base.Date.max().date() == expected:
            return previous
        # Recheck the last accepted bar and fetch only its suffix, in bounded chunks.
        # Overlap is checked only for previously accepted DNSE rows; the research
        # prefix is an immutable separate source, not assumed to have DNSE vintages.
        start = base.Date.max().date() if previous else base.Date.max().date() + timedelta(days=1)
        if start > expected:
            start = expected
        def series(symbol, begin):
            pieces, receipts = [], []
            while begin <= expected:
                end = min(expected, begin + timedelta(days=90))
                bars, receipt = dnse_bars(symbol, begin, end, self.fetch)
                pieces.append(bars); receipts.append(receipt)
                begin = end + timedelta(days=1)
            return pd.concat(pieces, ignore_index=True), receipts
        etf_start = etf.Date.max().date() if previous else etf.Date.max().date() + timedelta(days=1)
        with ThreadPoolExecutor(max_workers=2) as pool:
            index_job = pool.submit(series, 'VNINDEX', start)
            etf_job = pool.submit(series, 'E1VFVN30', min(etf_start, expected))
            bars, index_receipts = index_job.result()
            etf_bars, etf_receipts = etf_job.result()
        if bars.Date.max().date() != expected or etf_bars.Date.max().date() != expected:
            raise ValueError('STALE_OR_INCOMPLETE_SESSION')
        new_dates = bars.loc[bars.Date > base.Date.max(), 'Date']
        if not set(new_dates).issubset(set(etf_bars.Date)):
            raise ValueError('ETF_SESSION_MISSING')
        # DNSE's observed VNINDEX sessions are the calendar reference. Do not
        # synthesize missing weekdays (which may be exchange holidays).
        updated_index = append_frame(base, bars[['Date', 'Close']])
        updated_etf = append_frame(etf, etf_bars[['Date', 'Close', 'Volume']])
        old_bars = pd.read_csv(previous / 'VNINDEX_OHLCV.csv', parse_dates=['Date']) if previous else bars.iloc[:0].copy()
        if old_bars.empty:
            all_bars = bars
        else:
            all_bars = append_frame(old_bars, bars, ['Open', 'High', 'Low', 'Close', 'Volume'])
        receipts = dict(VNINDEX=index_receipts, E1VFVN30=etf_receipts)
        groups = {}
        for symbol in ['VN30', 'VNMID', 'VNSML']:
            initial = source / (symbol + '.csv') if previous else ROOT / 'data/research/market_indices_20261001_v3' / (symbol + '.csv')
            history = pd.read_csv(initial, parse_dates=['Date'])
            begin = history.Date.max().date() + timedelta(days=1)
            try:
                if begin <= expected:
                    if symbol == 'VN30':
                        extra, receipt = series(symbol, begin)
                        receipt = dict(provider='DNSE', requests=receipt)
                    else:
                        import prepare_regime_data as providers
                        from prepare_regime_indices import close_response
                        params = dict(resolution='D', symbol=symbol, **{
                            'from': int(datetime.combine(begin, time.min, TZ).timestamp()),
                            'to': int(datetime.combine(expected + timedelta(days=1), time.min, TZ).timestamp())})
                        url = providers.VND_URL + '?' + urllib.parse.urlencode(params)
                        raw = self.fetch(url)
                        extra = close_response(json.loads(raw), 'vnd', symbol, begin, expected)
                        receipt = dict(provider='VND', url=url, sha256=hashlib.sha256(raw).hexdigest())
                    history = append_frame(history, extra[['Date', 'Close']])
                    receipts[symbol] = receipt
            except Exception as error:
                # These features were trained with native missing-value handling.
                # Preserve missingness, never substitute VN30/ETF for other groups.
                receipts[symbol] = dict(status='OPTIONAL_SOURCE_UNAVAILABLE', error=type(error).__name__)
            groups[symbol] = history
        vix_path = source / 'VIX.csv' if previous else ROOT / 'data/research/global_risk/sources/VIX_History.csv'
        vix = pd.read_csv(vix_path)
        vix['Date'] = pd.to_datetime(vix.DATE, format='%m/%d/%Y')
        try:
            raw = self.fetch(CBOE)
            incoming = pd.read_csv(io.BytesIO(raw))
            incoming['Date'] = pd.to_datetime(incoming.DATE, format='%m/%d/%Y')
            incoming['Close'] = pd.to_numeric(incoming.CLOSE)
            if incoming.Date.duplicated().any() or not np.isfinite(incoming.Close).all() or (incoming.Close <= 0).any():
                raise ValueError('INVALID_VIX')
            # Keep frozen history; append official Cboe observations only.
            vix['Close'] = pd.to_numeric(vix.CLOSE)
            vix = append_frame(vix, incoming.loc[incoming.Date > vix.Date.max()], ['Close'])
            receipts['VIX'] = dict(provider='CBOE', url=CBOE, sha256=hashlib.sha256(raw).hexdigest())
        except Exception as error:
            receipts['VIX'] = dict(status='OPTIONAL_SOURCE_UNAVAILABLE', error=type(error).__name__)
        name = datetime.now(TZ).strftime('snapshot-%Y%m%dT%H%M%S-%f')
        stage = self.directory / ('.' + name)
        stage.mkdir()
        try:
            updated_index.to_csv(stage / 'VNINDEX.csv', index=False)
            updated_etf.to_csv(stage / 'E1VFVN30.csv', index=False)
            all_bars.to_csv(stage / 'VNINDEX_OHLCV.csv', index=False)
            for symbol, history in groups.items():
                history.to_csv(stage / (symbol + '.csv'), index=False)
            vix.drop(columns=['Date', 'Close'], errors='ignore').to_csv(stage / 'VIX.csv', index=False)
            manifest = dict(policy=SOURCE_POLICY, session=expected.isoformat(), sources=receipts,
                            files={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in stage.glob('*.csv')})
            (stage / 'manifest.json').write_text(json.dumps(manifest, indent=2))
            published = self.directory / name
            os.replace(stage, published)
            pending = self.directory / '.latest.json.tmp'
            pending.write_text(json.dumps(dict(snapshot=name)))
            os.replace(pending, self.directory / 'latest.json')
            return published
        finally:
            if stage.exists():
                shutil.rmtree(stage)


def live_completed_features(snapshot, seed_dir):
    """Same feature equations as the locked builder; live sources have their own policy."""
    import experiment_regime as exp
    import experiment_regime_information as information
    from experiment_regime_directional import directional_features
    snapshot, seed_dir = Path(snapshot), Path(seed_dir)
    index, index_audit = exp.base.load_market_data(snapshot / 'VNINDEX.csv')
    etf, etf_audit = exp.base.load_market_data(snapshot / 'E1VFVN30.csv')
    frame, _ = exp.base.build_feature_matrix(index, etf, 'close-etf')
    for name, value in exp.long_features(index).items():
        frame[name] = value
    seed_index, _ = exp.base.load_market_data(seed_dir / 'VNINDEX.csv')
    consensus, _ = information.ohlcv.load_consensus(seed_dir, seed_index)
    live = pd.read_csv(snapshot / 'VNINDEX_OHLCV.csv', parse_dates=['Date'])
    live = live.loc[live.Date > seed_index.Date.max()].rename(columns={'Close': 'Price'})
    consensus = pd.concat([consensus, live], ignore_index=True)
    bars = information.ohlcv.ohlcv_features(consensus)
    vix = pd.read_csv(snapshot / 'VIX.csv')
    vix['VIX_ObservationDate'] = pd.to_datetime(vix.DATE, format='%m/%d/%Y')
    vix_fields = information.global_risk.vix_features(vix, index.Date)
    stretch = information.extra.reversal_features(index).Stretch20
    vix_fields['VIX_StretchInteraction'] = stretch * (vix_fields.VIX_LogLevel - np.log(20.))
    groups = {symbol: pd.read_csv(snapshot / (symbol + '.csv'), parse_dates=['Date']) for symbol in ['VN30', 'VNMID', 'VNSML']}
    for book in [bars, vix_fields, information.indices.index_features(index, groups), directional_features(index)]:
        if (set(frame) & set(book)) - {'Date'}:
            raise ValueError('LIVE_FEATURE_COLLISION')
        frame = frame.merge(book, on='Date', how='left', validate='one_to_one', sort=False)
    frame['horizon_sigma'] = np.log(index.Price.astype(float)).diff().rolling(20, min_periods=20).std(ddof=1) * np.sqrt(20)
    np.testing.assert_array_equal(frame.Date, index.Date)
    return frame, dict(index=index_audit, etf=etf_audit, source_policy=SOURCE_POLICY)

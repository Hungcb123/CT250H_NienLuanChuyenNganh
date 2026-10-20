from datetime import datetime, date
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from urllib.parse import urlparse, parse_qs
from zoneinfo import ZoneInfo

import pandas as pd

from regime_live_data import completed_session, dnse_bars, append_frame, LiveDataStore, TZ


def payload(symbol, days):
    prices = [20.0 if symbol == 'E1VFVN30' else 100.0 + i for i, _ in enumerate(days)]
    return json.dumps(dict(t=[int(datetime.combine(d, datetime.min.time(), TZ).timestamp()) for d in days],
                           o=prices, h=[x + 1 for x in prices], l=[x - 1 for x in prices], c=prices,
                           v=[1000] * len(days))).encode()


class LiveDataTests(unittest.TestCase):
    def test_only_completed_weekday_session_is_selected(self):
        for text, expected in [('2026-10-19T14:00:00', '2026-10-16'),
                               ('2026-10-19T15:30:00', '2026-10-19'),
                               ('2026-10-17T18:00:00', '2026-10-16'),
                               ('2026-10-18T09:00:00', '2026-10-16')]:
            self.assertEqual(str(completed_session(datetime.fromisoformat(text).replace(tzinfo=TZ))), expected)

    def test_index_points_and_stock_thousand_vnd_are_distinct(self):
        day = date(2026, 10, 2)
        for symbol, expected in [('VNINDEX', 100), ('E1VFVN30', 20000)]:
            frame, _ = dnse_bars(symbol, day, day, lambda _: payload(symbol, [day]))
            self.assertEqual(frame.Close.iloc[0], expected)

    def test_malformed_ohlcv_rejected_and_intraday_future_filtered(self):
        day = date(2026, 10, 2)
        raw = json.loads(payload('VNINDEX', [day])); raw['h'] = []
        with self.assertRaises(ValueError):
            dnse_bars('VNINDEX', day, day, lambda _: json.dumps(raw).encode())
        raw = json.loads(payload('VNINDEX', [day])); raw['h'] = [1]
        with self.assertRaises(ValueError):
            dnse_bars('VNINDEX', day, day, lambda _: json.dumps(raw).encode())
        frame, _ = dnse_bars('VNINDEX', day, day, lambda _: payload('VNINDEX', [day, date(2026, 10, 5)]))
        self.assertEqual(len(frame), 1)

    def test_revision_rejected_without_modifying_original(self):
        original = pd.DataFrame(dict(Date=pd.to_datetime(['2026-10-01']), Close=[100.]))
        incoming = pd.DataFrame(dict(Date=pd.to_datetime(['2026-10-01', '2026-10-02']), Close=[90., 101.]))
        with self.assertRaisesRegex(ValueError, 'HISTORICAL_REVISION'):
            append_frame(original, incoming)
        self.assertEqual(original.Close.iloc[0], 100)

    def test_incremental_restart_no_duplicates_and_failure_keeps_previous_snapshot(self):
        with tempfile.TemporaryDirectory() as temp:
            seed, live = Path(temp) / 'seed', Path(temp) / 'live'; seed.mkdir()
            (seed / 'VNINDEX.csv').write_text('Date,Close\n2026-10-01,99\n')
            (seed / 'E1VFVN30.csv').write_text('Date,Close,Volume\n2026-10-01,19000,1000\n')
            calls = []
            def fetch(url):
                calls.append(url)
                if '/chart-api/' not in url:
                    raise OSError('optional source unavailable')
                query = parse_qs(urlparse(url).query)
                symbol = query['symbol'][0]
                return payload(symbol, [date(2026, 10, 2)])
            store = LiveDataStore(seed, live, fetch)
            first = store.sync(date(2026, 10, 2))
            self.assertEqual(len(pd.read_csv(first / 'VNINDEX.csv')), 2)
            count = len(calls)
            restarted = LiveDataStore(seed, live, fetch)
            self.assertEqual(restarted.sync(date(2026, 10, 2)), first)
            self.assertEqual(len(calls), count)
            failing = LiveDataStore(seed, live, Mock(side_effect=OSError('network down')))
            with self.assertRaises(OSError): failing.sync(date(2026, 10, 5))
            self.assertEqual(failing.latest(), first)
            self.assertEqual((seed / 'VNINDEX.csv').read_text(), 'Date,Close\n2026-10-01,99\n')
            (first / 'VNINDEX.csv').write_text('corrupted')
            with self.assertRaisesRegex(ValueError, 'CHECKSUM'):
                restarted.latest()


if __name__ == '__main__': unittest.main()

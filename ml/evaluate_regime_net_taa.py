"""Fixed VNINDEX/cash policy proxy; no model/threshold selection or deployment.

Decision after close t; rebalance at close t+1; earn return t+1 -> t+2.
Compare SAA35%, winner-score proxy, its55% gate, and net-score policy.
Includes weight drift and proportional traded-notional cost. Cash return=0.
This is not the full STOCK/GOLD/SAVINGS portfolio nor an executable index trade.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent


def simulate_net_taa(prices, scores_by_date, first, last, policy, anchor=.35, delta_max=.15, cost=.002):
    if policy not in ['saa', 'winner_score_proxy', 'winner_gate55_proxy', 'net_score']:
        raise ValueError('Unsupported policy')
    if not 0 <= anchor <= 1 or not 0 <= delta_max <= 1 or not 0 <= cost < 1:
        raise ValueError('Invalid portfolio constants')
    nav = 1.; pre_weight = anchor; records = []
    for decision in range(first, last+1):
        execute, realize = decision+1, decision+2
        if realize >= len(prices):
            raise ValueError('Incomplete delayed execution outcome')
        day = pd.Timestamp(prices.Date.iloc[decision])
        scores = scores_by_date.get(day)
        target = anchor
        if scores is not None:
            scores = np.asarray(scores, dtype=float)
            if scores.shape != (3,) or not np.isfinite(scores).all() or (scores < 0).any() or not np.isclose(scores.sum(), 1.):
                raise ValueError('Invalid decision scores')
            if policy == 'net_score':
                target += delta_max*(scores[2]-scores[0])
            elif policy.startswith('winner'):
                if policy != 'winner_gate55_proxy' or scores.max() >= .55:
                    target += delta_max*(int(scores.argmax())-1)*scores.max()
        target = float(np.clip(target, 0, 1))
        # Solve target weight AFTER transaction cost, including prior drift.
        change = target-pre_weight
        trade = change/(1+cost*target) if change >= 0 else change/(1-cost*target)
        turnover = abs(trade)
        expense = cost*turnover
        stock_return = prices.Close.iloc[realize]/prices.Close.iloc[execute]-1
        gross_growth = 1+target*stock_return
        growth = (1-expense)*gross_growth
        nav *= growth
        pre_weight = target*(1+stock_return)/gross_growth
        records.append(dict(decision_date=str(day.date()), execution_date=str(prices.Date.iloc[execute].date()),
                            outcome_date=str(prices.Date.iloc[realize].date()), target=target,
                            stock_return=float(stock_return), net_return=float(growth-1), equity=float(nav),
                            turnover=float(turnover), cost_fraction=float(expense), has_forecast=scores is not None))
    rows = pd.DataFrame(records)
    returns = rows.net_return.to_numpy()
    curve = np.r_[1., rows.equity.to_numpy()]
    drawdown = curve/np.maximum.accumulate(curve)-1
    sd = returns.std(ddof=1) if len(returns) > 1 else 0.
    metrics = dict(policy=policy, sessions=len(rows), total_return=float(nav-1),
                   annualized_return=float(nav**(252/len(rows))-1),
                   sharpe_zero_rf=float(np.sqrt(252)*returns.mean()/sd) if sd > 0 else None,
                   max_drawdown=float(drawdown.min()), annualized_turnover=float(rows.turnover.sum()*252/len(rows)),
                   mean_stock_weight=float(rows.target.mean()), cost_fraction_sum=float(rows.cost_fraction.sum()))
    return rows, metrics


def evaluate_net_taa():
    source = ROOT/'reports/regime_shock_native/20261019T090304_754869Z/native_predictions.csv'
    data = ROOT/'data/research/brokers_2010_20261001_reviewed/VNINDEX.csv'
    rows = pd.read_csv(source, parse_dates=['Date'])
    prices = pd.read_csv(data, parse_dates=['Date'])
    calendar = pd.DatetimeIndex(prices.Date)
    output = ROOT/'reports/regime_net_taa'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True, exist_ok=False)
    plan = dict(role='Historical inspected VNINDEX/cash policy PROXY only',
                source_hashes={str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__), source, data]},
                constants=dict(anchor=.35, delta_max=.15, traded_notional_cost=.002, cash_return=0, execution_delay_sessions=1),
                timing='Decision at close t; next close rebalance; next interval return. Full raw calendar; missing forecast ->SAA. Reset capital/holdings per fold.',
                caveats=['Reviewed index Close is not an executable stock/ETF price.', 'No gold, savings interest, dividends or exact Vietnamese tax model.',
                         'Winner proxies use the SAME ensemble scores, not actual legacy ONNX predictions.',
                         'Daily rebalance assumption; includes drift/cost, no turnover-minimization gate.',
                         'History repeatedly inspected; no independent acceptance or automatic TAA enablement.'],
                point_predictions_unchanged=True, deployed=False)
    (output/'plan.json').write_text(json.dumps(plan, indent=2)+'\n')
    metrics = []
    for fold, part in rows.groupby('outer_fold'):
        score_map = {r.Date: np.array([r.p_bear, r.p_side, r.p_bull]) for r in part.itertuples()}
        positions = calendar.get_indexer(part.Date)
        if (positions < 0).any():
            raise ValueError('Forecast outside calendar')
        for policy in ['saa', 'winner_score_proxy', 'winner_gate55_proxy', 'net_score']:
            predictions, result = simulate_net_taa(prices, score_map, int(positions[0]), int(positions[-1]), policy)
            predictions.to_csv(output/f'fold{fold}_{policy}.csv', index=False)
            metrics.append(dict(fold=int(fold), **result))
    pd.DataFrame(metrics).to_csv(output/'comparison.csv', index=False)
    report = dict(role=plan['role'], results=metrics, point_predictions_unchanged=True, independent_test=False, accepted=False, deployed=False)
    (output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(str(output)); print(pd.DataFrame(metrics).to_string(index=False))
    return output


if __name__ == '__main__':
    evaluate_net_taa()

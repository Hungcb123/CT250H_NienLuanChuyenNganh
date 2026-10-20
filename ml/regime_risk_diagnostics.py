"""Read-only diagnostics and causal threshold helpers for regime risk research."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import average_precision_score, roc_auc_score

WINDOWS = (60, 120)
FIXED_PARAMS = dict(n_estimators=150, learning_rate=.03, max_depth=3, num_leaves=7,
                    min_child_samples=50, colsample_bytree=.7, reg_alpha=.1, reg_lambda=1.,
                    class_weight='balanced', random_state=42, n_jobs=2, verbosity=-1)


def score_stats(values, prefix):
    values = np.asarray(values, dtype=float)
    return {prefix + '_n': len(values), prefix + '_mean': float(np.mean(values)),
            prefix + '_p90': float(np.quantile(values, .9, method='higher')),
            prefix + '_std': float(np.std(values))}


def rolling_thresholds(history_dates, history_scores, decision_dates, windows=WINDOWS):
    """Current-model scores only. Never use the current or later date in a threshold.

    History is an OUT-OF-FIT chronological feature cohort, rescored by one model.
    Windows count eligible observations; gaps are retained, not filled. Any
    insufficient history fails instead of silently shrinking the window.
    """
    dates = pd.DatetimeIndex(history_dates)
    decisions = pd.DatetimeIndex(decision_dates)
    scores = np.asarray(history_scores, dtype=float)
    if not dates.is_monotonic_increasing or dates.has_duplicates or len(dates) != len(scores):
        raise ValueError('Need unique sorted history dates and aligned scores')
    if not np.isfinite(scores).all():
        raise ValueError('Nonfinite score history')
    positions = dates.searchsorted(decisions, side='left')
    result = {}
    for window in windows:
        if (positions < window).any():
            raise ValueError(f'Need {window} strictly earlier out-of-fit feature observations')
        result[f'rolling_{window}_threshold'] = np.array([
            np.quantile(scores[pos-window:pos], .9, method='higher') for pos in positions])
    return result


def fold_diagnostics(records):
    rows = []
    for (policy, fold), group in records.groupby(['policy', 'outer_fold']):
        y, score = group.common_bear.astype(int), group.risk_score
        both = y.nunique() == 2
        loss = -group.future_return  # Higher loss = worse forward return.
        ic = float(spearmanr(score, loss).statistic) if score.nunique() > 1 and loss.nunique() > 1 else None
        rows.append(dict(policy=policy, outer_fold=int(fold), n=len(group), base_rate=float(y.mean()),
                         fold_ap=float(average_precision_score(y, score)) if both else None,
                         fold_auroc=float(roc_auc_score(y, score)) if both else None,
                         spearman_score_vs_forward_loss=ic,
                         **score_stats(score, 'prediction_score')))
    return pd.DataFrame(rows)


def event_runs(records, calendar):
    """Consecutive positive decision-day runs, NOT independent economic crashes."""
    output = []
    calendar = pd.DatetimeIndex(calendar)
    for (policy, fold), group in records.groupby(['policy', 'outer_fold']):
        positive = group.loc[group.common_bear].sort_values('Date')
        positions = calendar.get_indexer(positive.Date)
        if (positions < 0).any():
            raise ValueError('Prediction date missing from market calendar')
        runs = np.cumsum(np.r_[True, np.diff(positions) != 1]) if len(positions) else []
        for run_id, run in positive.groupby(runs):
            output.append(dict(policy=policy, outer_fold=int(fold), run=int(run_id),
                               first_decision=str(run.Date.min().date()), last_decision=str(run.Date.max().date()),
                               n_positive_days=len(run), n_static_alarm_hits=int(run.alarm.sum()),
                               minimum_forward_return=float(run.future_return.min())))
    return pd.DataFrame(output)


def write_diagnostics(records, refits, index, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    fold_diagnostics(records).to_csv(output / 'fold_diagnostics.csv', index=False)
    drift = []
    for audit in refits:
        group = records.loc[(records.policy == audit['policy']) & (records.outer_fold == audit['outer_fold']) &
                            (records.refit_block == audit['refit_block'])]
        drift.append({**audit, **score_stats(group.risk_score, 'prediction_score')})
    # Legacy reports did not save calibration score distributions. Do not invent them.
    pd.DataFrame(drift).to_csv(output / 'refit_drift.csv', index=False)
    event_runs(records, index.Date).to_csv(output / 'positive_day_runs.csv', index=False)
    selected = records.loc[(records.outer_fold == 3) & records.common_bear].copy()
    selected['static_false_negative'] = ~selected.alarm
    selected.to_csv(output / 'fold3_positive_days.csv', index=False)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    policies = list(records.policy.unique())
    fig, axes = plt.subplots(len(policies), 1, figsize=(14, 4 * len(policies)), squeeze=False)
    fold_dates = records.loc[records.outer_fold == 3, 'Date']
    if len(fold_dates):
        price = index.loc[index.Date.between(fold_dates.min() - pd.Timedelta(days=60),
                                             fold_dates.max() + pd.Timedelta(days=45))]
        for ax, policy in zip(axes[:, 0], policies):
            ax.plot(price.Date, price.Price, color='gray', linewidth=1, label='VNINDEX close')
            points = selected.loc[selected.policy == policy].merge(index[['Date', 'Price']], on='Date', validate='one_to_one')
            for missed, color, marker, label in [(True, 'red', 'x', 'Positive day missed by static threshold'),
                                                 (False, 'green', 'o', 'Positive day caught by static threshold')]:
                subset = points.loc[points.static_false_negative == missed]
                ax.scatter(subset.Date, subset.Price, c=color, marker=marker, s=35, label=label)
            ax.set_title(policy + ': fold 3; overlapping T+20 positive decision days')
            ax.legend()
    fig.tight_layout()
    fig.savefig(output / 'fold3_price_diagnostics.png', dpi=150)
    plt.close(fig)
    note = ['# Risk diagnostics', '',
            'Spearman IC correlates risk score with NEGATIVE forward simple return (higher = larger loss).',
            'AP below base rate is a warning on these samples, not proof of feature inversion or a causal explanation.',
            'Positive-day runs group consecutive index decision dates; they are not independent crash events.',
            'fold3_positive_days.csv includes ALL positive days and flags actual static-threshold false negatives.',
            'Legacy refit reports have no calibration mean/std; those values cannot be recovered from p90 alone.',
            'Price plots describe outcomes; they do not establish exhaustion, macro news or SHAP explanations.']
    (output / 'diagnostics.md').write_text('\n'.join(note) + '\n', encoding='utf-8')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--risk-dir', type=Path, required=True)
    parser.add_argument('--data-dir', type=Path, default=Path(__file__).resolve().parent / 'data/research/brokers_2010_20261001_reviewed')
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args(argv)
    import train_regime_v2 as base
    plan = json.loads((args.risk_dir / 'risk_plan.json').read_text())
    index, audit = base.load_market_data(args.data_dir / 'VNINDEX.csv')
    if audit['sha256'] != plan['input_hashes']['VNINDEX']:
        raise ValueError('Market snapshot differs from study input hash')
    records, refits = [], []
    for path in sorted(args.risk_dir.glob('*_predictions.csv')):
        group = pd.read_csv(path, parse_dates=['Date', 'label_end_date'])
        records.append(group)
        for audit in json.loads((args.risk_dir / path.name.replace('_predictions.csv', '_refits.json')).read_text()):
            refits.append(dict(policy=group.policy.iloc[0], **audit))
    output = args.output_dir or args.risk_dir / 'diagnostics'
    output.mkdir(parents=True, exist_ok=False)
    write_diagnostics(pd.concat(records, ignore_index=True), refits, index, output)
    print(f'Diagnostics only; no model fitted. Output: {output.resolve()}')


if __name__ == '__main__':
    main()

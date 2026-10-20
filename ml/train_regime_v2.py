"""Causal VNINDEX regime research: raw-calendar labels and a purged holdout.

Run from the repository root. Use --audit-only first; see ml/REGIME_V2.md.
Fixed present-day VN30 constituents are deliberately excluded. Features use
close(t); predictions are available AFTER that close, not before it.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score,
                             matthews_corrcoef, precision_recall_fscore_support)
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler

from research_protocol import assert_unseen_holdout, observed_exposure, record_exposure

HORIZONS = {
    20: {'name': 'T+20', 'bull_threshold': 0.05, 'bear_threshold': -0.05},
    60: {'name': 'T+60', 'bull_threshold': 0.10, 'bear_threshold': -0.10},
    120: {'name': 'T+120', 'bull_threshold': 0.15, 'bear_threshold': -0.15},
}
MODEL_NAMES = ['LogisticRegression', 'RandomForest', 'LightGBM', 'XGBoost', 'CatBoost']
OPTUNA_N_TRIALS = 60
OPTUNA_TIMEOUT = 300
N_SPLITS = 4
DATA_DIR = Path(__file__).parent / 'data' / 'raw'
REPORT_DIR = Path(__file__).parent / 'reports'
EXPOSURE_REGISTRY = Path(__file__).parent / 'holdout_exposure.json'
LABEL_NAMES = ['Bearish (-1)', 'Sideway (0)', 'Bullish (+1)']
ETF_FEATURE_NAMES = ['ETF_ROC20', 'ETF_HV20', 'ETF_Corr30_VNINDEX', 'ETF_ReturnSpread20']
FEATURE_VERSIONS = {'close': 'close-v3-research', 'close-etf': 'close-etf-v3-research'}


def _ema(values: np.ndarray, period: int) -> np.ndarray:
    """Exponential Moving Average."""
    out = [values[0]]
    alpha = 2.0 / (period + 1)
    for x in values[1:]:
        out.append(out[-1] + (x - out[-1]) * alpha)
    return np.array(out)


def close_features_v1(closes: np.ndarray) -> np.ndarray:
    """
    Original 12 close-only features (close-v1), matching Java CloseFeatures.
    Input: at least 60 (ideally 120) most recent close prices.
    """
    p = np.asarray(closes[-120:], dtype=float)
    if len(p) < 60 or not np.isfinite(p).all() or (p <= 0).any():
        return np.full(12, np.nan, dtype=np.float32)

    # RSI(14)
    change = np.diff(p)[-14:]
    gain = np.maximum(change, 0).mean()
    loss = np.maximum(-change, 0).mean()
    if gain == 0 and loss == 0:
        rsi = 50.0
    elif loss == 0:
        rsi = 100.0
    else:
        rsi = 100.0 - 100.0 / (1.0 + gain / loss)

    # MACD
    macd = (_ema(p, 12) - _ema(p, 26)) / p * 100
    signal = _ema(macd, 9)[-1]
    macd_val = macd[-1]
    macd_hist = macd_val - signal

    # Bollinger Bands
    s20 = p[-20:].mean()
    std20 = p[-20:].std(ddof=0)
    bb_width = 4 * std20 / s20 if s20 != 0 else 0
    bb_pctb = 0.5 if std20 == 0 else (p[-1] - (s20 - 2 * std20)) / (4 * std20)

    # SMA ratios
    s50 = p[-50:].mean()
    sma_ratio = s20 / s50 if s50 != 0 else 1.0
    dist_sma20 = p[-1] / s20 - 1 if s20 != 0 else 0
    dist_sma50 = p[-1] / s50 - 1 if s50 != 0 else 0

    # Other momentum
    abs_change_14 = np.abs(change).mean() / p[-1] * 100 if p[-1] != 0 else 0
    roc_20 = (p[-1] / p[-21] - 1) * 100 if len(p) >= 21 else 0
    log_returns = np.diff(np.log(p))[-20:]
    hv_20 = log_returns.std(ddof=1) * np.sqrt(252) * 100 if len(log_returns) > 1 else 0

    return np.array([
        rsi, macd_val, signal, macd_hist, bb_width, bb_pctb,
        sma_ratio, dist_sma20, dist_sma50, abs_change_14, roc_20, hv_20
    ], dtype=np.float32)


# Names for the 12 close-v1 features
CLOSE_V1_NAMES = [
    'RSI_14', 'MACD', 'MACD_Signal', 'MACD_Hist', 'BB_Width', 'BB_PctB',
    'SMA_20_50_Ratio', 'Dist_SMA20', 'Dist_SMA50', 'Abs_Change_14_Pct', 'ROC_20', 'HV_20'
]

def load_market_data(path: Path, *, today=None):
    """Validate, audit and sort a daily CSV without inventing observations.

    Adj Close is preferred when supplied. Raw Close otherwise remains explicitly
    unverified for corporate-action adjustments; CSV structure cannot prove provenance.
    """
    path = Path(path)
    df = pd.read_csv(path)
    if not {'Date', 'Close'}.issubset(df.columns) or df.empty:
        raise ValueError(f'{path}: need nonempty Date and Close columns')
    df['Date'] = pd.to_datetime(df['Date'], errors='raise')
    if df['Date'].isna().any() or df['Date'].dt.tz is not None:
        raise ValueError(f'{path}: dates must be non-null, timezone-free daily dates')
    if not df['Date'].eq(df['Date'].dt.normalize()).all():
        raise ValueError(f'{path}: intraday timestamps are not daily session dates')
    if df['Date'].duplicated().any():
        raise ValueError(f'{path}: duplicate session dates; resolve at source')
    if (df['Date'].dt.dayofweek >= 5).any():
        raise ValueError(f'{path}: weekend observations in a Vietnam daily series')
    cutoff = pd.Timestamp(today or datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).date())
    if df['Date'].max() > cutoff:
        raise ValueError(f'{path}: future market data')
    ordered = bool(df['Date'].is_monotonic_increasing)
    df = df.sort_values('Date').reset_index(drop=True)
    for col in ['Close', 'Adj Close', 'Open', 'High', 'Low', 'Volume']:
        if col not in df:
            continue
        df[col] = pd.to_numeric(df[col], errors='raise')
        if not np.isfinite(df[col]).all():
            raise ValueError(f'{path}: non-finite {col}')
        if (df[col] < 0).any() or (col != 'Volume' and (df[col] == 0).any()):
            raise ValueError(f'{path}: invalid {col}')
    if {'Open', 'High', 'Low'}.issubset(df.columns):
        if ((df['High'] < df[['Open', 'Close', 'Low']].max(axis=1)) |
                (df['Low'] > df[['Open', 'Close', 'High']].min(axis=1))).any():
            raise ValueError(f'{path}: inconsistent OHLC bounds')
    price_column = 'Adj Close' if 'Adj Close' in df else 'Close'
    df['Price'] = df[price_column]
    changes = df['Price'].pct_change(fill_method=None)
    jumps = changes.abs() > 0.15  # audit flag, never automatically winsorized
    gaps = df['Date'].diff().dt.days
    audit = {
        'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'rows': len(df), 'start': str(df['Date'].min().date()),
        'end': str(df['Date'].max().date()), 'input_was_sorted': ordered,
        'price_column': price_column,
        'adjustment_status': 'provided_adj_close_not_independently_verified' if price_column == 'Adj Close'
                             else 'raw_close_adjustments_unverified',
        'source_provenance': 'not_independently_verified',
        'zero_volume_rows': int((df['Volume'] == 0).sum()) if 'Volume' in df else None,
        'large_return_flags': [
            {'date': str(d.date()), 'return': float(r)}
            for d, r in zip(df.loc[jumps, 'Date'], changes[jumps])],
        'calendar_gaps_over_7_days': [str(x.date()) for x in df.loc[gaps > 7, 'Date']],
    }
    provenance_path = path.with_suffix('.provenance.json')
    if provenance_path.exists():
        provenance = json.loads(provenance_path.read_text(encoding='utf-8'))
        if provenance.get('schema_version') != 1 or provenance.get('csv_sha256') != audit['sha256']:
            raise ValueError(f'{path}: provenance hash/schema does not match CSV; rebuild snapshot')
        audit['provenance'] = provenance
        audit['source_provenance'] = provenance['source_provenance']
        audit['adjustment_status'] = provenance['adjustment_status']
    return df, audit


def audit_calendar(vnindex_df, etf_df=None, calendar_path=None):
    """Optionally validate index dates against an independently supplied exchange calendar."""
    dates = pd.DatetimeIndex(vnindex_df['Date'])
    result = {'reference': 'VNINDEX CSV dates', 'exchange_calendar_verified': False}
    if calendar_path:
        raw = pd.read_csv(calendar_path)
        official = pd.DatetimeIndex(pd.to_datetime(raw['Date'], errors='raise'))
        if official.hasnans or official.has_duplicates or not official.equals(official.normalize()):
            raise ValueError('Exchange calendar must contain unique non-null daily Date values')
        # Require coverage for the entire index history, not just overlapping dates.
        if official.min() > dates.min() or official.max() < dates.max():
            raise ValueError('Exchange calendar does not cover the full VNINDEX date range')
        official = official[(official >= dates.min()) & (official <= dates.max())]
        if len(dates.difference(official)) or len(official.difference(dates)):
            raise ValueError('VNINDEX dates disagree with exchange calendar; repair CSV before training')
        result.update(exchange_calendar_verified=True, reference=str(calendar_path),
                      calendar_sha256=hashlib.sha256(Path(calendar_path).read_bytes()).hexdigest())
    if etf_df is not None:
        etf_dates = pd.DatetimeIndex(etf_df['Date'])
        in_range = etf_dates[(etf_dates >= dates.min()) & (etf_dates <= dates.max())]
        overlap = dates[(dates >= etf_dates.min()) & (dates <= etf_dates.max())]
        result['etf_dates_outside_index_calendar'] = [str(d.date()) for d in in_range.difference(dates)]
        result['index_dates_missing_etf'] = [str(d.date()) for d in overlap.difference(etf_dates)]
    return result


def compute_etf_features(vnindex_df, etf_df):
    """Same-session rolling returns; no fill or constant-correlation fallback.

    Zero-volume ETF bars are unobserved prices. Missing observations invalidate
    the relevant rolling window instead of compressing its trading calendar.
    """
    dates = pd.DatetimeIndex(vnindex_df['Date'])
    observations = etf_df.set_index('Date')['Price'].copy()
    if 'Volume' in etf_df:
        observations.loc[etf_df.set_index('Date')['Volume'] <= 0] = np.nan
    etf = observations.reindex(dates)
    index = pd.Series(vnindex_df['Price'].to_numpy(dtype=float), index=dates)
    etf_returns = np.log(etf).diff()
    index_returns = np.log(index).diff()
    # ROC20 and its spread require every intermediate session to be observed too.
    complete21 = etf.notna().rolling(21, min_periods=21).sum().eq(21)
    roc20 = (etf / etf.shift(20) - 1).where(complete21)
    correlation = etf_returns.rolling(30, min_periods=30).corr(index_returns)
    result = pd.DataFrame({
        'ETF_ROC20': roc20 * 100,
        'ETF_HV20': etf_returns.rolling(20, min_periods=20).std(ddof=1) * np.sqrt(252) * 100,
        'ETF_Corr30_VNINDEX': correlation,
        'ETF_ReturnSpread20': (roc20 - (index / index.shift(20) - 1)) * 100,
    })
    result.index = vnindex_df.index
    return result.replace([np.inf, -np.inf], np.nan)


def build_feature_matrix(vnindex_df, etf_df=None, feature_set='close'):
    """Preserve every index session; filtering occurs only AFTER raw-calendar labels."""
    closes = vnindex_df['Price'].to_numpy(dtype=float)
    rows = [close_features_v1(closes[max(0, i-119):i+1]) for i in range(len(closes))]
    names = CLOSE_V1_NAMES.copy()
    frame = pd.concat([vnindex_df[['Date', 'Price']].reset_index(drop=True),
                       pd.DataFrame(rows, columns=names)], axis=1)
    if feature_set == 'close-etf':
        if etf_df is None:
            raise ValueError('close-etf requires E1VFVN30.csv')
        frame = pd.concat([frame, compute_etf_features(vnindex_df, etf_df)], axis=1)
        names += ETF_FEATURE_NAMES
    elif feature_set != 'close':
        raise ValueError(f'Unknown feature set: {feature_set}')
    return frame, names


def create_labels(feature_df, horizon, feature_names=None):
    """Shift on the COMPLETE index calendar, then remove invalid feature/label rows."""
    cfg = HORIZONS[horizon]
    df = feature_df.copy()
    future = df['Price'].shift(-horizon) / df['Price'] - 1
    df['label_end_date'] = df['Date'].shift(-horizon)
    df['future_return'] = future
    df['label'] = np.where(future < cfg['bear_threshold'], 0,
                           np.where(future > cfg['bull_threshold'], 2, 1))
    names = feature_names if feature_names is not None else CLOSE_V1_NAMES
    valid = np.isfinite(df[names].to_numpy(dtype=float)).all(axis=1) & future.notna()
    return df.loc[valid].reset_index(drop=True)


def partition_holdout(frame, holdout_start):
    """Keep only development labels strictly known before the first holdout close."""
    boundary = pd.Timestamp(holdout_start)
    before = frame['Date'] < boundary
    known = frame['label_end_date'] < boundary
    development = frame.loc[before & known].reset_index(drop=True)
    holdout = frame.loc[~before].reset_index(drop=True)
    if development.empty or holdout.empty:
        raise ValueError('No development or holdout rows; check coverage and holdout start')
    return development, holdout, int((before & ~known).sum())


def purged_folds(frame, n_splits=N_SPLITS):
    """Expanding validation folds, purged by actual label-end dates even with sparse rows."""
    folds = []
    # Reserve a longer initial training prefix than the default 1/(splits+1).
    # This rule depends on sample count, never on validation/holdout labels.
    test_size = len(frame) // (n_splits + 2)
    if test_size < 1:
        raise ValueError('Insufficient rows for the requested validation folds')
    for train, validation in TimeSeriesSplit(n_splits=n_splits, test_size=test_size).split(frame):
        boundary = frame['Date'].iloc[validation[0]]
        train = train[(frame['label_end_date'].iloc[train] < boundary).to_numpy()]
        if len(train) < 30:
            raise ValueError('Insufficient purged fold history (need >=30 rows); use fewer splits or more data')
        if set(frame['label'].iloc[train]) != {0, 1, 2}:
            raise ValueError('A training fold lacks one of the 3 regimes; use fewer splits or longer history')
        folds.append((train, validation))
    return folds


def _optuna_logistic_regression(trial) -> dict:
    return {
        'C': trial.suggest_float('C', 0.001, 100.0, log=True),
        'penalty': 'l2',
        'solver': 'lbfgs',
        'max_iter': 2000,
        'class_weight': 'balanced',
        'random_state': 42,
    }


def _optuna_random_forest(trial) -> dict:
    return {
        'n_estimators': trial.suggest_int('n_estimators', 100, 500, step=50),
        'max_depth': trial.suggest_int('max_depth', 3, 12),
        'min_samples_split': trial.suggest_int('min_samples_split', 5, 50),
        'min_samples_leaf': trial.suggest_int('min_samples_leaf', 3, 30),
        'max_features': trial.suggest_categorical('max_features', ['sqrt', 'log2', None]),
        'class_weight': 'balanced',
        'random_state': 42,
        'n_jobs': 2,
    }


def _optuna_lightgbm(trial) -> dict:
    return {
        'n_estimators': trial.suggest_int('n_estimators', 50, 400, step=25),
        'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.15, log=True),
        'max_depth': trial.suggest_int('max_depth', 3, 8),
        'num_leaves': trial.suggest_int('num_leaves', 10, 63),
        'min_child_samples': trial.suggest_int('min_child_samples', 20, 100),
        'subsample': trial.suggest_float('subsample', 0.6, 1.0),
        'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0),
        'reg_alpha': trial.suggest_float('reg_alpha', 1e-8, 10.0, log=True),
        'reg_lambda': trial.suggest_float('reg_lambda', 1e-8, 10.0, log=True),
        'class_weight': 'balanced',
        'random_state': 42,
        'n_jobs': 2,
        'verbosity': -1,
    }


def _optuna_xgboost(trial) -> dict:
    return {
        'n_estimators': trial.suggest_int('n_estimators', 50, 400, step=25),
        'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.15, log=True),
        'max_depth': trial.suggest_int('max_depth', 3, 8),
        'min_child_weight': trial.suggest_int('min_child_weight', 1, 20),
        'subsample': trial.suggest_float('subsample', 0.6, 1.0),
        'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0),
        'reg_alpha': trial.suggest_float('reg_alpha', 1e-8, 10.0, log=True),
        'reg_lambda': trial.suggest_float('reg_lambda', 1e-8, 10.0, log=True),
        'objective': 'multi:softprob',
        'num_class': 3,
        'eval_metric': 'mlogloss',
        'random_state': 42,
        'n_jobs': 2,
        'verbosity': 0,
        'use_label_encoder': False,
    }


def _optuna_catboost(trial) -> dict:
    return {
        'iterations': trial.suggest_int('iterations', 100, 500, step=50),
        'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.15, log=True),
        'depth': trial.suggest_int('depth', 3, 8),
        'l2_leaf_reg': trial.suggest_float('l2_leaf_reg', 1e-3, 10.0, log=True),
        'border_count': trial.suggest_int('border_count', 32, 255),
        'auto_class_weights': 'Balanced',
        'random_seed': 42,
        'verbose': 0,
        'thread_count': 2,
    }


OPTUNA_PARAM_FNS = {
    'LogisticRegression': _optuna_logistic_regression,
    'RandomForest':       _optuna_random_forest,
    'LightGBM':           _optuna_lightgbm,
    'XGBoost':            _optuna_xgboost,
    'CatBoost':           _optuna_catboost,
}


def create_model(name: str, params: dict):
    """Load optional training dependencies only for the requested model."""
    if name == 'LogisticRegression':
        return LogisticRegression(**params)
    if name == 'RandomForest':
        return RandomForestClassifier(**params)
    if name == 'LightGBM':
        from lightgbm import LGBMClassifier
        return LGBMClassifier(**params)
    if name == 'XGBoost':
        from xgboost import XGBClassifier
        return XGBClassifier(**params)
    if name == 'CatBoost':
        from catboost import CatBoostClassifier
        return CatBoostClassifier(**params)
    raise ValueError(f'Unknown model: {name}')


def needs_scaling(name: str) -> bool:
    return name == 'LogisticRegression'


def classification_metrics(y_true, predictions, training_labels):
    predictions = np.asarray(predictions).reshape(-1).astype(int)
    majority = int(np.bincount(training_labels, minlength=3).argmax())
    p, r, f, support = precision_recall_fscore_support(
        y_true, predictions, labels=[0, 1, 2], zero_division=0)
    return {
        'f1_macro': float(f1_score(y_true, predictions, labels=[0, 1, 2], average='macro', zero_division=0)),
        'mcc': float(matthews_corrcoef(y_true, predictions)),
        'accuracy': float(accuracy_score(y_true, predictions)),
        'baseline_f1': float(f1_score(y_true, np.full(len(y_true), majority),
                                     labels=[0, 1, 2], average='macro', zero_division=0)),
        'confusion_matrix': confusion_matrix(y_true, predictions, labels=[0, 1, 2]).tolist(),
        'per_class': {LABEL_NAMES[c]: {'precision': float(p[c]), 'recall': float(r[c]),
                                      'f1': float(f[c]), 'support': int(support[c])} for c in range(3)},
    }


def tune_and_evaluate(model_name, development, feature_names, folds,
                      n_trials=OPTUNA_N_TRIALS, timeout=OPTUNA_TIMEOUT):
    """Tune on development ONLY. Returned CV scores are selection/validation scores.

    No holdout data or labels enter this API. The selected candidate is fitted
    once on all permitted development rows by the caller.
    """
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    X = development[feature_names].to_numpy(dtype=np.float32)
    y = development['label'].to_numpy(dtype=np.int64)

    def objective(trial):
        params = OPTUNA_PARAM_FNS[model_name](trial)
        fold_results = []
        for train, validation in folds:
            X_tr, X_va = X[train], X[validation]
            if needs_scaling(model_name):
                scaler = StandardScaler().fit(X_tr)
                X_tr, X_va = scaler.transform(X_tr), scaler.transform(X_va)
            model = create_model(model_name, params)
            model.fit(X_tr, y[train])
            metrics = classification_metrics(y[validation], model.predict(X_va), y[train])
            metrics.update(
                n_train=len(train), n_validation=len(validation),
                train_end=str(development['Date'].iloc[train[-1]].date()),
                train_label_end=str(development['label_end_date'].iloc[train].max().date()),
                validation_start=str(development['Date'].iloc[validation[0]].date()),
                validation_end=str(development['Date'].iloc[validation[-1]].date()))
            fold_results.append(metrics)
        trial.set_user_attr('folds', fold_results)
        return float(np.mean([m['f1_macro'] for m in fold_results]))

    study = optuna.create_study(direction='maximize', sampler=optuna.samplers.TPESampler(seed=42))
    study.optimize(objective, n_trials=n_trials, timeout=timeout)
    best = study.best_trial
    return {
        'model_name': model_name,
        'best_params': OPTUNA_PARAM_FNS[model_name](best),
        'optuna_n_trials': len(study.trials),
        'validation_f1_macro': float(best.value),
        'validation_mcc': float(np.mean([f['mcc'] for f in best.user_attrs['folds']])),
        'validation_folds': best.user_attrs['folds'],
        'score_role': 'selection_validation_not_unbiased_test',
    }


def fit_selected_candidate(result, development, feature_names):
    X = development[feature_names].to_numpy(dtype=np.float32)
    y = development['label'].to_numpy(dtype=np.int64)
    scaler = StandardScaler().fit(X) if needs_scaling(result['model_name']) else None
    model = create_model(result['model_name'], result['best_params'])
    model.fit(scaler.transform(X) if scaler is not None else X, y)
    return model, scaler


def evaluate_holdout(model, scaler, development, holdout, feature_names):
    X = holdout[feature_names].to_numpy(dtype=np.float32)
    predictions = np.asarray(model.predict(scaler.transform(X) if scaler is not None else X)).reshape(-1)
    result = classification_metrics(holdout['label'].to_numpy(), predictions,
                                    development['label'].to_numpy(dtype=int))
    result.update(n_sessions=len(holdout), start=str(holdout['Date'].min().date()),
                  end=str(holdout['Date'].max().date()),
                  final_label_end=str(holdout['label_end_date'].max().date()))
    records = holdout[['Date', 'label_end_date', 'label', 'future_return']].copy()
    records['prediction'] = predictions.astype(int)
    return result, records


def export_onnx(model, model_name, horizon, feature_names, scaler,
                sample_input, output_dir, train_end, feature_version):
    """Verify native/ONNX parity before writing a research artifact (never auto-deploy).

    Logistic scaling is embedded in the ONNX graph, so the ONNX input is always
    the raw feature vector. Class encoding remains 0/1/2 with semantic -1/0/+1 metadata.
    """
    import onnx
    import onnxruntime as ort
    output_dir = Path(output_dir)
    n_features = len(feature_names)
    if model_name in ('LogisticRegression', 'RandomForest'):
        from sklearn.pipeline import Pipeline
        from skl2onnx import convert_sklearn
        from skl2onnx.common.data_types import FloatTensorType
        estimator = Pipeline([('scale', scaler), ('model', model)]) if scaler is not None else model
        exported = convert_sklearn(estimator, initial_types=[('float_input', FloatTensorType([None, n_features]))],
                                   target_opset=15)
    elif model_name in ('LightGBM', 'XGBoost'):
        import onnxmltools
        from onnxmltools.convert.common.data_types import FloatTensorType
        convert = onnxmltools.convert_lightgbm if model_name == 'LightGBM' else onnxmltools.convert_xgboost
        exported = convert(model, initial_types=[('float_input', FloatTensorType([None, n_features]))], target_opset=15)
    elif model_name == 'CatBoost':
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'catboost.onnx'
            model.save_model(str(path), format='onnx')
            exported = onnx.load(str(path))
    else:
        raise ValueError(f'Cannot export {model_name}')
    for key, value in {
        'feature_version': feature_version, 'features': ','.join(feature_names),
        'ticker': 'VNINDEX', 'train_end': train_end, 'horizon': str(horizon),
        'model_type': model_name, 'scaling': 'embedded' if scaler is not None else 'none',
        'label_map': '0:-1,1:0,2:1', 'execution': 'features_available_after_close',
        'artifact_role': 'research_pre_holdout_model',
    }.items():
        prop = exported.metadata_props.add()
        prop.key, prop.value = key, value
    session = ort.InferenceSession(exported.SerializeToString(), providers=['CPUExecutionProvider'])
    samples = np.asarray(sample_input[:32], dtype=np.float32)
    native_X = scaler.transform(samples) if scaler is not None else samples
    expected = np.asarray(model.predict(native_X)).reshape(-1).astype(int)
    outputs = session.run(None, {session.get_inputs()[0].name: samples})
    np.testing.assert_array_equal(np.asarray(outputs[0]).reshape(-1).astype(int), expected)
    probs = outputs[1]
    if isinstance(probs, list) and probs and isinstance(probs[0], dict):
        probs = np.array([[row[int(c)] for c in model.classes_] for row in probs])
    np.testing.assert_allclose(np.asarray(probs), model.predict_proba(native_X), rtol=1e-4, atol=1e-5)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f'stock_regime_t{horizon}.onnx'
    path.write_bytes(exported.SerializeToString())
    fixture = {'features': samples[0].tolist(), 'feature_names': feature_names,
               'feature_version': feature_version, 'label': int(expected[0]), 'horizon': horizon}
    path.with_suffix('.fixture.json').write_text(json.dumps(fixture, indent=2), encoding='utf-8')
    return path


def plot_comparison_chart(all_results, output_path):
    """Plot development selection scores only; keep final holdout results separate."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    horizons = sorted({r['horizon'] for r in all_results})
    fig, axes = plt.subplots(1, len(horizons), figsize=(7 * len(horizons), 5), squeeze=False)
    for ax, horizon in zip(axes[0], horizons):
        rows = [r for r in all_results if r['horizon'] == horizon]
        names = [f"{r['feature_set']} / {r['model_name']}" for r in rows]
        values = [r['validation_f1_macro'] for r in rows]
        ax.bar(np.arange(len(rows)), values)
        ax.set_xticks(np.arange(len(rows)), names, rotation=50, ha='right')
        ax.set_ylim(0, 1)
        ax.set_title(f'T+{horizon}: development validation (used for selection)')
        ax.set_ylabel('Macro F1 (fixed 3 classes)')
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--quick', action='store_true', help='5 trials / 30s per candidate; NO final holdout scoring or export')
    parser.add_argument('--audit-only', action='store_true', help='Validate data/features/splits; do not fit or export models')
    parser.add_argument('--development-only', action='store_true',
                        help='Use all mature labelled rows for development CV; no final holdout scoring or export')
    parser.add_argument('--trials', type=int, default=OPTUNA_N_TRIALS)
    parser.add_argument('--timeout', type=int, default=OPTUNA_TIMEOUT)
    parser.add_argument('--horizons', type=int, nargs='+', choices=list(HORIZONS), default=list(HORIZONS))
    parser.add_argument('--models', nargs='+', choices=MODEL_NAMES, default=MODEL_NAMES)
    parser.add_argument('--feature-sets', nargs='+', choices=list(FEATURE_VERSIONS), default=['close'],
                        help='When comparing feature sets, use identical eligible dates for fairness')
    parser.add_argument('--holdout-start', type=str, help='First reserved session (ISO date); otherwise reserve latest 20%% of label-eligible raw calendar')
    parser.add_argument('--splits', type=int, default=N_SPLITS)
    parser.add_argument('--data-dir', type=Path, default=DATA_DIR)
    parser.add_argument('--output-dir', type=Path, help='New research run directory; defaults to ml/reports/regime_v2/<UTC timestamp>')
    parser.add_argument('--calendar', type=Path, help='Optional independently sourced complete exchange-session CSV with Date column')
    parser.add_argument('--skip-onnx', action='store_true', help='Generate metrics only')
    parser.add_argument('--exposure-registry', type=Path, default=EXPOSURE_REGISTRY,
                        help='Record of previously inspected label periods')
    parser.add_argument('--prior-reports-dir', type=Path, default=REPORT_DIR / 'regime_v2',
                        help='Previous experiment reports to include when checking holdout reuse')
    args = parser.parse_args(argv)
    if args.trials < 1 or args.timeout < 1 or args.splits < 2:
        parser.error('trials/timeout must be positive and splits >=2')
    if args.development_only and args.holdout_start:
        parser.error('--development-only uses all mature labels; do not combine it with --holdout-start')
    args.horizons = list(dict.fromkeys(args.horizons))
    args.models = list(dict.fromkeys(args.models))
    args.feature_sets = list(dict.fromkeys(args.feature_sets))
    return args


def prepare_run(args):
    """Audit all inputs and all requested splits before any tuning starts."""
    index, index_audit = load_market_data(args.data_dir / 'VNINDEX.csv')
    etf_path = args.data_dir / 'E1VFVN30.csv'
    etf, etf_audit = load_market_data(etf_path) if etf_path.exists() else (None, None)
    calendar = audit_calendar(index, etf, args.calendar)
    if 'close-etf' in args.feature_sets and etf is None:
        raise ValueError(f'{etf_path} is required for close-etf')
    # Same boundary across feature sets AND horizon subsets (fixed maximum configured horizon).
    eligible_count = len(index) - max(HORIZONS)
    if eligible_count < 100:
        raise ValueError('Too few raw index sessions for the configured horizons')
    boundary = None if args.development_only else (
        pd.Timestamp(args.holdout_start) if args.holdout_start else index['Date'].iloc[int(eligible_count * 0.8)])
    if boundary is not None and boundary not in set(index['Date']):
        raise ValueError('holdout-start must be a session in VNINDEX.csv')
    exposure = observed_exposure(args.exposure_registry, args.prior_reports_dir)
    features = {kind: build_feature_matrix(index, etf, kind) for kind in args.feature_sets}
    datasets, summaries, errors = {}, [], []
    for horizon in args.horizons:
        labeled = {kind: create_labels(frame, horizon, names) for kind, (frame, names) in features.items()}
        common = None
        for frame in labeled.values():
            dates = pd.Index(frame['Date'])
            common = dates if common is None else common.intersection(dates)
        for kind, frame in labeled.items():
            names = features[kind][1]
            before_alignment = len(frame)
            frame = frame.loc[frame['Date'].isin(common)].reset_index(drop=True)
            summary = {'feature_set': kind, 'horizon': horizon, 'n_features': len(names),
                       'eligible_before_comparison_alignment': before_alignment,
                       'eligible_sessions': len(frame), 'label_counts': {
                           str(c): int((frame['label'] == c).sum()) for c in range(3)}}
            try:
                if args.development_only:
                    development, holdout, purged = frame, frame.iloc[:0].copy(), 0
                else:
                    development, holdout, purged = partition_holdout(frame, boundary)
                folds = purged_folds(development, args.splits)
                summary.update(n_development=len(development), n_holdout=len(holdout),
                               purged_at_holdout=purged,
                               feature_start=str(frame['Date'].min().date()),
                               feature_end=str(frame['Date'].max().date()),
                               folds=[{'n_train': len(tr), 'n_validation': len(va),
                                       'train_end': str(development['Date'].iloc[tr[-1]].date()),
                                       'train_label_end': str(development['label_end_date'].iloc[tr].max().date()),
                                       'validation_start': str(development['Date'].iloc[va[0]].date())}
                                      for tr, va in folds])
                datasets[kind, horizon] = (development, holdout, names, folds)
            except ValueError as exc:
                summary['error'] = str(exc)
                errors.append(f'{kind} T+{horizon}: {exc}')
            summaries.append(summary)
    if not (args.quick or args.development_only):
        try:
            assert_unseen_holdout(boundary, exposure)
        except ValueError as exc:
            errors.append(str(exc))
    audit = {'inputs': {'VNINDEX': index_audit, 'E1VFVN30': etf_audit}, 'calendar': calendar,
             'holdout_start': str(boundary.date()) if boundary is not None else None,
             'evaluation_protocol': exposure, 'development_only': args.development_only,
             'datasets': summaries, 'errors': errors,
             'assumptions': [
                 'CSV dates are the reference calendar unless --calendar is supplied; holidays are not independently certified.',
                 'CSV provenance and corporate-action adjustments need source verification; audit is not a data authenticity certificate.',
                 'No bfill, ffill, synthetic prices, or fixed-current-VN30 breadth.',
                 'ETF zero-volume observations are excluded; no market-price/NAV substitution.',
                 'Features use closing prices and become available after close(t).',
                 'All candidate feature sets use the same eligible dates when compared in one run.',
             ]}
    return datasets, audit


def main(argv=None):
    args = parse_args(argv)
    datasets, audit = prepare_run(args)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    out = args.output_dir or REPORT_DIR / 'regime_v2' / stamp
    out.mkdir(parents=True, exist_ok=False)
    (out / 'data_audit.json').write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'Output: {out.resolve()}')
    print(f"Evaluation: {'all mature labels for development only' if args.development_only else 'holdout from ' + audit['holdout_start']}; "
          f"calendar verified: {audit['calendar']['exchange_calendar_verified']}")
    if audit.get('evaluation_protocol', {}).get('latest_observed_label_date'):
        print('Previously inspected labels through: ' + audit['evaluation_protocol']['latest_observed_label_date'])
    print('Price adjustments / source provenance: see data_audit.json; not independently verified.')
    for row in audit['datasets']:
        print(json.dumps(row, ensure_ascii=False))
    if audit['errors']:
        raise ValueError('Preflight failed; no training started. ' + '; '.join(audit['errors']))
    if args.audit_only:
        print('Audit complete. No model fitted, holdout scored, or ONNX exported.')
        return audit
    report = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'mode': 'quick_development_only' if args.quick else ('development_only' if args.development_only else 'final_holdout'),
        'holdout_start': audit['holdout_start'],
        'selection': 'highest development CV macro F1 across requested models and feature sets; deterministic first candidate on ties',
        'evaluation': ('development selection scores only; no independent test claim' if args.quick or args.development_only else
                       'only the selected candidate per horizon is evaluated on the reserved holdout; no refit on holdout'),
        'evaluation_protocol': audit.get('evaluation_protocol'),
        'cv': {'n_splits': args.splits, 'purge': 'label_end_date < validation_start'},
        'optuna': {'n_trials': 5 if args.quick else args.trials, 'timeout_seconds': 30 if args.quick else args.timeout},
        'features': {kind: {'version': FEATURE_VERSIONS[kind], 'names': datasets[kind, args.horizons[0]][2]}
                     for kind in args.feature_sets},
        'results': [], 'best_per_horizon': {}, 'data_audit': 'data_audit.json',
    }
    for horizon in args.horizons:
        candidates = []
        for kind in args.feature_sets:
            development, _, names, folds = datasets[kind, horizon]
            for model_name in args.models:
                print(f'Tuning {kind} / {model_name} T+{horizon} (development only)', flush=True)
                result = tune_and_evaluate(model_name, development, names, folds,
                                           n_trials=report['optuna']['n_trials'],
                                           timeout=report['optuna']['timeout_seconds'])
                result.update(feature_set=kind, horizon=horizon)
                candidates.append(result)
                report['results'].append(result)
                print(f"Validation F1={result['validation_f1_macro']:.4f}; MCC={result['validation_mcc']:.4f}")
        winner = max(candidates, key=lambda r: r['validation_f1_macro'])
        selected = {'model': winner['model_name'], 'feature_set': winner['feature_set'],
                    'validation_f1_macro': winner['validation_f1_macro']}
        if not (args.quick or args.development_only):
            development, holdout, names, _ = datasets[winner['feature_set'], horizon]
            model, scaler = fit_selected_candidate(winner, development, names)
            # Recheck after tuning in case another run has consumed this period.
            if horizon == args.horizons[0]:
                exposure = observed_exposure(args.exposure_registry, args.prior_reports_dir)
                assert_unseen_holdout(holdout['Date'].min(), exposure)
                # Reserve the whole predeclared run before revealing its first score.
                # A later horizon in this same run must not block itself.
                for reserved_horizon in args.horizons:
                    reserved = datasets[winner['feature_set'], reserved_horizon][1]
                    record_exposure(args.exposure_registry, out / 'regime_v2_report.json', reserved_horizon,
                                    reserved['Date'].min(), reserved['label_end_date'].max())
            metrics, predictions = evaluate_holdout(model, scaler, development, holdout, names)
            selected.update(holdout=metrics, artifact_train_end=str(development['Date'].max().date()),
                            artifact_train_label_end=str(development['label_end_date'].max().date()))
            predictions.to_csv(out / f'holdout_predictions_t{horizon}.csv', index=False)
            print(f"Selected {winner['feature_set']} / {winner['model_name']} T+{horizon}: HOLDOUT F1={metrics['f1_macro']:.4f}, MCC={metrics['mcc']:.4f}")
            if not args.skip_onnx:
                try:
                    path = export_onnx(model, winner['model_name'], horizon, names, scaler,
                                       holdout[names].to_numpy(dtype=np.float32), out / 'models',
                                       selected['artifact_train_end'], FEATURE_VERSIONS[winner['feature_set']])
                    selected['onnx'] = str(path.relative_to(out))
                except Exception as exc:
                    selected['onnx_error'] = str(exc)
                    print(f'ONNX export failed for selected model: {exc}. Metrics retained; no model substitution.')
        else:
            selected['holdout'] = 'not_scored_in_quick_mode' if args.quick else 'not_scored_in_development_mode'
        report['best_per_horizon'][str(horizon)] = selected
        # Preserve completed horizons even if a later candidate fails.
        (out / 'regime_v2_report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    plot_comparison_chart(report['results'], out / 'model_comparison.png')
    print(f'Done. Reports: {out.resolve()}')
    return report


if __name__ == '__main__':
    main()

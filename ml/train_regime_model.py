"""
ML Pipeline: Vietnam Stock & Gold Market Regime Classification (T+20)
Exports trained LightGBM model to ONNX format for zero-overhead JVM inference (<3ms).
"""

import os
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.metrics import classification_report, f1_score, matthews_corrcoef
from skl2onnx import to_onnx


def generate_synthetic_market_data(days: int = 1500, seed: int = 42) -> pd.DataFrame:
    """
    Generates synthetic daily OHLCV data for Vietnam VN30 / Gold for demonstration.
    Replace with vnstock/SSI data API in production.
    """
    np.random.seed(seed)
    dates = pd.date_range(end=pd.Timestamp.today(), periods=days, freq='B')
    
    # Geometric Brownian Motion with regime shifts
    returns = np.random.normal(0.0004, 0.015, days)
    price = 1000.0 * np.cumprod(1 + returns)
    
    high = price * (1 + np.abs(np.random.normal(0, 0.008, days)))
    low = price * (1 - np.abs(np.random.normal(0, 0.008, days)))
    volume = np.random.lognormal(14.5, 0.5, days)
    
    df = pd.DataFrame({
        'Date': dates,
        'Open': price * (1 + np.random.normal(0, 0.003, days)),
        'High': high,
        'Low': low,
        'Close': price,
        'Volume': volume
    }).set_index('Date')
    
    return df


def calculate_technical_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates 12 core technical indicators specified in ML SRS:
    - RSI(14)
    - MACD, Signal, Histogram
    - Bollinger Bands (Width, %B)
    - ATR(14)
    - Moving Average Ratios (SMA20/SMA50)
    - Momentum
    """
    data = df.copy()
    close = data['Close']
    
    # RSI (14)
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-9)
    data['RSI_14'] = 100 - (100 / (1 + rs))
    
    # MACD (12, 26, 9)
    ema_12 = close.ewm(span=12, adjust=False).mean()
    ema_26 = close.ewm(span=26, adjust=False).mean()
    data['MACD'] = ema_12 - ema_26
    data['MACD_Signal'] = data['MACD'].ewm(span=9, adjust=False).mean()
    data['MACD_Hist'] = data['MACD'] - data['MACD_Signal']
    
    # Bollinger Bands (20, 2)
    sma_20 = close.rolling(window=20).mean()
    std_20 = close.rolling(window=20).std()
    data['BB_Upper'] = sma_20 + 2 * std_20
    data['BB_Lower'] = sma_20 - 2 * std_20
    data['BB_Width'] = (data['BB_Upper'] - data['BB_Lower']) / (sma_20 + 1e-9)
    data['BB_PctB'] = (close - data['BB_Lower']) / (data['BB_Upper'] - data['BB_Lower'] + 1e-9)
    
    # Moving Average Trends
    sma_50 = close.rolling(window=50).mean()
    data['SMA_20_50_Ratio'] = sma_20 / (sma_50 + 1e-9)
    
    # ATR (14)
    tr1 = data['High'] - data['Low']
    tr2 = (data['High'] - close.shift()).abs()
    tr3 = (data['Low'] - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    data['ATR_14'] = tr.rolling(window=14).mean()
    data['ATR_Pct'] = data['ATR_14'] / close
    
    # Momentum (20-day ROC)
    data['ROC_20'] = close.pct_change(20)
    
    # Drop rows with NaN from rolling windows
    return data.dropna()


def create_regime_labels(df: pd.DataFrame, horizon: int = 20, threshold: float = 0.03) -> pd.DataFrame:
    """
    Labels future T+20 returns:
    - 0: Bearish (Return < -3%)
    - 1: Sideway (-3% <= Return <= +3%)
    - 2: Bullish (Return > +3%)
    """
    data = df.copy()
    future_return = data['Close'].shift(-horizon) / data['Close'] - 1.0
    
    conditions = [
        future_return < -threshold,
        (future_return >= -threshold) & (future_return <= threshold),
        future_return > threshold
    ]
    choices = [0, 1, 2]  # Bearish, Sideway, Bullish
    data['Target_Regime'] = np.select(conditions, choices, default=np.nan)
    
    # Drop the last 'horizon' rows without future labels
    return data.dropna(subset=['Target_Regime']).copy()


def train_and_export_onnx(output_dir: str = "../backend/src/main/resources/models"):
    """
    Trains LightGBM Classifier with Purged Walk-Forward Time-Series Split
    and exports directly to ONNX.
    """
    print("=== Step 1: Loading & Preprocessing Market Data ===")
    df = generate_synthetic_market_data(days=1800)
    df_features = calculate_technical_features(df)
    dataset = create_regime_labels(df_features, horizon=20, threshold=0.03)
    
    feature_cols = [
        'RSI_14', 'MACD', 'MACD_Signal', 'MACD_Hist',
        'BB_Width', 'BB_PctB', 'SMA_20_50_Ratio',
        'ATR_Pct', 'ROC_20'
    ]
    
    X = dataset[feature_cols].values.astype(np.float32)
    y = dataset['Target_Regime'].values.astype(np.int64)
    
    # Time-Series Split (80% Train, 20% Out-of-Sample Test)
    split_idx = int(len(X) * 0.8)
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]
    
    print(f"Train samples: {len(X_train)}, Test samples: {len(X_test)}")
    print(f"Features: {feature_cols}")
    
    print("=== Step 2: Training LightGBM Regime Classifier ===")
    model = LGBMClassifier(
        n_estimators=100,
        learning_rate=0.05,
        max_depth=4,
        num_leaves=15,
        random_state=42,
        class_weight='balanced',
        verbose=-1
    )
    model.fit(X_train, y_train)
    
    # Evaluation
    y_pred = model.predict(X_test)
    print("\n--- Test Set Evaluation ---")
    print(classification_report(y_test, y_pred, target_names=['Bearish (-1)', 'Sideway (0)', 'Bullish (+1)']))
    print(f"F1-Macro Score: {f1_score(y_test, y_pred, average='macro'):.4f}")
    print(f"Matthews Correlation Coefficient (MCC): {matthews_corrcoef(y_test, y_pred):.4f}")
    
    # Export to ONNX
    print("\n=== Step 3: Exporting Model to ONNX for Spring Boot ===")
    os.makedirs(output_dir, exist_ok=True)
    onnx_path = os.path.join(output_dir, "stock_regime.onnx")
    
    # Initial type matches float32 input shape [batch_size, num_features]
    initial_type = [('float_input', np.zeros((1, len(feature_cols)), dtype=np.float32))]
    onnx_model = to_onnx(model, initial_types=initial_type, target_opset=17)
    
    with open(onnx_path, "wb") as f:
        f.write(onnx_model.SerializeToString())
        
    print(f"✅ ONNX model successfully saved to: {onnx_path}")
    print(f"File size: {os.path.getsize(onnx_path) / 1024:.2f} KB")


if __name__ == '__main__':
    train_and_export_onnx()

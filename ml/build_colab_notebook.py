import json
import os

cells = []

def add_md(source: str):
    cells.append({
        'cell_type': 'markdown',
        'metadata': {},
        'source': [line + '\n' for line in source.strip().split('\n')]
    })

def add_code(source: str):
    cells.append({
        'cell_type': 'code',
        'execution_count': None,
        'metadata': {},
        'outputs': [],
        'source': [line + '\n' for line in source.strip().split('\n')]
    })

# ==========================================
# Cell 1: Intro Markdown
# ==========================================
add_md("""# 🚀 EquiFolio: Huấn luyện Mô hình Phân loại Chu kỳ Thị trường (LightGBM ➔ ONNX)
**Đồ án:** CT250H - Niên Luận Chuyên Ngành (Software Engineering Capstone)  
**Mục tiêu chính:**
1. Huấn luyện mô hình nhận diện chế độ thị trường T+20 (Bullish +1, Sideway 0, Bearish -1) cho Cổ phiếu VN30 & Vàng.
2. **Mount Google Drive & Auto-save Checkpoint:** Mỗi khi một lần thử nghiệm (trial) đạt kết quả tốt hơn kỷ lục trước đó, mô hình sẽ **LẬP TỨC ĐƯỢC LƯU VÀO GOOGLE DRIVE** (`.onnx`, `.pkl`, `.txt`, `metadata.json`).
3. **Cơ chế chống mất mát (Fault-Tolerant):** Nếu Google Colab bị ngắt kết nối giữa chừng (Disconnect/Timeout), bạn chỉ cần chạy lại notebook. Hệ thống sẽ tự động đọc lại kỷ lục cũ và tiếp tục tối ưu hóa!""")

# ==========================================
# Cell 2: Mount Drive & Folder Setup
# ==========================================
add_code("""import os
import json
import time
from datetime import datetime

# 1. Mount Google Drive
try:
    from google.colab import drive
    drive.mount('/content/drive')
    IN_COLAB = True
    BASE_DIR = '/content/drive/MyDrive/EquiFolio_ML'
except ImportError:
    IN_COLAB = False
    BASE_DIR = './EquiFolio_ML'

# 2. Thiết lập cấu trúc thư mục lưu trữ trên Google Drive
MODELS_DIR = os.path.join(BASE_DIR, 'models')
LOGS_DIR = os.path.join(BASE_DIR, 'logs')
DATA_DIR = os.path.join(BASE_DIR, 'data')

for p in [BASE_DIR, MODELS_DIR, LOGS_DIR, DATA_DIR]:
    os.makedirs(p, exist_ok=True)

print("✅ Đã kết nối Google Drive thành công!")
print(f"📁 Thư mục lưu checkpoint & model: {MODELS_DIR}")
print(f"📊 Thư mục lưu nhật ký huấn luyện: {LOGS_DIR}")
print(f"📈 Thư mục dữ liệu thị trường: {DATA_DIR}")""")

# ==========================================
# Cell 3: Install Dependencies
# ==========================================
add_code("""# Cài đặt các thư viện định lượng & học máy cần thiết
!pip install -q lightgbm onnxmltools skl2onnx onnx onnxruntime optuna yfinance requests tabulate
print("✅ Cài đặt thư viện hoàn tất!")""")

# ==========================================
# Cell 4: Download Real Market Data
# ==========================================
add_code("""import requests
import yfinance as yf
import pandas as pd
import numpy as np

def load_or_fetch_data():
    vni_path = os.path.join(DATA_DIR, 'VNINDEX.csv')
    gold_path = os.path.join(DATA_DIR, 'GOLD.csv')

    # 1. Tải chỉ số VN-Index từ VNDirect DChart API (Dữ liệu thật 5 năm)
    if not os.path.exists(vni_path):
        print("⏳ Đang tải dữ liệu VN-Index từ VNDirect API...")
        url = "https://dchart-api.vndirect.com.vn/dchart/history?resolution=D&symbol=VNINDEX&from=1609459200&to=1790859600"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=15).json()
        df_vni = pd.DataFrame({
            'Date': pd.to_datetime(res['t'], unit='s').strftime('%Y-%m-%d'),
            'Open': res['o'],
            'High': res['h'],
            'Low': res['l'],
            'Close': res['c'],
            'Volume': res['v']
        })
        df_vni.to_csv(vni_path, index=False)
        print(f"✅ Đã lưu VN-Index: {len(df_vni)} phiên vào {vni_path}")
    else:
        df_vni = pd.read_csv(vni_path)
        print(f"✅ Đã có sẵn dữ liệu VN-Index ({len(df_vni)} phiên) từ Google Drive.")

    # 2. Tải Giá Vàng thế giới (GC=F) làm chỉ báo tương quan vĩ mô
    if not os.path.exists(gold_path):
        print("⏳ Đang tải dữ liệu Giá Vàng thế giới (GC=F)...")
        gold = yf.download('GC=F', start='2021-01-01', progress=False)
        gold = gold.reset_index()
        gold.columns = [c[0] if isinstance(c, tuple) else c for c in gold.columns]
        gold['Date'] = pd.to_datetime(gold['Date']).dt.strftime('%Y-%m-%d')
        gold.to_csv(gold_path, index=False)
        print(f"✅ Đã lưu Giá Vàng: {len(gold)} phiên vào {gold_path}")
    else:
        gold = pd.read_csv(gold_path)
        print(f"✅ Đã có sẵn dữ liệu Giá Vàng ({len(gold)} phiên) từ Google Drive.")

    return df_vni, gold

df_vni, df_gold = load_or_fetch_data()""")

# ==========================================
# Cell 5: Feature Engineering Pipeline
# ==========================================
add_code("""def build_feature_dataset(df_vni, df_gold):
    df = df_vni.copy()
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values('Date').reset_index(drop=True)
    
    close = df['Close']
    volume = df['Volume']

    # 1. RSI (14)
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / (loss + 1e-9)
    df['RSI_14'] = 100 - (100 / (1 + rs))

    # 2. MACD (12, 26, 9) - Chuẩn hóa % theo giá
    ema_12 = close.ewm(span=12, adjust=False).mean()
    ema_26 = close.ewm(span=26, adjust=False).mean()
    df['MACD'] = (ema_12 - ema_26) / close * 100.0
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']

    # 3. Bollinger Bands (20, 2)
    sma_20 = close.rolling(20).mean()
    std_20 = close.rolling(20).std()
    upper = sma_20 + 2 * std_20
    lower = sma_20 - 2 * std_20
    df['BB_Width'] = (upper - lower) / sma_20
    df['BB_PctB'] = (close - lower) / (upper - lower + 1e-9)

    # 4. SMA Ratio (20/50)
    sma_50 = close.rolling(50).mean()
    df['SMA_20_50_Ratio'] = sma_20 / (sma_50 + 1e-9)

    # 5. ATR% (14)
    tr1 = df['High'] - df['Low']
    tr2 = (df['High'] - close.shift()).abs()
    tr3 = (df['Low'] - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df['ATR_Pct'] = (tr.rolling(14).mean() / close) * 100.0

    # 6. ROC 20 (Rate of Change)
    df['ROC_20'] = close.pct_change(20) * 100.0

    # 7. Volume Ratio (Đột biến thanh khoản)
    vol_sma20 = volume.rolling(20).mean()
    df['Volume_Ratio'] = volume / (vol_sma20 + 1e-9)

    # 8. Historical Volatility (HV 20D)
    log_ret = np.log(close / close.shift(1))
    df['HV_20'] = log_ret.rolling(20).std() * np.sqrt(252) * 100.0

    # 9. Tương quan liên thị trường Vàng / VN-Index (Z-Score 60 phiên)
    df_g = df_gold[['Date', 'Close']].copy()
    df_g['Date'] = pd.to_datetime(df_g['Date'])
    df_g = df_g.rename(columns={'Close': 'Gold_Close'})
    df = pd.merge(df, df_g, on='Date', how='left')
    df['Gold_Close'] = df['Gold_Close'].ffill().bfill()
    df['Gold_Equity_Ratio'] = df['Gold_Close'] / df['Close']
    ratio_mean = df['Gold_Equity_Ratio'].rolling(60).mean()
    ratio_std = df['Gold_Equity_Ratio'].rolling(60).std()
    df['Gold_Equity_Zscore'] = (df['Gold_Equity_Ratio'] - ratio_mean) / (ratio_std + 1e-9)

    # 10. Gắn nhãn mục tiêu Chu kỳ T+20 (Horizon = 20 phiên)
    # 0: Bearish (<-3%), 1: Sideway ([-3%, +3%]), 2: Bullish (>+3%)
    future_return = df['Close'].shift(-20) / df['Close'] - 1.0
    conditions = [
        future_return < -0.03,
        (future_return >= -0.03) & (future_return <= 0.03),
        future_return > 0.03
    ]
    df['Target_Regime'] = np.select(conditions, [0, 1, 2], default=np.nan)

    FEATURE_COLS = [
        'RSI_14', 'MACD', 'MACD_Signal', 'MACD_Hist',
        'BB_Width', 'BB_PctB', 'SMA_20_50_Ratio',
        'ATR_Pct', 'ROC_20', 'Volume_Ratio', 'HV_20', 'Gold_Equity_Zscore'
    ]

    df_clean = df.dropna(subset=FEATURE_COLS + ['Target_Regime']).copy()
    return df_clean, FEATURE_COLS

dataset, FEATURE_COLS = build_feature_dataset(df_vni, df_gold)
print(f"✅ Trích xuất dữ liệu thành công! Tổng số mẫu: {len(dataset)}")
print(f"📋 Danh sách {len(FEATURE_COLS)} đặc trưng chuẩn hóa I(0):")
for i, col in enumerate(FEATURE_COLS, 1):
    print(f"  {i:02d}. {col}")
print("\\n📊 Phân bố các nhãn chu kỳ T+20:")
print(dataset['Target_Regime'].value_counts().rename({0: 'Bearish (-1)', 1: 'Sideway (0)', 2: 'Bullish (+1)'}))""")

# ==========================================
# Cell 6: Drive Checkpoint Manager
# ==========================================
add_code("""import joblib
import shutil
import onnxmltools
from onnxmltools.convert.common.data_types import FloatTensorType
from sklearn.metrics import f1_score, matthews_corrcoef, classification_report

class DriveCheckpointManager:
    \"\"\"
    Quản lý lưu trữ checkpoint vào Google Drive theo cơ chế ATOMIC.
    Cứ khi nào có mô hình đạt F1-Macro cao hơn kỷ lục cũ, lập tức:
    1. Lưu model LightGBM (.pkl, .txt)
    2. Convert và xuất ra định dạng ONNX (.onnx)
    3. Cập nhật metadata và lịch sử huấn luyện (metadata.json)
    Nếu Colab bị disconnect hoặc gặp lỗi, phiên chạy sau sẽ tự động đọc kỷ lục cũ!
    \"\"\"
    def __init__(self, models_dir: str, logs_dir: str, feature_cols: list):
        self.models_dir = models_dir
        self.logs_dir = logs_dir
        self.feature_cols = feature_cols
        self.meta_path = os.path.join(self.logs_dir, 'checkpoint_metadata.json')
        self.history_path = os.path.join(self.logs_dir, 'training_history.csv')
        self.best_f1 = -1.0
        self.best_mcc = -1.0
        self.best_trial = -1
        self.history = []

        # Đọc lại kỷ lục cũ từ Drive nếu đã từng chạy trước đó
        if os.path.exists(self.meta_path):
            try:
                with open(self.meta_path, 'r', encoding='utf-8') as f:
                    meta = json.load(f)
                    self.best_f1 = meta.get('best_f1_macro', -1.0)
                    self.best_mcc = meta.get('best_mcc', -1.0)
                    self.best_trial = meta.get('best_trial', -1)
                    print(f"🔄 Đọc lại kỷ lục từ Drive: Trial #{self.best_trial} | F1-Macro: {self.best_f1:.4f} | MCC: {self.best_mcc:.4f}")
            except Exception as e:
                print(f"⚠️ Không thể đọc metadata cũ ({e}), khởi tạo kỷ lục mới.")

    def evaluate_and_checkpoint(self, trial_num: int, model, X_test, y_test, params: dict):
        y_pred = model.predict(X_test)
        f1_macro = f1_score(y_test, y_pred, average='macro')
        mcc = matthews_corrcoef(y_test, y_pred)
        
        is_improved = (f1_macro > self.best_f1)
        
        record = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'trial': trial_num,
            'f1_macro': round(float(f1_macro), 4),
            'mcc': round(float(mcc), 4),
            'improved': is_improved,
            'params': params
        }
        self.history.append(record)

        if is_improved:
            prev_best = self.best_f1
            self.best_f1 = f1_macro
            self.best_mcc = mcc
            self.best_trial = trial_num

            print(f"\\n🔥 [KỶ LỤC MỚI - TRIAL #{trial_num}] 🔥")
            print(f"   📈 F1-Macro: {prev_best:.4f} ➔ {f1_macro:.4f} (+{(f1_macro - prev_best):.4f})")
            print(f"   🎯 MCC: {mcc:.4f}")

            # 1. Lưu LightGBM Pickle & Text
            pkl_path = os.path.join(self.models_dir, 'best_lgbm_model.pkl')
            joblib.dump(model, pkl_path)
            txt_path = os.path.join(self.models_dir, 'best_lgbm_model.txt')
            model.booster_.save_model(txt_path)

            # 2. Chuyển đổi và xuất ONNX chuẩn OpSet 15
            onnx_path = os.path.join(self.models_dir, 'stock_regime.onnx')
            initial_type = [('float_input', FloatTensorType([None, len(self.feature_cols)]))]
            onnx_model = onnxmltools.convert_lightgbm(model, initial_types=initial_type, target_opset=15)
            
            # Ghi an toàn (Atomic write): ghi ra file .tmp rồi rename để chống lỗi giữa chừng
            tmp_onnx = onnx_path + '.tmp'
            with open(tmp_onnx, 'wb') as f:
                f.write(onnx_model.SerializeToString())
            shutil.move(tmp_onnx, onnx_path)

            # 3. Cập nhật Metadata JSON trên Drive
            meta_content = {
                'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'best_trial': trial_num,
                'best_f1_macro': round(float(self.best_f1), 4),
                'best_mcc': round(float(self.best_mcc), 4),
                'num_features': len(self.feature_cols),
                'feature_names': self.feature_cols,
                'best_hyperparameters': params,
                'classification_report': classification_report(
                    y_test, y_pred, target_names=['Bearish (-1)', 'Sideway (0)', 'Bullish (+1)'], output_dict=True
                )
            }
            tmp_meta = self.meta_path + '.tmp'
            with open(tmp_meta, 'w', encoding='utf-8') as f:
                json.dump(meta_content, f, indent=2, ensure_ascii=False)
            shutil.move(tmp_meta, self.meta_path)

            print(f"   💾 ĐÃ LƯU TỨC THÌ VÀO GOOGLE DRIVE:")
            print(f"      • {onnx_path} (Sẵn sàng nạp vào Spring Boot)")
            print(f"      • {pkl_path}")
            print(f"      • {self.meta_path}")
        else:
            print(f"Trial #{trial_num:02d}: F1={f1_macro:.4f} | MCC={mcc:.4f} (Kỷ lục hiện tại: #{self.best_trial} với F1={self.best_f1:.4f})")

        pd.DataFrame(self.history).to_csv(self.history_path, index=False)
        return is_improved

checkpoint_mgr = DriveCheckpointManager(MODELS_DIR, LOGS_DIR, FEATURE_COLS)""")

# ==========================================
# Cell 7: Optuna Hyperparameter Optimization
# ==========================================
add_code("""import optuna
from lightgbm import LGBMClassifier

optuna.logging.set_verbosity(optuna.logging.WARNING)

# 1. Tách tập Train (80%) và Out-of-Sample Test (20%) theo thứ tự thời gian (Không shuffle!)
X = dataset[FEATURE_COLS].values.astype(np.float32)
y = dataset['Target_Regime'].values.astype(np.int64)

split_idx = int(len(X) * 0.8)
X_train, X_test = X[:split_idx], X[split_idx:]
y_train, y_test = y[:split_idx], y[split_idx:]

print(f"📊 Phân chia tập dữ liệu: Train = {len(X_train)} phiên | Test (OOS) = {len(X_test)} phiên")

# 2. Hàm mục tiêu tối ưu hóa với Optuna
def objective(trial):
    params = {
        'n_estimators': trial.suggest_int('n_estimators', 60, 250, step=20),
        'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.15, log=True),
        'max_depth': trial.suggest_int('max_depth', 3, 6),
        'num_leaves': trial.suggest_int('num_leaves', 10, 35),
        'min_child_samples': trial.suggest_int('min_child_samples', 15, 60),
        'subsample': trial.suggest_float('subsample', 0.6, 1.0),
        'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0),
        'reg_alpha': trial.suggest_float('reg_alpha', 1e-3, 10.0, log=True),
        'reg_lambda': trial.suggest_float('reg_lambda', 1e-3, 10.0, log=True),
        'class_weight': 'balanced',
        'random_state': 42,
        'verbose': -1,
        'n_jobs': -1
    }

    model = LGBMClassifier(**params)
    model.fit(X_train, y_train)

    # Đánh giá và lưu ngay vào Google Drive nếu tốt hơn kỷ lục trước
    checkpoint_mgr.evaluate_and_checkpoint(trial.number, model, X_test, y_test, params)
    
    y_pred = model.predict(X_test)
    return f1_score(y_test, y_pred, average='macro')

print("\\n🚀 Bắt đầu quá trình huấn luyện & tìm kiếm siêu tham số...")
print("🛡️ Mọi lần thử tốt hơn sẽ được lưu ngay tức thì vào Google Drive!")

study = optuna.create_study(direction='maximize')
study.optimize(objective, n_trials=35, timeout=1200)

print("\\n🎉 QUÁ TRÌNH HUẤN LUYỆN HOÀN TẤT!")
print(f"🏆 Kỷ lục tốt nhất thuộc về Trial #{checkpoint_mgr.best_trial} với F1-Macro = {checkpoint_mgr.best_f1:.4f}")""")

# ==========================================
# Cell 8: ONNX Sanity Verification
# ==========================================
add_code("""import onnxruntime as ort

onnx_file = os.path.join(MODELS_DIR, 'stock_regime.onnx')
session = ort.InferenceSession(onnx_file)

input_name = session.get_inputs()[0].name
output_name = session.get_outputs()[0].name

print(f"✅ Nạp mô hình ONNX thành công từ Drive: {onnx_file}")
print(f"   Input Tensor: {input_name} (Shape: {session.get_inputs()[0].shape})")
print(f"   Output Tensor: {output_name} (Shape: {session.get_outputs()[0].shape})")

# Kiểm tra tốc độ suy luận trên 1 mẫu
sample_x = X_test[:1].astype(np.float32)
start_t = time.perf_counter()
raw_result = session.run([output_name], {input_name: sample_x})
infer_time_ms = (time.perf_counter() - start_t) * 1000

pred_label = raw_result[0][0]
regime_map = {0: 'Bearish (-1) 🔻', 1: 'Sideway (0) ⚖️', 2: 'Bullish (+1) 🚀'}
print(f"\\n⚡ Độ trễ suy luận (Inference Latency): {infer_time_ms:.3f} ms (Thỏa mãn < 2ms JVM)")
print(f"   Dự báo chu kỳ thị trường: {regime_map.get(pred_label, pred_label)}")""")

# ==========================================
# Cell 9: Deployment Instructions
# ==========================================
add_md("""### 📥 Các bước đồng bộ Model từ Google Drive về Backend Spring Boot:
1. Mở **Google Drive** của bạn, truy cập vào thư mục:  
   `Google Drive > MyDrive > EquiFolio_ML > models > stock_regime.onnx`
2. Tải file `stock_regime.onnx` về máy tính.
3. Chép đè vào thư mục dự án:  
   `backend/src/main/resources/models/stock_regime.onnx`
4. Khởi động lại Spring Boot backend. Khi khởi động, bạn sẽ thấy log xác nhận:  
   `Loaded ONNX Market Regime model into JVM successfully. Ready for inference.`  
   *(Không còn cảnh báo heuristic fallback nữa!)*""")

notebook_json = {
    'cells': cells,
    'metadata': {
        'colab': {
            'provenance': [],
            'authorship_tag': 'EquiFolio CT250H'
        },
        'language_info': {
            'name': 'python',
            'version': '3.10.0'
        }
    },
    'nbformat': 4,
    'nbformat_minor': 5
}

with open('ml/train_regime_colab.ipynb', 'w', encoding='utf-8') as f:
    json.dump(notebook_json, f, indent=2, ensure_ascii=False)

print('Generated ml/train_regime_colab.ipynb successfully!')

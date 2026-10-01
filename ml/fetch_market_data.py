"""
Market Data Downloader for Vietnam Equities (VN30 Basket + Index ETFs + Gold)
Fetches 5-year historical OHLCV data from Yahoo Finance API without authentication.
Saves individual asset CSVs and consolidated daily close matrix for Markowitz & ML.
"""

import os
import sys
import json
import time
import urllib.request
from datetime import datetime
import pandas as pd


# 1. Full 30 VN30 Constituents on HOSE
VN30_TICKERS = [
    'ACB.VN', 'BCM.VN', 'BID.VN', 'BVH.VN', 'CTG.VN',
    'FPT.VN', 'GAS.VN', 'GVR.VN', 'HDB.VN', 'HPG.VN',
    'MBB.VN', 'MSN.VN', 'MWG.VN', 'PLX.VN', 'POW.VN',
    'SAB.VN', 'SHB.VN', 'SSB.VN', 'SSI.VN', 'STB.VN',
    'TCB.VN', 'TPB.VN', 'VCB.VN', 'VHM.VN', 'VIB.VN',
    'VIC.VN', 'VJC.VN', 'VNM.VN', 'VPB.VN', 'VRE.VN'
]

# 2. Leading Index Tracking ETFs & Commodities
ETF_AND_COMMODITIES = [
    'E1VFVN30.VN',  # Quỹ ETF DCVFMVN30 (Mô phỏng rổ chỉ số VN30)
    'FUEVN100.VN',  # Quỹ ETF VinaCapital VN100 (Mô phỏng rổ chỉ số VN100)
    'FUEVFVND.VN',  # Quỹ ETF DCVFMVN DIAMOND (Top cổ phiếu kín room ngoại)
    'GC=F'          # Vàng thế giới quy đổi (Gold Spot / Futures)
]

ALL_ASSETS = VN30_TICKERS + ETF_AND_COMMODITIES


def fetch_ticker_data(ticker: str, range_period: str = '5y') -> pd.DataFrame:
    """
    Downloads daily OHLCV bars for a ticker via Yahoo Finance v8 chart API.
    """
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range={range_period}&interval=1d"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status} from Yahoo Finance for {ticker}")
        payload = json.loads(resp.read().decode('utf-8'))
        
    chart = payload.get('chart', {}).get('result', [])
    if not chart:
        raise ValueError(f"No chart data found for {ticker}")
        
    result = chart[0]
    timestamps = result.get('timestamp', [])
    indicators = result.get('indicators', {})
    quote = indicators.get('quote', [{}])[0]
    
    dates = [datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d') for ts in timestamps]
    
    df = pd.DataFrame({
        'Date': dates,
        'Open': quote.get('open', []),
        'High': quote.get('high', []),
        'Low': quote.get('low', []),
        'Close': quote.get('close', []),
        'Volume': quote.get('volume', [])
    })
    
    # Drop rows with null close
    df = df.dropna(subset=['Close']).copy()
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values('Date').reset_index(drop=True)
    return df


def download_all_market_data(output_dir: str = "data"):
    """
    Downloads all 34 assets, saves individual raw CSVs and a consolidated Close price matrix.
    """
    raw_dir = os.path.join(output_dir, "raw")
    os.makedirs(raw_dir, exist_ok=True)
    
    print(f"================================================================")
    print(f"📊 Bắt đầu thu thập dữ liệu 5 năm ({len(ALL_ASSETS)} tài sản tài chính)...")
    print(f"   • 30 Cổ phiếu VN30: {', '.join([t.replace('.VN', '') for t in VN30_TICKERS[:5]])}, ...")
    print(f"   • 3 Quỹ ETF mô phỏng: E1VFVN30, FUEVN100, FUEVFVND")
    print(f"   • 1 Tài sản Vàng: GC=F (Gold)")
    print(f"================================================================\n")
    
    results = {}
    close_series = {}
    success_count = 0
    
    for idx, ticker in enumerate(ALL_ASSETS, 1):
        clean_name = ticker.replace('.VN', '').replace('=F', '')
        print(f"[{idx:02d}/{len(ALL_ASSETS):02d}] 📥 Đang tải {ticker:<12} ... ", end="", flush=True)
        
        try:
            df = fetch_ticker_data(ticker, range_period='5y')
            file_path = os.path.join(raw_dir, f"{clean_name}.csv")
            df.to_csv(file_path, index=False)
            
            # Store Close price for matrix
            close_series[clean_name] = df.set_index('Date')['Close']
            
            bars_count = len(df)
            start_date = df['Date'].min().strftime('%Y-%m-%d')
            end_date = df['Date'].max().strftime('%Y-%m-%d')
            print(f"✅ Xong ({bars_count:>4} phiên | {start_date} -> {end_date})")
            
            results[clean_name] = {
                'ticker': ticker,
                'bars': bars_count,
                'startDate': start_date,
                'endDate': end_date,
                'latestClose': float(df['Close'].iloc[-1])
            }
            success_count += 1
            
        except Exception as e:
            print(f"❌ Thất bại ({e})")
            
        time.sleep(0.3)  # Polite crawling rate-limit
        
    print(f"\n================================================================")
    print(f"🎉 Hoàn tất tải {success_count}/{len(ALL_ASSETS)} tài sản!")
    
    # Generate consolidated Close Price Matrix for Markowitz Covariance
    print(f"🔄 Đang tạo ma trận giá đóng cửa đồng bộ (vn30_close_matrix.csv)...")
    matrix_df = pd.DataFrame(close_series).sort_index()
    # Forward-fill minor holiday mismatches between VN and International Gold
    matrix_df = matrix_df.ffill().bfill()
    
    matrix_path = os.path.join(output_dir, "vn30_close_matrix.csv")
    matrix_df.to_csv(matrix_path)
    print(f"✅ Đã lưu ma trận giá ({matrix_df.shape[0]} ngày x {matrix_df.shape[1]} mã) tại: {matrix_path}")
    
    # Save Metadata JSON
    metadata_path = os.path.join(output_dir, "market_metadata.json")
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"✅ Đã lưu metadata tổng hợp tại: {metadata_path}")
    print(f"================================================================\n")


if __name__ == '__main__':
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, "data")
    download_all_market_data(output_dir=data_dir)

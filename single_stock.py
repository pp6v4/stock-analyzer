"""单只股票深度分析"""
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import akshare as ak
import efinance as ef
import pandas as pd
from datetime import datetime, timedelta
import time

code = sys.argv[1] if len(sys.argv) > 1 else '002181'
name_map = {'002181': '粤传媒'}

print(f"=== {name_map.get(code, code)} ({code}) 深度分析 ===\n")
print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

# 1. K线数据
print("[1] 拉取60日K线...")
try:
    df = ef.stock.get_quote_history(code, klt=101)
    if df is not None and not df.empty:
        df = df.tail(60)
        print(f"    共 {len(df)} 行\n")

        # 计算技术指标
        df['日期'] = df.iloc[:, 2] if df.shape[1] > 2 else df.index
        close_col = '收盘' if '收盘' in df.columns else df.columns[3]
        high_col = '最高' if '最高' in df.columns else df.columns[4]
        low_col = '最低' if '最低' in df.columns else df.columns[5]
        vol_col = '成交量' if '成交量' in df.columns else df.columns[7]

        closes = pd.to_numeric(df[close_col], errors='coerce')

        # 显示最后20天
        show_cols = [c for c in ['日期','开盘','收盘','最高','最低','成交量','换手率','涨跌幅'] if c in df.columns]
        print("--- 近20日K线 ---")
        print(df.tail(20)[show_cols].to_string())
        print()

        # 近期统计
        if len(closes) >= 5:
            print(f"5日均价: {closes.tail(5).mean():.2f}")
            print(f"10日均价: {closes.tail(10).mean():.2f}")
            print(f"20日均价: {closes.tail(20).mean():.2f}")
            print(f"今日收盘: {closes.iloc[-1]:.2f}")

            # 高低点
            high_20 = pd.to_numeric(df[high_col].tail(20), errors='coerce').max()
            low_20 = pd.to_numeric(df[low_col].tail(20), errors='coerce').min()
            print(f"20日最高: {high_20:.2f}")
            print(f"20日最低: {low_20:.2f}")
            print(f"20日振幅: {((high_20 - low_20) / low_20 * 100):.1f}%")

            # 涨跌幅统计
            print(f"\n近5日涨跌幅: {(closes.iloc[-1] / closes.iloc[-6] - 1) * 100:.2f}%" if len(closes) >= 6 else "")
            print(f"近10日涨跌幅: {(closes.iloc[-1] / closes.iloc[-11] - 1) * 100:.2f}%" if len(closes) >= 11 else "")
except Exception as e:
    print(f"    efinance失败: {e}")
    # fallback akshare
    try:
        end = datetime.now().strftime('%Y%m%d')
        start = (datetime.now() - timedelta(days=90)).strftime('%Y%m%d')
        df = ak.stock_zh_a_hist(symbol=code, period='daily', start_date=start, end_date=end, adjust='qfq')
        if df is not None and not df.empty:
            print(f"    akshare OK, {len(df)} 行")
            print(df.tail(30).to_string())
    except Exception as e2:
        print(f"    akshare也失败: {e2}")

# 2. 今日分时（如果可以）
print("\n[2] 尝试拉取实时行情...")
try:
    snap = ef.stock.get_quote_snapshot(code)
    if snap is not None:
        for k, v in snap.items():
            print(f"    {k}: {v}")
except Exception as e:
    print(f"    失败: {e}")

# 3. 龙虎榜
print("\n[3] 龙虎榜数据...")
try:
    df_lhb = ak.stock_lhb_stock_detail_em(symbol=code, date='20260602')
    if df_lhb is not None and not df_lhb.empty:
        print(df_lhb.to_string())
    else:
        print("    今日无龙虎榜数据")
except Exception:
    try:
        df_lhb = ak.stock_lhb_stock_detail_em(symbol=code)
        if df_lhb is not None and not df_lhb.empty:
            print(df_lhb.head(20).to_string())
        else:
            print("    无龙虎榜数据")
    except Exception as e:
        print(f"    失败: {e}")

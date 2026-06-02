"""持仓分析 - 三只票深度诊断"""
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import efinance as ef
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
import time

stocks = [
    ("000725", "京东方A", 5.30),
    ("002582", "好想你", None),
    ("002181", "粤传媒", None),
]

print(f"=== 持仓诊断 ({datetime.now().strftime('%Y-%m-%d %H:%M')}) ===\n")

for code, name, cost in stocks:
    print(f"\n{'='*60}")
    print(f"  {name} ({code})")
    if cost:
        print(f"  成本: {cost:.2f}")
    print(f"{'='*60}")

    # K线
    try:
        df = ef.stock.get_quote_history(code, klt=101)
        if df is not None and not df.empty:
            df = df.tail(30)
            close_col = '收盘' if '收盘' in df.columns else [c for c in df.columns if '收' in c][3]
            high_col = '最高' if '最高' in df.columns else [c for c in df.columns if '高' in c][4]
            low_col = '最低' if '最低' in df.columns else [c for c in df.columns if '低' in c][5]
            vol_col = '成交量' if '成交量' in df.columns else [c for c in df.columns if '量' in c][7]
            open_col = '开盘' if '开盘' in df.columns else [c for c in df.columns if '开' in c][2]
            pct_col = '涨跌幅' if '涨跌幅' in df.columns else [c for c in df.columns if '涨跌' in c][9] if len(df.columns) > 9 else None

            closes = pd.to_numeric(df[close_col], errors='coerce')
            highs = pd.to_numeric(df[high_col], errors='coerce')
            lows = pd.to_numeric(df[low_col], errors='coerce')
            opens = pd.to_numeric(df[open_col], errors='coerce')
            vols = pd.to_numeric(df[vol_col], errors='coerce')

            last = closes.iloc[-1]
            prev = closes.iloc[-2] if len(closes) >= 2 else last
            chg = (last / prev - 1) * 100

            # 技术指标
            ma5 = closes.tail(5).mean()
            ma10 = closes.tail(10).mean()
            ma20 = closes.tail(20).mean() if len(closes) >= 20 else closes.mean()
            high20 = highs.tail(20).max()
            low20 = lows.tail(20).min()
            vol_avg5 = vols.tail(5).mean()
            vol_latest = vols.iloc[-1]

            print(f"\n  [今日] 收:{last:.2f} | 涨跌:{chg:+.2f}%")
            print(f"  [均线] MA5:{ma5:.2f} | MA10:{ma10:.2f} | MA20:{ma20:.2f}")
            print(f"  [区间] 20日高:{high20:.2f} | 20日低:{low20:.2f}")
            print(f"  [量能] 今日量:{(vol_latest/1e4):.0f}万手 | 5日均量:{(vol_avg5/1e4):.0f}万手 | 量比:{vol_latest/vol_avg5:.2f}")

            # 和成本比较
            if cost:
                profit = (last / cost - 1) * 100
                print(f"  [持仓] 成本:{cost:.2f} | 盈亏:{profit:+.2f}%")

            # 判断
            if last > ma5 > ma10:
                trend = "多头排列，短线强势"
            elif last < ma5 < ma10:
                trend = "空头排列，短线弱势"
            elif last > ma5:
                trend = "站上5日线，偏强"
            elif last < ma5:
                trend = "跌破5日线，偏弱"
            else:
                trend = "均线纠缠，方向不明"

            if chg >= 9.5:
                trend += " | 今日涨停"
            elif chg <= -9.5:
                trend += " | 今日跌停！"

            print(f"  [趋势] {trend}")

            # 近5日走势
            print(f"\n  近10日K线:")
            tail = df.tail(10)
            for _, r in tail.iterrows():
                date_val = r.get('日期', '')
                c = float(r[close_col])
                o = float(r[open_col])
                h = float(r[high_col])
                l = float(r[low_col])
                v = float(r[vol_col])
                p = (c / o - 1) * 100 if o != 0 else 0
                bar = "█" * min(int(abs(p) * 5), 20)
                direction = "+" if p >= 0 else "-"
                print(f"    {date_val} | O:{o:.2f} C:{c:.2f} H:{h:.2f} L:{l:.2f} | {direction}{abs(p):.1f}% {bar} | 量:{v/1e4:.0f}万手")

    except Exception as e:
        print(f"  [ERROR] {e}")
        import traceback
        traceback.print_exc()

    time.sleep(1)

# 2. 实时快照
print(f"\n{'='*60}")
print(f"  实时行情快照")
print(f"{'='*60}")
for code, name, cost in stocks:
    try:
        snap = ef.stock.get_quote_snapshot(code)
        if snap is not None:
            print(f"\n  {name}({code}): {snap.get('最新价','')} | {snap.get('涨跌幅','')}%")
            print(f"  卖1: {snap.get('卖1价','')}({snap.get('卖1数量','')}) | 买1: {snap.get('买1价','')}({snap.get('买1数量','')})")
    except:
        pass

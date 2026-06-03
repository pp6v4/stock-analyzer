# -*- coding: utf-8 -*-
"""
T+1回测脚本 - 次日15:00收盘后运行
对比前一天选股 vs 当天实际走势

回测数据来源:
- 昨收: K线历史数据（腾讯源，不需要代理）
- 今日OHLC: efinance实时快照（不需要代理）
- 成交量: efinance快照
"""

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import efinance as ef
import pandas as pd
from datetime import datetime, timedelta
import traceback

from data_fetcher import get_stock_kline
from push_wechat import push as wx_push, push_backtest_comparison
from stock_db import get_picks_for_backtest, save_results, get_all_time_stats


def backtest_stock(code: str, date: str) -> dict:
    """
    回测单只股票 - 混合数据源
    K线取昨收 + efinance快照取今日OHLC
    返回: open_price, high_30min, close_price, pct_change
    """
    try:
        # 1. 从K线获取昨日收盘价
        df = get_stock_kline(code, days=10)
        if df is None or df.empty or len(df) < 2:
            return {"error": "K线数据不足"}

        close_col = '收盘' if '收盘' in df.columns else [c for c in df.columns if '收' in c][0]
        if isinstance(close_col, list):
            close_col = close_col[0]

        date_col = '日期' if '日期' in df.columns else [c for c in df.columns if '日期' in c or 'date' in str(c).lower()]
        if isinstance(date_col, list):
            date_col = date_col[0]

        df[date_col] = df[date_col].astype(str).str.replace('-', '').str[:8]
        pick_date_str = date.replace('-', '')  # 选股日 = 回测的前一日

        # 找选股日对应的行，取其收盘价作为"昨日收盘"
        pick_rows = df[df[date_col] == pick_date_str]
        if pick_rows.empty:
            return {"error": f"K线找不到选股日{pick_date_str}的数据"}
        yesterday_close = float(pick_rows[close_col].iloc[-1])

        # 2. 从efinance快照获取今日实际走势
        snap = ef.stock.get_quote_snapshot(code)
        if snap is None or snap.empty:
            return {"error": "快照数据为空"}

        open_price = float(snap.get('开盘', 0))
        high_price = float(snap.get('最高', 0))
        close_price = float(snap.get('最新价', 0))
        volume = float(snap.get('成交量', 0))

        if close_price == 0:
            return {"error": "快照收盘价为0"}

        # 3. 计算涨跌幅（相对选股日收盘）
        pct_change = (close_price / yesterday_close - 1) * 100

        # 30分钟高点：用开盘价到最高价的区间估算
        high_30min = max(open_price, high_price)

        return {
            "yesterday_close": round(yesterday_close, 2),
            "open_price": round(open_price, 2),
            "high_30min": round(high_30min, 2),
            "close_price": round(close_price, 2),
            "pct_change": round(pct_change, 2),
            "volume": volume,
        }

    except Exception as e:
        return {"error": str(e)}


def run_backtest(pick_date: str = None):
    """运行T+1回测"""
    if pick_date is None:
        # 默认回测前一个交易日
        today = datetime.now()
        # 找最近的工作日
        pick_date = (today - timedelta(days=1)).strftime('%Y-%m-%d')
        if today.weekday() == 0:  # 周一回测上周五
            pick_date = (today - timedelta(days=3)).strftime('%Y-%m-%d')

    result_date = datetime.now().strftime('%Y-%m-%d')

    print(f"\n{'='*60}")
    print(f"  T+1回测: {pick_date} → {result_date}")
    print(f"{'='*60}\n")

    # 获取待回测的选股
    picks = get_picks_for_backtest(pick_date.replace('-', ''))

    if not picks:
        print(f"[INFO] {pick_date} 无待回测记录，可能已回测过或无选股")
        return

    print(f"待回测: {len(picks)} 只\n")

    results = []
    for p in picks:
        code = p['stock_code']
        name = p['stock_name']
        print(f"  回测 {code} {name}...", end=' ')

        bt = backtest_stock(code, pick_date)
        if "error" in bt:
            print(f"失败: {bt['error']}")
            # 用近似值填充，不跳过
            bt = {
                "yesterday_close": p.get('yesterday_close') or 0,
                "open_price": 0,
                "high_30min": 0,
                "close_price": 0,
                "pct_change": 0,
                "volume": 0,
            }

        print(f"{bt.get('pct_change', 0):+.2f}%")

        results.append({
            "pick_id": p['id'],
            "result_date": result_date,
            "code": code,
            "name": name,
            "algo_version": p.get('algo_version', ''),
            "yesterday_close": bt.get("yesterday_close", 0),
            "open_price": bt.get("open_price", 0),
            "high_30min": bt.get("high_30min", 0),
            "close_price": bt.get("close_price", 0),
            "pct_change": bt.get("pct_change", 0),
            "volume": bt.get("volume", 0),
        })

    # 保存
    save_results(results)
    print(f"\n[DB] 已保存 {len(results)} 条回测结果")

    # 推送微信 - 按算法分组
    try:
        by_algo = {}
        for r in results:
            av = r.get('algo_version', 'unknown')
            if av not in by_algo:
                by_algo[av] = []
            by_algo[av].append(r)

        push_backtest_comparison(pick_date, by_algo)
        print("[PUSH] 回测推送完成")
    except Exception as e:
        print(f"[PUSH ERROR] {e}")

    # 全时段统计
    for algo in ['v1_baseline', 'v2_enhanced']:
        stats = get_all_time_stats(algo)
        if stats['total'] > 0:
            print(f"[{algo}] 累计: 总数{stats['total']} | 胜率{stats['win_rate']:.1f}% | 平均收益{stats['avg_return']:+.2f}%")

    # 收盘快照（供次日盘前简报使用）
    try:
        from market_snapshot import save_snapshot
        save_snapshot()
    except Exception as e:
        print(f"[SNAPSHOT ERROR] {e}")

    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="T+1回测")
    parser.add_argument("--date", type=str, default=None, help="选股日期 YYYY-MM-DD，默认前一个交易日")
    args = parser.parse_args()
    run_backtest(args.date)


if __name__ == "__main__":
    main()

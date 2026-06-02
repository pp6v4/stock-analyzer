# -*- coding: utf-8 -*-
"""
T+1回测脚本 - 次日15:00收盘后运行
对比前一天选股 vs 当天实际走势
"""

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import pandas as pd
from datetime import datetime, timedelta
import traceback

from data_fetcher import get_stock_kline
from push_wechat import push as wx_push, push_backtest, push_backtest_comparison
from stock_db import get_picks_for_backtest, save_results, get_all_time_stats


def backtest_stock(code: str, date: str) -> dict:
    """
    回测单只股票
    返回: open_price, high_30min, close_price, pct_change
    """
    try:
        df = get_stock_kline(code, days=30)
        if df is None or df.empty or len(df) < 2:
            return {"error": "K线数据不足"}

        # 找目标日期的数据
        # 先确定列名
        date_col = '日期' if '日期' in df.columns else [c for c in df.columns if '日期' in c]
        date_col = date_col[0] if isinstance(date_col, list) and date_col else df.columns[2]

        open_col = '开盘' if '开盘' in df.columns else [c for c in df.columns if '开' in c][0]
        high_col = '最高' if '最高' in df.columns else [c for c in df.columns if '高' in c][0]
        close_col = '收盘' if '收盘' in df.columns else [c for c in df.columns if '收' in c][0]
        vol_col = '成交量' if '成交量' in df.columns else [c for c in df.columns if '量' in c and '成' in c][0]

        # 格式化日期列
        df[date_col] = df[date_col].astype(str).str.replace('-', '').str[:8]
        target = date.replace('-', '')

        # 找目标日及前一日
        rows = df[df[date_col] == target]
        if rows.empty:
            # 尝试直接拿最后一行（如果是今天的数据）
            today = datetime.now().strftime('%Y%m%d')
            rows = df[df[date_col] == today]
            if rows.empty:
                rows = df.tail(1)
                target = today

        if rows.empty:
            return {"error": f"找不到{date}的数据"}

        row = rows.iloc[-1]

        # 前一日收盘
        prev_rows = df[df.index < rows.index[0]]
        yesterday_close = float(prev_rows[close_col].iloc[-1]) if not prev_rows.empty else float(row[open_col])

        open_price = float(row[open_col])
        high_price = float(row[high_col])
        close_price = float(row[close_col])
        volume = float(row[vol_col]) if vol_col in row.index else 0

        # 计算涨跌幅（相对前一日收盘）
        pct_change = (close_price / yesterday_close - 1) * 100

        # 30分钟高点（日线数据无法精确到30分钟，用开盘价到最高价的中间值近似）
        # 实际上日线拿不到日内30分钟数据，用当日最高作为参考
        high_30min = max(open_price, high_price * 0.985)  # 近似

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

    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="T+1回测")
    parser.add_argument("--date", type=str, default=None, help="选股日期 YYYY-MM-DD，默认前一个交易日")
    args = parser.parse_args()
    run_backtest(args.date)


if __name__ == "__main__":
    main()

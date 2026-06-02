# -*- coding: utf-8 -*-
"""
每日选股 - 双算法并行（V1 + V2）
14:30自动运行 → 选股 → 入库 → 推微信
"""

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import pandas as pd
from datetime import datetime
import traceback

from data_fetcher import get_limit_up_stocks, get_continuous_limit_up, get_industry_rank
from algorithms import select_stocks, list_versions
from push_wechat import push as wx_push, push_stock_picks
from stock_db import save_picks


def run(date: str, algo_versions: list = None):
    """
    运行选股
    algo_versions: 要运行的算法版本列表，默认全部
    """
    if algo_versions is None:
        algo_versions = list_versions()

    print(f"\n{'='*60}")
    print(f"  每日选股 ({date} {datetime.now().strftime('%H:%M')})")
    print(f"  算法: {', '.join(algo_versions)}")
    print(f"{'='*60}\n")

    # 1. 拉数据
    print("[1/3] 市场数据...")
    zt = get_limit_up_stocks(date)
    zt_codes = set()
    sector_counts = {}
    if not zt.empty:
        zt_codes = set(zt['代码'].tolist())
        ind_col = '所属行业' if '所属行业' in zt.columns else None
        if ind_col:
            sector_counts = zt[ind_col].value_counts().to_dict()

    strong = get_continuous_limit_up()
    if strong.empty:
        print("[ERROR] 强势股数据为空")
        return {}

    print(f"      涨停{len(zt_codes)}只, 强势股{len(strong)}只, 活跃板块{len(sector_counts)}个\n")

    # 2. 每个算法选股
    print("[2/3] 算法选股...\n")
    all_picks = {}

    for algo_ver in algo_versions:
        picks = select_stocks(algo_ver, strong, sector_counts, zt_codes, max_picks=5)
        for p in picks:
            p['date'] = date
            p['yesterday_close'] = None
        all_picks[algo_ver] = picks

        print(f"  [{algo_ver}] 选出 {len(picks)} 只:")
        for p in picks:
            print(f"     #{p['rank']} {p['code']} {p['name']} | +{p['pct']}% | "
                  f"{p['sector']}({p['sector_zt_count']}只) | 评分:{p['score']}")
        print()

    # 3. 保存 + 推送
    print("[3/3] 保存 & 推送...")

    for algo_ver, picks in all_picks.items():
        if picks:
            save_picks(picks)
            print(f"  [{algo_ver}] DB保存 {len(picks)} 条")

    # 推送微信 - 合并两个算法的结果
    push_combined(date, all_picks, len(zt_codes))

    return all_picks


def push_combined(date: str, all_picks: dict, zt_count: int):
    """合并推送两个算法的选股结果"""
    lines = [
        f"## 今日选股 ({date})",
        f"",
        f"**涨停**: {zt_count}只 | **算法**: {' vs '.join(all_picks.keys())}",
        f"",
    ]

    for algo_ver, picks in all_picks.items():
        algo_label = algo_ver.replace('_', ' ').title()
        lines.append(f"### {algo_label}")
        lines.append("")
        lines.append("| # | 代码 | 名称 | 涨幅 | 板块 | 评分 | 逻辑 |")
        lines.append("|---|---|---|---|---|---|---|")
        for p in picks:
            lines.append(
                f"| {p['rank']} | {p['code']} | {p['name']} | +{p['pct']}% | "
                f"{p['sector']}({p['sector_zt_count']}只) | {p['score']} | {p['reason']} |"
            )
        lines.append("")

    lines.append("> V1=基础版 | V2=增强版(量能+市值因子)")
    lines.append("> T+1回测结果将于明日收盘后推送")

    wx_push(f"【选股】{date} 双算法对比", "\n".join(lines))


def main():
    date = datetime.now().strftime('%Y%m%d')
    try:
        run(date)
        print(f"\n{'='*60}")
        print("  选股完成")
        print(f"{'='*60}")
    except Exception as e:
        print(f"[ERROR] {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()

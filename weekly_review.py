# -*- coding: utf-8 -*-
"""
每周复盘 - 含算法A/B对比 + 优胜劣汰
每周五15:30运行
"""

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from datetime import datetime, timedelta
from push_wechat import push_weekly_review
from stock_db import (get_week_stats, get_algo_comparison, save_weekly_review,
                      get_all_time_stats, get_picks_by_date)
from algorithms import list_versions


def get_week_range():
    today = datetime.now()
    monday = today - timedelta(days=today.weekday())
    friday = monday + timedelta(days=4)
    return monday.strftime('%Y%m%d'), friday.strftime('%Y%m%d')


def run_weekly_review():
    week_start, week_end = get_week_range()
    week_label = f"{week_start[:4]}-{week_start[4:6]}-{week_start[6:]} ~ {week_end[:4]}-{week_end[4:6]}-{week_end[6:]}"

    print(f"\n{'='*60}")
    print(f"  周复盘: {week_label}")
    print(f"{'='*60}\n")

    stats = get_week_stats(week_start, week_end)
    if not stats:
        print("[INFO] 本周无选股记录")
        push_weekly_review(week_label, "本周无选股记录")
        return

    # ========== 算法对比 ==========
    algo_comparison = get_algo_comparison(week_start, week_end)
    print("算法对比:")
    for algo, as_ in algo_comparison.items():
        print(f"  {algo}: 胜率{as_['win_rate']:.1f}% | 平均收益{as_['avg_return']:+.2f}% | 累计收益{as_['total_return']:+.2f}%")

    # 判定胜者
    winner = determine_winner(algo_comparison)
    print(f"\n  本周优胜算法: {winner}")

    # ========== 生成报告 ==========
    lines = build_report(week_label, stats, algo_comparison, winner)

    # ========== 保存 & 推送 ==========
    total_picks = len(stats)
    has_results = [s for s in stats if s.get('pct_change') is not None]
    wins = [s for s in has_results if s.get('pct_change', 0) > 0]
    all_returns = [s['pct_change'] for s in has_results]
    avg_return = sum(all_returns) / len(all_returns) if all_returns else 0
    best = max(has_results, key=lambda x: x['pct_change']) if has_results else None
    worst = min(has_results, key=lambda x: x['pct_change']) if has_results else None

    week_obj = {
        "total": total_picks, "wins": len(wins), "avg_return": avg_return,
        "best_stock": f"{best['stock_name']}({best['stock_code']})" if best else "",
        "worst_stock": f"{worst['stock_name']}({worst['stock_code']})" if worst else "",
    }

    # 算法比较JSON
    import json
    comparison_json = json.dumps({
        algo: {"win_rate": as_['win_rate'], "avg_return": as_['avg_return'],
               "total_return": as_['total_return']}
        for algo, as_ in algo_comparison.items()
    }, ensure_ascii=False)

    save_weekly_review(week_start, week_end, week_obj, comparison_json, winner, "\n".join(lines))
    print(f"[DB] 周复盘已保存, 优胜算法: {winner}")

    push_weekly_review(week_label, "\n".join(lines))
    print(f"[PUSH] 周复盘已推送")

    return winner


def determine_winner(algo_comparison: dict) -> str:
    """
    判定优胜算法
    规则：综合得分 = 平均收益*0.4 + 胜率*0.3 + 总收益*0.3
    如果只有一个算法则直接获胜
    """
    if len(algo_comparison) <= 1:
        return list(algo_comparison.keys())[0] if algo_comparison else "none"

    scores = {}
    for algo, as_ in algo_comparison.items():
        # 归一化
        ret_score = as_['avg_return'] * 0.4
        wr_score = as_['win_rate'] * 0.3
        total_score = min(as_['total_return'], 30) * 0.3  # cap at 30%
        scores[algo] = ret_score + wr_score + total_score

    return max(scores, key=scores.get)


def build_report(week_label: str, stats: list, algo_comparison: dict, winner: str) -> list:
    """生成周复盘报告"""
    lines = [
        f"## 周复盘 ({week_label})",
        f"",
    ]

    # === 算法PK ===
    lines.append("### 算法A/B对比")
    lines.append("")
    lines.append("| 指标 | V1 基础版 | V2 增强版 |")
    lines.append("|------|-----------|-----------|")

    v1 = algo_comparison.get('v1_baseline', {})
    v2 = algo_comparison.get('v2_enhanced', {})

    for metric, key, fmt in [
        ("选股数", "total", "{}"),
        ("胜率", "win_rate", "{:.1f}%"),
        ("平均收益", "avg_return", "{:+.2f}%"),
        ("最大盈利", "max_win", "{:+.2f}%"),
        ("最大亏损", "max_loss", "{:+.2f}%"),
        ("累计收益", "total_return", "{:+.2f}%"),
    ]:
        v1_val = v1.get(key, 0) if v1 else 0
        v2_val = v2.get(key, 0) if v2 else 0
        v1_str = fmt.format(v1_val)
        v2_str = fmt.format(v2_val)
        # 标记优劣
        better = ""
        if v1 and v2:
            if key in ("max_loss",):
                better = "👑" if v1_val > v2_val else ("👑" if v1_val < v2_val else "")
            else:
                better_v = "v1" if v1_val > v2_val else ("v2" if v2_val > v1_val else "")
        lines.append(f"| {metric} | {v1_str} | {v2_str} {'←' + better_v if better_v else ''} |")

    lines.append("")
    winner_label = winner.replace('_', ' ').title()
    lines.append(f"**本周优胜**: 🏆 **{winner_label}**")
    lines.append("")

    # === 每日详情 ===
    lines.append("### 每日选股详情")
    lines.append("")

    by_date = {}
    for s in stats:
        d = s['pick_date']
        if d not in by_date:
            by_date[d] = {}
        algo = s.get('algo_version', 'unknown')
        if algo not in by_date[d]:
            by_date[d][algo] = []
        by_date[d][algo].append(s)

    for date_str in sorted(by_date.keys()):
        date_label = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
        lines.append(f"**{date_label}**")
        lines.append("")

        for algo_ver in ['v1_baseline', 'v2_enhanced']:
            day_picks = by_date[date_str].get(algo_ver, [])
            if not day_picks:
                continue
            algo_short = "V1" if "v1" in algo_ver else "V2"
            lines.append(f"{algo_short}:")
            for p in day_picks:
                pct = p.get('pct_change')
                if pct is not None:
                    mark = "✅" if pct > 0 else "❌"
                    pct_str = f"→ {pct:+.2f}% {mark}"
                else:
                    pct_str = "→ ⏳待回测"
                lines.append(f"- {p['stock_code']} {p['stock_name']} ({p['sector'] or '-'}) {pct_str}")
        lines.append("")

    # === 历史累计 ===
    lines.append("### 历史累计")
    lines.append("")
    lines.append("| 算法 | 总数 | 胜率 | 平均收益 |")
    lines.append("|------|------|------|----------|")
    for algo in ['v1_baseline', 'v2_enhanced']:
        as_ = get_all_time_stats(algo)
        if as_['total'] > 0:
            lines.append(f"| {algo.replace('_',' ').title()} | {as_['total']} | {as_['win_rate']:.1f}% | {as_['avg_return']:+.2f}% |")
    lines.append("")

    # === 策略建议 ===
    lines.append("### 策略改进建议")
    lines.append("")
    lines.append(f"- 本周优胜算法为 **{winner_label}**，下周将以该算法为主策略")
    lines.append(f"- 若连续2周优胜方不变，下下周起可单跑优胜算法（减少噪音）")
    lines.append(f"- 若连续2周均亏损，触发策略重审机制")

    return lines


if __name__ == "__main__":
    run_weekly_review()

# -*- coding: utf-8 -*-
"""微信推送模块 - 通过Server酱推送到微信"""

import os
import requests

# 优先从环境变量读取，否则使用默认值
SENDKEY = os.environ.get("SCT_SENDKEY", "")
if not SENDKEY:
    # 尝试从本地配置文件读取
    try:
        with open(os.path.join(os.path.dirname(__file__), ".sendkey"), "r") as f:
            SENDKEY = f.read().strip()
    except:
        pass

API_URL = f"https://sctapi.ftqq.com/{SENDKEY}.send" if SENDKEY else ""


def push(title: str, content: str, channel: str = "9") -> bool:
    """
    推送消息到微信
    title: 标题
    content: 正文（支持Markdown）
    channel: 9=方糖服务号
    """
    if not SENDKEY:
        print("[PUSH SKIP] 未配置SendKey，跳过推送")
        return False
    try:
        resp = requests.post(API_URL, data={
            "title": title,
            "desp": content,
            "channel": channel
        }, timeout=15)
        result = resp.json()
        if result.get("code") == 0:
            print(f"[PUSH OK] {title}")
            return True
        else:
            print(f"[PUSH FAIL] {result}")
            return False
    except Exception as e:
        print(f"[PUSH ERROR] {e}")
        return False


def push_stock_picks(date: str, picks: list, market_summary: str):
    """推送每日选股结果"""
    lines = [
        f"## 今日选股 ({date})",
        f"",
        f"### 市场概况",
        market_summary,
        f"",
        f"### 精选5只标的",
        f"",
        f"| 排名 | 代码 | 名称 | 入选逻辑 | 今日涨幅 |",
        f"|------|------|------|----------|----------|",
    ]
    for i, p in enumerate(picks, 1):
        lines.append(f"| {i} | {p.get('code','')} | {p.get('name','')} | {p.get('reason','')} | {p.get('pct','')} |")

    lines.append("")
    lines.append(f"> 以上为AI选股参考，T+1回测结果将于明日收盘后推送")

    return push(f"【选股】{date} 尾盘5只标的", "\n".join(lines))


def push_backtest(date: str, results: list):
    """推送T+1回测结果"""
    total_pct = sum(r.get("pct_change", 0) for r in results)
    avg_pct = total_pct / len(results) if results else 0
    win = sum(1 for r in results if r.get("pct_change", 0) > 0)

    lines = [
        f"## T+1回测 ({date})",
        f"",
        f"**胜率**: {win}/{len(results)} | **平均收益**: {avg_pct:+.2f}%",
        f"",
        f"| 代码 | 名称 | 昨收 | 今开 | 30分钟 | 收盘 | 涨跌幅 | 胜负 |",
        f"|------|------|------|------|--------|------|--------|------|",
    ]
    for r in results:
        win_mark = "✅" if r.get("pct_change", 0) > 0 else "❌"
        lines.append(
            f"| {r.get('code','')} | {r.get('name','')} | {r.get('yesterday_close','')} | "
            f"{r.get('open_price','')} | {r.get('high_30min','')} | {r.get('close_price','')} | "
            f"{r.get('pct_change',''):+.2f}% | {win_mark} |"
        )

    return push(f"【回测】{date} T+1结果", "\n".join(lines))


def push_backtest_comparison(date: str, by_algo: dict):
    """推送T+1回测结果（按算法分组对比）"""
    lines = [f"## T+1回测 ({date})", ""]

    lines.append("### 今日汇总")
    lines.append("")
    lines.append("| 算法 | 胜率 | 平均收益 | 累计收益 |")
    lines.append("|------|------|----------|----------|")
    for algo_ver, results in by_algo.items():
        if not results:
            continue
        wins = sum(1 for r in results if r.get('pct_change', 0) > 0)
        avg = sum(r.get('pct_change', 0) for r in results) / len(results)
        total = sum(r.get('pct_change', 0) for r in results)
        algo_label = algo_ver.replace('_', ' ').title()
        lines.append(f"| {algo_label} | {wins}/{len(results)}={wins/len(results)*100:.0f}% | {avg:+.2f}% | {total:+.2f}% |")
    lines.append("")

    for algo_ver, results in by_algo.items():
        algo_label = algo_ver.replace('_', ' ').title()
        lines.append(f"### {algo_label}")
        lines.append("")
        lines.append("| 代码 | 名称 | 昨收 | 今开 | 30分高 | 收盘 | 涨跌 | 胜负 |")
        lines.append("|------|------|------|------|--------|------|------|------|")
        for r in results:
            win_mark = "✅" if r.get('pct_change', 0) > 0 else "❌"
            lines.append(
                f"| {r.get('code','')} | {r.get('name','')} | "
                f"{r.get('yesterday_close','')} | {r.get('open_price','')} | "
                f"{r.get('high_30min','')} | {r.get('close_price','')} | "
                f"{r.get('pct_change',''):+.2f}% | {win_mark} |"
            )
        lines.append("")

    return push(f"【回测】{date} T+1", "\n".join(lines))


def push_weekly_review(week_range: str, summary: str):
    """推送每周复盘"""
    return push(f"【周复盘】{week_range}", summary)


if __name__ == "__main__":
    push("测试", "如果你收到这条消息，说明推送配置成功！")

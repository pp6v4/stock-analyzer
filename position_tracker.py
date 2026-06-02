# -*- coding: utf-8 -*-
"""
持仓追踪 - 每日盘前/尾盘分析持仓并给出操作建议
可单独运行，也可被morning_brief和daily_pick调用
"""

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import efinance as ef
from datetime import datetime
import time

# 用户持仓
PORTFOLIO = [
    {"code": "000725", "name": "京东方A", "shares": 1400, "cost": 5.30},
    {"code": "002582", "name": "好想你", "shares": 300, "cost": None},
    {"code": "002181", "name": "粤传媒", "shares": 100, "cost": None},
]


def get_snapshot(code: str) -> dict:
    """获取个股实时快照"""
    try:
        snap = ef.stock.get_quote_snapshot(code)
        if snap is None:
            return {}
        return {
            "price": float(snap.get("最新价", 0)),
            "open": float(snap.get("开盘", 0)),
            "high": float(snap.get("最高", 0)),
            "low": float(snap.get("最低", 0)),
            "pct": float(snap.get("涨跌幅", 0)),
            "volume": float(snap.get("成交量", 0)),
            "turnover_rate": float(snap.get("换手率", 0)),
            "sell1_price": snap.get("卖1价", None),
            "sell1_vol": snap.get("卖1数量", None),
            "buy1_price": snap.get("买1价", None),
            "buy1_vol": snap.get("买1数量", None),
        }
    except Exception as e:
        return {"error": str(e)}


def analyze_position(holding: dict, mode: str = "morning") -> dict:
    """
    分析单只持仓
    mode: "morning"(盘前) 或 "afternoon"(尾盘)
    """
    code = holding["code"]
    name = holding["name"]
    shares = holding["shares"]
    cost = holding["cost"]

    snap = get_snapshot(code)
    if not snap or "price" not in snap:
        return {"code": code, "name": name, "error": snap.get("error", "数据获取失败")}

    price = snap["price"]
    pct = snap["pct"]
    high = snap["high"]
    low = snap["low"]
    sell1_vol = snap.get("sell1_vol", 0) or 0
    buy1_vol = snap.get("buy1_vol", 0) or 0

    result = {
        "code": code, "name": name, "shares": shares,
        "price": price, "pct": pct, "high": high, "low": low,
        "buy_vol": buy1_vol, "sell_vol": sell1_vol,
    }

    if cost:
        profit = (price / cost - 1) * 100
        profit_amt = (price - cost) * shares
        result["cost"] = cost
        result["profit_pct"] = round(profit, 2)
        result["profit_amt"] = round(profit_amt, 0)
    else:
        result["cost"] = None

    # === 操作建议生成 ===

    # 粤传媒特殊处理（跌停封死）
    if code == "002181":
        if pct <= -9.5 and buy1_vol == 0:
            result["action"] = "跌停封死，无法卖出"
            result["advice"] = "集合竞价挂跌停价卖出。如果连续3天出不来，等开板日第一时间跑。绝对不补仓。"
            result["urgency"] = "high"
        elif pct <= -5:
            result["action"] = "继续减仓"
            result["advice"] = "趁反弹减仓，不抱幻想。"
            result["urgency"] = "high"
        elif pct > 0:
            result["action"] = "趁反弹卖出"
            result["advice"] = "难得反弹，减仓机会。"
            result["urgency"] = "high"
        else:
            result["action"] = "持有观望"
            result["advice"] = "等待方向。不放量不操作。"
            result["urgency"] = "medium"

    # 好想你（趋势走弱）
    elif code == "002582":
        if cost and profit_pct <= -10:
            result["action"] = "建议止损"
            result["advice"] = "亏损超10%，主力持续流出，不建议死扛。"
            result["urgency"] = "high"
        elif pct > 3:
            result["action"] = "趁反弹减仓"
            result["advice"] = "主力资金未回流，反弹是离场机会。"
            result["urgency"] = "medium"
        elif pct < -3:
            result["action"] = "观望，不补仓"
            result["advice"] = "趋势向下，不加仓。若跌破9.5考虑止损。"
            result["urgency"] = "medium"
        else:
            result["action"] = "持有"
            result["advice"] = "小幅波动，继续观察。"
            result["urgency"] = "low"

    # 京东方A（重点仓位）
    elif code == "000725":
        if profit_pct and profit_pct >= 8:
            result["action"] = "减半仓锁利润"
            result["advice"] = f"浮盈{profit_pct:.1f}%，建议卖出700股锁定利润，剩余博中线。"
            result["urgency"] = "high"
        elif profit_pct and profit_pct >= 3:
            result["action"] = "持有，准备减仓"
            result["advice"] = f"浮盈{profit_pct:.1f}%，关注5.54阻力。突破持有，受阻减半仓。"
            result["urgency"] = "medium"
        elif pct > 0:
            result["action"] = "持有"
            result["advice"] = "趋势向上，继续持有。"
            result["urgency"] = "low"
        elif price < 5.11:
            result["action"] = "⚠️ 止损"
            result["advice"] = "跌破5.11前低，建议减仓或清仓。"
            result["urgency"] = "high"
        elif pct < -3:
            result["action"] = "警惕，观察5.11"
            result["advice"] = "回调中，若跌破5.11执行止损。"
            result["urgency"] = "medium"
        else:
            result["action"] = "持有"
            result["advice"] = "小幅波动，趋势未破。"
            result["urgency"] = "low"

    # 根据盘前/尾盘调整
    if mode == "morning":
        # 盘前更关注准备，不催操作
        if result["urgency"] == "high":
            result["advice"] += "\n今日重点关注此票。"

    return result


def build_report(results: list, mode: str = "morning") -> str:
    """生成持仓报告"""
    now = datetime.now().strftime("%H:%M")

    if mode == "morning":
        title = f"【持仓】盘前分析 ({now})"
        intro = "今日关注价位和操作准备："
    else:
        title = f"【持仓】尾盘操作 ({now})"
        intro = "尾盘实际执行建议："

    lines = [f"## {title}", "", intro, ""]

    # 汇总
    total_value = 0
    total_profit = 0
    for r in results:
        if "price" in r:
            val = r["price"] * r["shares"]
            total_value += val
            if r.get("profit_amt"):
                total_profit += r["profit_amt"]

    lines.append(f"**总市值**: {total_value:,.0f}元 | **总浮盈**: {total_profit:+,.0f}元")
    lines.append("")

    # 逐个分析
    for r in results:
        if "error" in r:
            lines.append(f"### {r['name']}({r['code']})")
            lines.append(f"⚠️ {r['error']}")
            lines.append("")
            continue

        urgency_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(r.get("urgency", "low"), "")
        lines.append(f"### {urgency_icon} {r['name']}({r['code']})")
        lines.append("")
        lines.append(f"| 项目 | 数据 |")
        lines.append(f"|------|------|")
        lines.append(f"| 现价 | {r['price']:.2f} ({r['pct']:+.2f}%) |")
        if r.get("cost"):
            lines.append(f"| 成本 | {r['cost']:.2f} |")
            lines.append(f"| 盈亏 | {r['profit_pct']:+.2f}% ({r['profit_amt']:+.0f}元) |")
        lines.append(f"| 今日区间 | {r['low']:.2f} - {r['high']:.2f} |")
        lines.append(f"| 买卖比 | 买{r['buy_vol']:.0f} / 卖{r['sell_vol']:.0f} |")
        lines.append(f"| 建议 | **{r['action']}** |")
        lines.append("")
        lines.append(r['advice'])
        lines.append("")

    lines.append("> 以上为AI持仓分析，不构成投资建议。")
    return "\n".join(lines)


def run(mode: str = "morning"):
    """运行持仓分析，mode='morning'或'afternoon'"""
    print(f"\n=== 持仓分析 ({mode}) ===\n")

    results = []
    for h in PORTFOLIO:
        print(f"  分析 {h['name']}({h['code']})...")
        r = analyze_position(h, mode)
        results.append(r)
        time.sleep(0.5)

    return results


def run_and_push(mode: str = "morning"):
    """运行并推送"""
    from push_wechat import push as wx_push

    results = run(mode)
    content = build_report(results, mode)

    print(content[:500])

    try:
        title = "持仓盘前" if mode == "morning" else "持仓尾盘"
        wx_push(f"【{title}】{datetime.now().strftime('%m-%d')}", content)
        print(f"\n[PUSH] {title}报告已推送")
    except Exception as e:
        print(f"\n[PUSH ERROR] {e}")

    return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["morning", "afternoon"], default="afternoon")
    args = parser.parse_args()
    run_and_push(args.mode)

# -*- coding: utf-8 -*-
"""
观察清单 - 验证分析框架的跟踪案例
不参与选股/回测主流程，每日复盘时手动查看
"""

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import efinance as ef
from datetime import datetime
import time

# ============================================================
# 案例1: 粤传媒(002181) — 烂板出货识别验证
# ============================================================
#
# 分析日期: 2026-06-03
# 核心逻辑: 6/1涨停是"烂板出货"（4次炸板+尾盘封+3900万假封单+13%换手）
#           → 6/2跌停 → 6/3开板
# 后市判断: 大概率复制第一轮崩盘路径，目标12.50-13.00
#           A(50%): 续跌3-5天到12.50-13.00
#           B(30%): 14.50-16.00横盘
#           C(20%): V型反转
#
# 验证节点:
#   6/4: 收盘<15.00 → A确认 / 站上16.34 → C可能
#   6/5: 跌破14.00 → A加速
#   6/8: 目标12.50-13.00 vs 实际情况
#
# 教训: K线图上的涨停阳线会骗人，封板微观数据不会

CASE_1 = {
    "code": "002181",
    "name": "粤传媒",
    "analysis_date": "2026-06-03",
    "entry_context": "6/1下午追涨停买入(18.16)，6/3开板卖出(~14.80)",
    "core_logic": "烂板出货识别 — 6/1涨停数据: 4次炸板、封板资金3900万(占成交1.5%)、最后封板14:44、换手13.13%",
    "prediction": "A路径(50%): 续跌3-5天→12.50-13.00 | B(30%): 14.50-16.00横盘 | C(20%): V型反转",
    "key_levels": {
        "entry": 18.16,
        "exit": 14.80,
        "target_low": 12.50,
        "support_1": 14.71,  # 6/3低点
        "resistance_1": 16.34,  # 6/2跌停价
        "resistance_2": 17.20,  # 6/3高点
    },
    "verification_nodes": {
        "6/4": "收盘<15.00→A确认 | 站上16.34→C可能",
        "6/5": "跌破14.00→A加速",
        "6/8": "是否到达12.50-13.00目标区",
    },
    "daily_log": [],
}

# ============================================================
# 案例2: 豫能股份(001896) — 箱体波段/量化做T验证
# ============================================================
#
# 分析日期: 2026-06-03
# 核心逻辑: 近3个月在上升通道内做箱体震荡，每轮振幅20-30%
#           箱底从12.63→13.90→14.38逐步上移
#           箱顶在17-19区间反复测试
# 本次操作: 6/1在17.65提前卖出，错过后续到20.08的涨幅(+13.7%)
# 问题: 执行偏离了"19-20才卖"的规则，被盘中冲高回落干扰
#
# 波段网格建议:
#   卖出3/3: 19.50-20.00
#   卖出2/3: 18.50-19.00
#   卖出1/3: 17.50-18.00
#   持有:     16.00-17.00
#   买入1/3: 15.00-15.50
#   买入2/3: 14.50-15.00
#   买入3/3: 14.00-14.50
#   止损:     跌破13.80
#
# 验证目标: 这个网格规则在未来1-2个月内是否有效
#          今天涨停20.08突破箱顶，是真突破还是又要闷人？

CASE_2 = {
    "code": "001896",
    "name": "豫能股份",
    "analysis_date": "2026-06-03",
    "entry_context": "长期观察3个月，6/1在17.65提前清仓",
    "core_logic": "上升通道箱体震荡 — 箱底12.63→13.90→14.38(逐步上移) | 箱顶17-19(反复测试)",
    "prediction": "6/3涨停20.08突破箱顶 — 65%概率假突破(次日闷杀) | 35%概率真突破(回踩20后冲22-24)",
    "key_levels": {
        "last_sell": 17.65,
        "today_close": 20.08,
        "box_bottom": 14.50,  # 最近一次箱底
        "box_top_old": 19.40,  # 前几次箱顶
        "grid_buy_1": 15.00,
        "grid_buy_2": 14.50,
        "grid_sell_1": 17.50,
        "grid_sell_2": 19.00,
        "grid_sell_3": 20.00,
        "stop_loss": 13.80,
    },
    "verification_nodes": {
        "6/4": "是否高开低走/跌停(假突破) | 是否站稳20上方(真突破)",
        "6/5": "回踩深度 — 20.00支撑 vs 回到17-18区间",
        "持续": "网格规则是否在2个月内有效",
    },
    "daily_log": [],
}


def check_today(case: dict) -> dict:
    """获取个股今日快照并记录"""
    code = case["code"]
    name = case["name"]
    try:
        snap = ef.stock.get_quote_snapshot(code)
        if snap is None or snap.empty:
            return {"error": "快照为空"}

        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "price": float(snap.get("最新价", 0)),
            "open": float(snap.get("开盘", 0)),
            "high": float(snap.get("最高", 0)),
            "low": float(snap.get("最低", 0)),
            "pct": float(snap.get("涨跌幅", 0)),
            "volume": float(snap.get("成交量", 0)),
            "turnover": float(snap.get("换手率", 0)),
            "buy1_vol": float(snap.get("买1数量", 0) or 0),
            "sell1_vol": float(snap.get("卖1数量", 0) or 0),
        }
    except Exception as e:
        return {"error": str(e)}


def format_case_report(case: dict, snap: dict) -> str:
    """格式化单个案例的日报"""
    name = case["name"]
    code = case["code"]
    kl = case["key_levels"]

    lines = [f"### {name}({code})"]

    if "error" in snap:
        lines.append(f"⚠️ 数据获取失败: {snap['error']}")
        return "\n".join(lines)

    lines.append("")
    lines.append(f"| 项目 | 数据 |")
    lines.append(f"|------|------|")
    lines.append(f"| 现价 | {snap['price']:.2f} ({snap['pct']:+.2f}%) |")
    lines.append(f"| 今日区间 | {snap['low']:.2f} - {snap['high']:.2f} |")
    lines.append(f"| 换手率 | {snap['turnover']:.2f}% |")
    lines.append(f"| 买卖盘 | 买{snap['buy1_vol']:.0f} / 卖{snap['sell1_vol']:.0f} |")

    # Key levels relevant to this case
    if "entry" in kl:
        chg = (snap['price'] / kl['entry'] - 1) * 100
        lines.append(f"| 相对入场(18.16) | {chg:+.1f}% |")
    if "exit" in kl:
        chg = (snap['price'] / kl['exit'] - 1) * 100
        lines.append(f"| 相对离场(14.80) | {chg:+.1f}% |")
    if "last_sell" in kl:
        chg = (snap['price'] / kl['last_sell'] - 1) * 100
        lines.append(f"| 相对卖出(17.65) | {chg:+.1f}% |")
    if "box_bottom" in kl:
        dist = (snap['price'] / kl['box_bottom'] - 1) * 100
        lines.append(f"| 距箱底({kl['box_bottom']}) | {dist:+.1f}% |")
    if "box_top_old" in kl:
        dist = (snap['price'] / kl['box_top_old'] - 1) * 100
        lines.append(f"| 距旧箱顶({kl['box_top_old']}) | {dist:+.1f}% |")

    lines.append("")
    return "\n".join(lines)


def generate_report() -> str:
    """生成观察清单日报"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"## 🔍 观察清单日报 ({now})",
        "",
        "> 以下为分析框架验证案例，非持仓，仅追踪逻辑",
        "",
    ]

    for case in [CASE_1, CASE_2]:
        print(f"  检查 {case['name']}({case['code']})...")
        snap = check_today(case)
        lines.append(format_case_report(case, snap))
        time.sleep(0.3)

    lines.append("---")
    lines.append("> 观察清单 | 验证分析框架 | 不构成投资建议")
    return "\n".join(lines)


def push_report():
    """推送到微信"""
    from push_wechat import push as wx_push
    content = generate_report()
    print(content[:600])
    print("...")
    try:
        wx_push("【观察清单】" + datetime.now().strftime("%m-%d"), content)
        print("[PUSH] OK")
    except Exception as e:
        print(f"[PUSH ERROR] {e}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--push", action="store_true", help="推送到微信")
    args = parser.parse_args()

    if args.push:
        push_report()
    else:
        print(generate_report())

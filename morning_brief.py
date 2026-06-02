# -*- coding: utf-8 -*-
"""
晨报脚本 v1.0 - 每交易日9:00运行
灵感来源: financial-services/equity-research/morning-note skill

生成盘前简报：前日涨停复盘 + 隔夜消息 + 今日关注方向
"""

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from datetime import datetime, timedelta
import time

from data_fetcher import get_limit_up_stocks, get_continuous_limit_up, get_stock_kline
from push_wechat import push as wx_push


def get_previous_trading_day() -> str:
    """获取上一个交易日"""
    today = datetime.now()
    # 简单处理：周一到周五的前一日
    if today.weekday() == 0:  # 周一
        prev = today - timedelta(days=3)
    elif today.weekday() == 6:  # 周日
        prev = today - timedelta(days=2)
    elif today.weekday() == 5:  # 周六
        prev = today - timedelta(days=1)
    else:
        prev = today - timedelta(days=1)
    return prev.strftime('%Y%m%d')


def run():
    date = datetime.now().strftime('%Y%m%d')
    prev_date = get_previous_trading_day()
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M')

    print(f"\n=== 盘前简报 ({now_str}) ===\n")

    # 1. 前日涨停复盘
    print("[1/3] 前日涨停复盘...")
    try:
        zt = get_limit_up_stocks(prev_date)
        zt_count = len(zt) if not zt.empty else 0
    except:
        zt_count = 0

    # 2. 大盘状态
    print("[2/3] 大盘状态...")
    market_status = "数据获取失败"
    sh_pct = 0
    try:
        sh = get_stock_kline('000001', days=3)
        if sh is not None and not sh.empty and len(sh) >= 2:
            close_col = '收盘' if '收盘' in sh.columns else [c for c in sh.columns if '收' in c][0]
            closes = [float(x) for x in sh[close_col].tail(2)]
            sh_pct = (closes[-1] / closes[-2] - 1) * 100 if closes[-2] != 0 else 0
            if sh_pct > 1:
                market_status = "强势"
            elif sh_pct > -1:
                market_status = "震荡"
            else:
                market_status = "偏弱"
    except:
        pass

    # 3. 连板天梯
    print("[3/3] 连板情况...")
    try:
        strong = get_continuous_limit_up()
        strong_count = len(strong) if not strong.empty else 0
    except:
        strong_count = 0

    # === 构建简报 ===
    lines = [
        f"## 盘前简报 ({now_str})",
        f"",
        f"### 市场状态",
        f"- 上证前日: {sh_pct:+.2f}% ({market_status})",
        f"- 前日涨停: {zt_count}只",
        f"- 强势股数: {strong_count}只",
        f"",
        f"### 今日关注",
        f"- 前日主线板块是否延续",
        f"- 开盘30分钟量能对比",
        f"- 高位连板股溢价情况",
        f"",
    ]

    # === 持仓分析（嵌入） ===
    try:
        from position_tracker import run, build_report
        pos_results = run(mode="morning")
        pos_content = build_report(pos_results, mode="morning")
        # 去掉第一个标题行（避免重复），追加到简报后面
        pos_lines = pos_content.split("\n")
        lines.extend(pos_lines[1:])  # 跳过 "## 持仓盘前分析" 标题
    except Exception as e:
        lines.append(f"⚠️ 持仓数据获取失败: {e}")
        lines.append("")

    content = "\n".join(lines)
    print(content)

    try:
        wx_push(f"【盘前】{prev_date}", content)
        print("[PUSH] 简报已推送")
    except Exception as e:
        print(f"[PUSH ERROR] {e}")


if __name__ == "__main__":
    run()

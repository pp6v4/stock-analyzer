# -*- coding: utf-8 -*-
"""
晨报脚本 v1.1 - 每交易日9:00运行
优先读取前日收盘快照（本地），API降级，都失败则不发
"""

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from datetime import datetime, timedelta
import os

from market_snapshot import load_snapshot
from push_wechat import push as wx_push


def get_previous_trading_day() -> str:
    """获取上一个交易日"""
    today = datetime.now()
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
    prev_date = get_previous_trading_day()
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M')

    print(f"\n=== 盘前简报 ({now_str}) ===\n")

    # 1. 尝试加载快照
    snapshot = load_snapshot(prev_date)
    zt_count = 0
    strong_count = 0
    sh_pct = 0
    market_status = "数据获取失败"
    used_snapshot = False

    if snapshot:
        print("[快照] 使用本地缓存数据")
        used_snapshot = True
        zt_count = snapshot.get("limit_up_count", 0)
        strong_count = snapshot.get("strong_count", 0)

        kline = snapshot.get("sh_kline", [])
        if kline and len(kline) >= 2:
            closes = [d["close"] for d in kline[-2:]]
            if closes[-2] != 0:
                sh_pct = (closes[-1] / closes[-2] - 1) * 100
            if sh_pct > 1:
                market_status = "强势"
            elif sh_pct > -1:
                market_status = "震荡"
            else:
                market_status = "偏弱"
    else:
        # 2. 快照不存在，降级到实时API
        print("[API] 快照缺失，降级为实时API...")
        from data_fetcher import get_limit_up_stocks, get_continuous_limit_up, get_stock_kline

        try:
            zt = get_limit_up_stocks(prev_date)
            zt_count = len(zt) if not zt.empty else 0
        except:
            zt_count = 0

        try:
            sh = get_stock_kline("000001", days=3)
            if sh is not None and not sh.empty and len(sh) >= 2:
                close_col = "收盘" if "收盘" in sh.columns else [c for c in sh.columns if "收" in c][0]
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

        try:
            strong = get_continuous_limit_up()
            strong_count = len(strong) if not strong.empty else 0
        except:
            strong_count = 0

    # 3. 昨日选股回顾
    picks_lines = []
    try:
        from stock_db import get_picks_by_date
        picks = get_picks_by_date(prev_date)
        if picks:
            from collections import defaultdict
            by_algo = defaultdict(list)
            for p in picks:
                by_algo[p["algo_version"]].append(p)

            picks_lines.append("### 昨日选股回顾")
            picks_lines.append("")
            algo_names = {"v1_baseline": "V1基础", "v2_enhanced": "V2增强", "v3_adaptive": "V3自适应", "v4_quant": "V4量化"}
            for algo, ps in sorted(by_algo.items()):
                label = algo_names.get(algo, algo)
                stock_list = "、".join(f"{p['stock_name']}({p['stock_code'][:6]})" for p in ps[:5])
                picks_lines.append(f"- **{label}**: {stock_list}")
            picks_lines.append("")
            print(f"[DB] 昨日选股: {len(picks)} 只, {len(by_algo)} 个算法")
    except Exception as e:
        print(f"[DB WARN] 选股回顾获取失败: {e}")

    # 4. 都拿不到数据就不发
    if zt_count == 0 and strong_count == 0 and market_status == "数据获取失败":
        print("[SKIP] 无有效数据，跳过推送")
        return

    # === 构建简报 ===
    lines = [
        f"## 盘前简报 ({now_str})",
        "",
        f"### 市场状态",
        f"- 上证前日: {sh_pct:+.2f}% ({market_status})",
        f"- 前日涨停: {zt_count}只",
        f"- 强势股数: {strong_count}只",
        "",
    ]
    lines.extend(picks_lines)
    lines.extend([
        f"### 今日关注",
        f"- 前日主线板块是否延续",
        f"- 开盘30分钟量能对比",
        f"- 高位连板股溢价情况",
        "",
    ])

    # === 持仓分析 ===
    try:
        from position_tracker import run as pos_run, build_report
        pos_results = pos_run(mode="morning")
        pos_content = build_report(pos_results, mode="morning")
        pos_lines = pos_content.split("\n")
        lines.extend(pos_lines[1:])
    except Exception as e:
        lines.append(f"持仓数据获取失败: {e}")
        lines.append("")

    content = "\n".join(lines)
    print(content[:800])

    try:
        wx_push(f"【盘前】{prev_date}", content)
        print("[PUSH] 简报已推送")
    except Exception as e:
        print(f"[PUSH ERROR] {e}")


if __name__ == "__main__":
    run()

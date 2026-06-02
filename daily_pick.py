# -*- coding: utf-8 -*-
"""
每日选股 v1.1 - 多算法并行 + 大盘过滤
14:30自动运行 → 大盘检查 → 选股 → 入库 → 推微信

变更(v1.1):
- 新增周末/节假日自动跳过
- 新增上证指数5日趋势过滤（大盘弱势暂停选股）
- 市场状态评估结果推送到微信
"""

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import pandas as pd
from datetime import datetime, timedelta
import traceback

from data_fetcher import get_limit_up_stocks, get_continuous_limit_up, get_stock_kline
from algorithms import select_stocks, list_versions
from push_wechat import push as wx_push
from stock_db import save_picks


# A股节假日列表（2026年，可扩展）
A_STOCK_HOLIDAYS_2026 = {
    '20260101', '20260102',  # 元旦
    '20260216', '20260217', '20260218', '20260219', '20260220',  # 春节
    '20260406',  # 清明节
    '20260501', '20260504', '20260505',  # 劳动节
    '20260619',  # 端午节
    '20260928', '20260929', '20260930',  # 中秋+国庆
    '20261001', '20261002', '20261005', '20261006', '20261007', '20261008',
}


def is_trading_day() -> tuple:
    """
    判断今天是否为交易日
    返回: (is_trading, reason)
    """
    today = datetime.now()
    date_str = today.strftime('%Y%m%d')

    # 周末
    if today.weekday() >= 5:
        return False, f"周末（{['周一','周二','周三','周四','周五','周六','周日'][today.weekday()]}），暂停选股"

    # 节假日
    if date_str in A_STOCK_HOLIDAYS_2026:
        return False, "节假日，暂停选股"

    # 时间检查：14:30之前不运行（防止手动误触发时拉不到当日数据）
    # 这里不强制，计划任务14:30触发即可

    return True, "交易日"


def check_market_health() -> tuple:
    """
    大盘健康检查
    拉上证指数近5日K线，判断是否适合选股
    返回: (is_healthy, market_status_text, market_score)
    """
    try:
        sh = get_stock_kline('000001', days=5)
        if sh is None or sh.empty or len(sh) < 3:
            return True, "大盘数据不足，跳过过滤", 0

        # 找收盘价列
        close_col = '收盘' if '收盘' in sh.columns else [c for c in sh.columns if '收' in c][0]
        closes = pd.to_numeric(sh[close_col], errors='coerce')

        if len(closes) < 3:
            return True, "数据不足", 0

        # 计算近5日累计涨跌幅
        pct_5d = (closes.iloc[-1] / closes.iloc[0] - 1) * 100

        # 连续下跌天数
        down_days = 0
        for i in range(len(closes) - 1, 0, -1):
            if closes.iloc[i] < closes.iloc[i - 1]:
                down_days += 1
            else:
                break

        # 判断
        status_parts = [f"上证近5日: {pct_5d:+.2f}%", f"连跌{days}天" if (days := down_days) > 1 else ""]

        if pct_5d < -5:
            return False, f"大盘5日跌{pct_5d:.1f}%，严重弱势，暂停选股", -30
        elif pct_5d < -3:
            return False, f"大盘5日跌{pct_5d:.1f}%，弱势环境，暂停选股", -20
        elif down_days >= 4:
            return False, f"大盘连跌{down_days}天，风险较高，暂停选股", -15
        elif pct_5d < -1:
            return True, f"大盘5日跌{pct_5d:.1f}%，偏弱但可操作", -10
        elif pct_5d > 2:
            return True, f"大盘5日涨{pct_5d:.1f}%，强势环境", 15
        else:
            return True, f"大盘5日{pct_5d:+.2f}%，正常", 0

    except Exception as e:
        print(f"[WARN] 大盘检查失败: {e}")
        return True, "大盘检查异常，继续选股", 0


def run(date: str, algo_versions: list = None):
    """
    运行选股
    algo_versions: 要运行的算法版本列表，默认全部
    """
    if algo_versions is None:
        algo_versions = list_versions()

    print(f"\n{'='*60}")
    print(f"  每日选股 v1.1 ({date} {datetime.now().strftime('%H:%M')})")
    print(f"{'='*60}\n")

    # === 0. 交易日检查 ===
    is_trading, trade_reason = is_trading_day()
    if not is_trading:
        print(f"[SKIP] {trade_reason}")
        return {}

    # === 1. 大盘健康检查 ===
    print("[0/4] 大盘健康检查...")
    market_ok, market_status, market_score = check_market_health()
    print(f"      {market_status}")

    if not market_ok:
        print("[SKIP] 大盘弱势，今日暂停选股")
        wx_push(
            f"【选股暂停】{date}",
            f"## 今日暂停选股\n\n**原因**: {market_status}\n\n"
            f"大盘环境不佳时强行选股胜率低，等待市场企稳后恢复。"
        )
        return {}

    # === 2. 拉数据 ===
    print("[1/4] 市场数据...")
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
        wx_push(f"【选股异常】{date}", "今日强势股数据为空，可能非交易日或接口异常")
        return {}

    print(f"      涨停{len(zt_codes)}只, 强势股{len(strong)}只, 活跃板块{len(sector_counts)}个\n")
    print(f"      市场状态: {market_status}\n")

    # === 3. 算法选股 ===
    print("[2/4] 算法选股...\n")
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

    # === 4. 保存 + 推送 ===
    print("[3/4] 保存...")
    for algo_ver, picks in all_picks.items():
        if picks:
            save_picks(picks)
            print(f"  [{algo_ver}] DB保存 {len(picks)} 条")

    print("[4/4] 推送微信...")
    push_combined(date, all_picks, len(zt_codes), market_status, market_score)

    return all_picks


def push_combined(date: str, all_picks: dict, zt_count: int, market_status: str, market_score: int):
    """合并推送选股结果（含大盘状态）"""
    # 大盘状态图标
    if market_score > 0:
        market_icon = "🟢"
    elif market_score > -15:
        market_icon = "🟡"
    else:
        market_icon = "🔴"

    lines = [
        f"## 今日选股 ({date})",
        f"",
        f"{market_icon} **大盘**: {market_status}",
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

    lines.append("> V1=基础版 | V2=增强版 | V3=自适应版 | V4=多因子量化版")
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
        wx_push("【选股异常】", f"选股脚本报错:\n```\n{traceback.format_exc()}\n```")


if __name__ == "__main__":
    main()

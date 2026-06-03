# -*- coding: utf-8 -*-
"""
收盘快照模块 - 在15:05回测后将盘前简报所需数据固化到本地
morning_brief.py 早上直接读本地文件，不再依赖实时API
"""

import json
import os
from datetime import datetime, timedelta
from data_fetcher import get_limit_up_stocks, get_continuous_limit_up
import akshare as ak

SNAPSHOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
SNAPSHOT_FILE = os.path.join(SNAPSHOT_DIR, "market_snapshot.json")


def save_snapshot(date: str = None):
    """收盘后保存快照"""
    if date is None:
        date = datetime.now().strftime("%Y%m%d")

    os.makedirs(SNAPSHOT_DIR, exist_ok=True)

    print(f"\n=== 收盘快照 ({date}) ===\n")

    snapshot = {"date": date, "saved_at": datetime.now().isoformat()}

    # 1. 涨停板
    print("[1/3] 涨停板...")
    try:
        zt = get_limit_up_stocks(date)
        snapshot["limit_up"] = zt.to_dict(orient="records") if not zt.empty else []
        snapshot["limit_up_count"] = len(zt) if not zt.empty else 0
        print(f"      {snapshot['limit_up_count']} 只")
    except Exception as e:
        print(f"      [WARN] {e}")
        snapshot["limit_up"] = []
        snapshot["limit_up_count"] = 0

    # 2. 上证指数K线
    print("[2/3] 大盘K线...")
    try:
        sh = ak.stock_zh_index_daily(symbol="sh000001")
        if sh is not None and not sh.empty:
            sh = sh.tail(3)
            kline_data = []
            for _, row in sh.iterrows():
                kline_data.append({
                    "date": str(row.get("date", "")),
                    "open": float(row.get("open", 0)),
                    "close": float(row.get("close", 0)),
                    "high": float(row.get("high", 0)),
                    "low": float(row.get("low", 0)),
                    "volume": float(row.get("volume", 0)),
                })
            snapshot["sh_kline"] = kline_data
            print(f"      {len(kline_data)} 条")
        else:
            snapshot["sh_kline"] = []
            print("      无数据")
    except Exception as e:
        print(f"      [WARN] {e}")
        snapshot["sh_kline"] = []

    # 3. 连板天梯
    print("[3/3] 连板天梯...")
    try:
        strong = get_continuous_limit_up()
        snapshot["continuous_limit_up"] = strong.to_dict(orient="records") if not strong.empty else []
        snapshot["strong_count"] = len(strong) if not strong.empty else 0
        print(f"      {snapshot['strong_count']} 只")
    except Exception as e:
        print(f"      [WARN] {e}")
        snapshot["continuous_limit_up"] = []
        snapshot["strong_count"] = 0

    # 写入
    with open(SNAPSHOT_FILE, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)

    print(f"\n[OK] 快照已保存: {SNAPSHOT_FILE}")
    return snapshot


def load_snapshot(expected_date: str = None) -> dict:
    """加载最近的快照，如果日期匹配则返回"""
    if not os.path.exists(SNAPSHOT_FILE):
        return None

    try:
        with open(SNAPSHOT_FILE, "r", encoding="utf-8") as f:
            snapshot = json.load(f)
    except Exception:
        return None

    if expected_date and snapshot.get("date") != expected_date:
        return None

    return snapshot


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=str, default=None, help="日期 YYYYMMDD，默认今天")
    args = parser.parse_args()
    save_snapshot(args.date)

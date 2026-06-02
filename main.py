# -*- coding: utf-8 -*-
"""
A股短线分析工具
用法:
  python main.py              # 拉数据 + 生成分析报告
  python main.py --live       # 拉数据并在控制台输出完整prompt
  python main.py --code 000001  # 拉某只股票的K线数据
"""

import argparse
import sys
import io

# 修复Windows控制台中文输出问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')


def main():
    parser = argparse.ArgumentParser(description="A股短线分析")
    parser.add_argument("--live", action="store_true", help="直接在控制台输出分析数据")
    parser.add_argument("--code", type=str, help="查看指定股票K线")
    parser.add_argument("--output", type=str, default=None, help="报告输出路径")
    args = parser.parse_args()

    from data_fetcher import fetch_all, get_stock_kline
    from analyzer import build_analysis_prompt, save_report, save_raw_data

    if args.code:
        print(f"[INFO] 拉取 {args.code} K线数据...")
        df = get_stock_kline(args.code)
        if not df.empty:
            print(df.tail(30).to_string())
        else:
            print("[WARN] 未获取到数据，请确认代码（如 000001）")
        return

    print("[INFO] 正在拉取全市场短线数据...\n")
    data = fetch_all()

    save_raw_data(data)

    prompt = build_analysis_prompt(data)
    report_path = save_report(prompt, args.output)

    if args.live:
        print("\n" + "=" * 60)
        print(prompt)

    print(f"\n[DONE] 报告路径: {report_path}")
    print("[TIP] 把报告内容贴到Claude对话中让我帮你分析")


if __name__ == "__main__":
    main()

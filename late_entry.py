"""尾盘潜伏选股：找主线板块中还没涨停的强势股"""
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import akshare as ak
import pandas as pd
from datetime import datetime
import time

pd.set_option('display.max_columns', 20)
pd.set_option('display.width', 200)
pd.set_option('display.max_colwidth', 20)

print(f"=== 尾盘潜伏选股 ({datetime.now().strftime('%H:%M')}) ===\n")

# 1. 先拿强势股池（含未涨停的活跃股）
print("[1] 拉取强势股池...")
try:
    strong = ak.stock_zt_pool_strong_em(date=datetime.now().strftime('%Y%m%d'))
    print(f"    共 {len(strong)} 只强势股")
except Exception as e:
    print(f"    失败: {e}")
    strong = pd.DataFrame()

# 2. 拉涨停板列表
print("[2] 拉取涨停板...")
try:
    zt = ak.stock_zt_pool_em(date=datetime.now().strftime('%Y%m%d'))
    zt_codes = set(zt['代码'].tolist()) if not zt.empty else set()
    print(f"    共 {len(zt_codes)} 只涨停")
except Exception as e:
    print(f"    失败: {e}")
    zt_codes = set()

# 3. 从强势股中筛出未涨停的
if not strong.empty:
    print("\n[3] 筛选未涨停强势股...")
    # 列名映射
    code_col = '代码' if '代码' in strong.columns else strong.columns[0]

    strong['is_zt'] = strong[code_col].apply(lambda x: str(x) in zt_codes)
    non_zt = strong[~strong['is_zt']].copy()

    # 按涨跌幅排序
    pct_col = '涨跌幅' if '涨跌幅' in non_zt.columns else [c for c in non_zt.columns if '涨跌' in c][0]
    non_zt = non_zt.sort_values(pct_col, ascending=False)

    print(f"    未涨停强势股: {len(non_zt)} 只")
    print(f"\n    === 涨5%-9%之间的潜在标的（有尾盘封板可能） ===\n")

    mid = non_zt[(non_zt[pct_col] >= 5) & (non_zt[pct_col] <= 9.5)]

    show_cols = [c for c in ['代码','名称',pct_col,'涨停统计','所属行业'] if c in non_zt.columns]
    if not mid.empty:
        print(mid.head(30)[show_cols].to_string())
    else:
        print("    （无5-9%区间个股，展示全部未涨停强势股前30）")
        print(non_zt.head(30)[show_cols].to_string())

# 4. 拉主线板块成分股 -- 元件、通信设备、光学光电
print("\n\n[4] 拉取主线板块成分股（元件/通信/光电）...")

hot_sectors = {
    '元件': None,
    '通信设备': None,
    '光学光电': None,
    '消费电子': None,
    '自动化设备': None,
}

for sector_name in hot_sectors:
    try:
        df = ak.stock_board_industry_cons_em(symbol=sector_name)
        hot_sectors[sector_name] = df
        print(f"    {sector_name}: {len(df)} 只成分股")
        time.sleep(0.5)
    except Exception as e:
        print(f"    {sector_name}: 拉取失败")
        time.sleep(1)

# 5. 从主线板块中找放量上涨但未涨停的个股
print("\n[5] 板块内筛选：涨幅3%-7% + 放量的个股...\n")

for sector_name, df in hot_sectors.items():
    if df is None or df.empty:
        continue

    # 过滤已涨停
    code_col = '代码' if '代码' in df.columns else df.columns[0]
    df['is_zt'] = df[code_col].apply(lambda x: str(x) in zt_codes)
    candidates = df[~df['is_zt']].copy()

    # 找涨幅在3-7%之间的
    pct_col = None
    for c in ['涨跌幅', '涨幅', '最新价']:
        if c in candidates.columns:
            pct_col = c
            break

    if pct_col is None:
        continue

    try:
        candidates[pct_col] = pd.to_numeric(candidates[pct_col], errors='coerce')
        up_stocks = candidates[(candidates[pct_col] >= 3) & (candidates[pct_col] <= 7.5)]

        if not up_stocks.empty:
            show_cols = [c for c in ['代码','名称',pct_col,'换手率','量比','成交额'] if c in up_stocks.columns]
            print(f"--- {sector_name}（{len(up_stocks)}只候选）---")
            print(up_stocks.head(10)[show_cols].to_string())
            print()
    except Exception as e:
        print(f"    {sector_name}: 处理失败 - {e}")

print("\n=== 筛选完成 ===")

"""尾盘选股脚本"""
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from data_fetcher import get_limit_up_stocks, get_continuous_limit_up, get_hot_rank, get_industry_rank
from datetime import datetime

date = datetime.now().strftime('%Y%m%d')
print(f"=== 尾盘数据 ({datetime.now().strftime('%H:%M')}) ===\n")

print("--- 涨停板列表 ---")
lu = get_limit_up_stocks(date)
if not lu.empty:
    cols = ['代码', '名称', '涨跌幅', '连板数', '首次封板时间', '炸板次数', '涨停统计', '所属行业']
    available = [c for c in cols if c in lu.columns]
    print(lu.head(40)[available].to_string())
else:
    print("无数据")

print("\n--- 连板天梯(前30) ---")
cl = get_continuous_limit_up()
if not cl.empty:
    show = [c for c in ['代码', '名称', '涨跌幅', '涨停统计', '所属行业'] if c in cl.columns]
    print(cl.head(30)[show].to_string())

print("\n--- 行业涨幅 ---")
ind = get_industry_rank()
if not ind.empty:
    print(ind.head(15).to_string())

print("\n--- 热度排行(前20) ---")
hot = get_hot_rank()
if not hot.empty:
    print(hot.head(20).to_string())

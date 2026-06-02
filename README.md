# A股短线选股分析系统

基于Python + akshare + AI的A股短线选股系统。每日14:30自动选股，T+1回测，周五周复盘，微信推送。

## 快速开始

```bash
pip install akshare efinance pandas requests
python daily_pick.py     # 手动选股
python daily_backtest.py # T+1回测
python weekly_review.py  # 周复盘
```

## 自动化流程

| 时间 | 脚本 | 功能 |
|------|------|------|
| 每日 14:30 | `daily_pick.py` | 大盘检查 → 多算法选股 → 推微信 |
| 每日 15:05 | `daily_backtest.py` | T+1回测前日选股 → 推微信 |
| 每周五 15:30 | `weekly_review.py` | 算法PK → 宣布优胜 → 推微信 |

### 大盘保护（v1.1新增）
- 周末和A股节假日自动跳过
- 上证指数近5日跌超3% → 暂停选股
- 连跌4天以上 → 暂停选股

## 项目结构

```
stock-analyzer/
├── daily_pick.py        # 每日选股主脚本
├── daily_backtest.py    # T+1回测脚本
├── weekly_review.py     # 周复盘（算法PK）
├── algorithms.py        # 算法版本管理
├── data_fetcher.py      # akshare数据接口
├── analyzer.py          # 数据格式化
├── push_wechat.py       # Server酱微信推送
├── stock_db.py          # SQLite数据库操作
├── single_stock.py      # 单股深度分析
├── setup_schedule.ps1   # Windows计划任务配置
├── main.py              # 全市场数据拉取
├── CHANGELOG.md         # 版本变更记录
└── data/
    └── stock_records.db # 选股记录（自动创建）
```

## 选股算法

系统使用多版本并行算法，每周PK淘汰：

### V1 基础版
追板块效应 + 涨停基因，偏进攻

### V2 增强版
V1基础上 + 量能因子 + 市值偏好，偏风控

### V3 自适应版（最新）
V2基础上 + 封板质量（炸板次数、封板时间），综合平衡

## 配置微信推送

1. 访问 [Server酱](https://sct.ftqq.com) 注册获取 SendKey
2. 在项目根目录创建 `.sendkey` 文件，写入你的 SendKey
3. 运行 `python -c "from push_wechat import push; push('测试','OK')"` 验证

`.sendkey` 已加入 `.gitignore`，不会被提交。

## 添加新算法

在 `algorithms.py` 中添加新函数：

```python
@register("v4_myalgo")
def score_v4(row, sector_counts, zt_codes):
    score = 0
    # 你的打分逻辑
    return score
```

下次选股自动并行运行，周五自动PK。

## 计划任务

```powershell
# 配置（管理员终端）
.\setup_schedule.ps1

# 查看
taskschd.msc  → 搜索"A股"
```

## 常用命令

```bash
# 单股分析
python single_stock.py 000725

# 指定日期回测
python daily_backtest.py --date 2026-06-02

# 测试微信推送
python -c "from push_wechat import push; push('test','hello')"

# 查看数据库
python -c "from stock_db import *; print(get_all_time_stats())"
```

## 环境要求

- Python 3.10+
- Windows 10/11（计划任务依赖）
- 网络（拉取东方财富/同花顺数据）

## 数据源

- [akshare](https://github.com/akfamily/akshare) - 开源金融数据接口
- 东方财富 - 涨停板、龙虎榜、热度排行
- 同花顺 - 概念板块、行业板块

## License

MIT

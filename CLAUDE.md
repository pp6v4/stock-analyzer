# A股短线选股分析系统

每日14:30自动选股 + 次日T+1回测 + 周五周复盘 + 微信推送。

## 触发条件
用户提到"选股"、"龙头"、"涨停"、"回测"、"复盘"、"A股"等关键词时加载此skill。

## 项目结构
```
stock-analyzer/
├── daily_pick.py        # 每日选股（V1+V2双算法并行）
├── daily_backtest.py    # T+1回测
├── weekly_review.py     # 周五周复盘（算法PK）
├── algorithms.py        # 算法版本管理（注册新版本）
├── data_fetcher.py      # akshare数据拉取
├── analyzer.py          # 数据→prompt格式化
├── push_wechat.py       # Server酱微信推送
├── stock_db.py          # SQLite数据库
├── single_stock.py      # 单股深度分析
├── tail_session.py      # 尾盘选股（手动）
├── setup_schedule.ps1   # 配置Windows计划任务
└── data/
    └── stock_records.db # 选股+回测记录
```

## 自动化流程
| 时间 | 任务 | 说明 |
|------|------|------|
| 每日14:30 | daily_pick.py | V1/V2各选5只→推微信 |
| 每日15:05 | daily_backtest.py | 前日选股vs实际→推微信 |
| 周五15:30 | weekly_review.py | V1vsV2 PK+胜者+推微信 |

## 算法版本
- **V1基础版**: 板块效应(50) + 涨幅位置(25) + 涨停基因(25) + 可买性(10)
- **V2增强版**: 板块(40) + 涨幅(20) + 涨停基因(15) + 量能(15) + 市值(10)

新算法在 `algorithms.py` 中用 `@register("版本名")` 装饰器注册即可。

## 常用命令
```bash
# 手动选股（盘中使用）
python daily_pick.py

# 手动回测
python daily_backtest.py --date 2026-06-02

# 单股分析
python single_stock.py 000725

# 周复盘
python weekly_review.py

# 测试推送
python -c "from push_wechat import push; push('test','测试')"
```

## 数据源
- akshare (1.18.64): 东方财富/同花顺免费数据
- 涨停板、连板天梯稳定，概念/资金流接口间歇限速
- Python 3.14 环境

## 微信推送
- Server酱 SendKey: 见 push_wechat.py
- 注册地址: https://sct.ftqq.com

## 计划任务
Win+R → taskschd.msc → 搜索"A股"查看三个任务状态。

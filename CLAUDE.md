# A股短线选股分析系统

每日14:30自动选股 + 次日T+1回测 + 周五周复盘 + 微信推送。

## 触发条件
用户提到"选股"、"龙头"、"涨停"、"回测"、"复盘"、"A股"等关键词时加载此skill。

## 项目结构
```
stock-analyzer/
├── daily_pick.py        # 每日选股（V1-V4四算法并行）
├── daily_backtest.py    # T+1回测
├── morning_brief.py     # 盘前简报（9:00）
├── weekly_review.py     # 周五周复盘（算法PK）
├── algorithms.py        # 算法版本管理（@register注册）
├── data_fetcher.py      # akshare数据拉取
├── analyzer.py          # 数据→prompt格式化
├── push_wechat.py       # Server酱微信推送
├── stock_db.py          # SQLite数据库
├── single_stock.py      # 单股深度分析
├── setup_schedule.ps1   # 配置Windows计划任务
├── CHANGELOG.md         # 版本变更记录
├── README.md            # 使用说明
├── .sendkey             # 推送密钥（gitignore）
└── data/
    └── stock_records.db
```

## 自动化流程
| 时间 | 任务 | 说明 |
|------|------|------|
| 每日 9:00 | morning_brief.py | 盘前简报（可选） |
| 每日 14:30 | daily_pick.py | V1-V4各选5只→推微信 |
| 每日 15:05 | daily_backtest.py | 前日选股vs实际→推微信 |
| 周五 15:30 | weekly_review.py | 算法PK+胜者+推微信 |

## 版本
当前: **v1.2** | [CHANGELOG](CHANGELOG.md) | [GitHub](https://github.com/pp6v4/stock-analyzer)

## 算法版本（4个并行）
| | V1基础 | V2增强 | V3自适应 | V4量化 |
|------|:----:|:----:|:----:|:----:|
| 板块 | 50 | 40 | 30 | 15 |
| 涨幅 | 25 | 20 | 15 | 20 |
| 基因 | 25 | 15 | 12 | 10 |
| 量能 | - | 15 | 12 | 20 |
| 市值 | - | 10 | 8 | 10 |
| 封板 | - | - | 13 | 5 |
| 量价 | - | - | - | 5 |
| 可买 | 10 | 10 | 10 | 15 |
| **特点** | 进攻 | 风控 | 平衡 | 量化 |

新算法在 `algorithms.py` 中用 `@register("版本名")` 装饰器注册即可。

### 大盘保护
- 上证指数5日跌超3%自动暂停选股
- 周末和节假日自动跳过

## 已加载金融技能（来自 anthropics/financial-services）
| 技能 | 用途 |
|------|------|
| equity-idea-generation | 选股思路生成框架 |
| equity-sector-overview | 行业板块深度分析 |
| equity-morning-note | 盘前简报模板 |
| equity-comps-analysis | 可比公司估值分析 |
| equity-competitive-analysis | 竞争格局分析 |
| equity-catalyst-calendar | 催化剂事件日历 |
| equity-thesis-tracker | 投资论点追踪 |
| equity-earnings-analysis | 财报分析报告 |

## 常用命令
```bash
python daily_pick.py       # 手动选股
python daily_backtest.py   # T+1回测
python morning_brief.py    # 盘前简报
python weekly_review.py    # 周复盘
python single_stock.py 代码  # 单股分析
```

## 数据源
- akshare (1.18.64): 东方财富/同花顺免费数据
- Python 3.14 环境

## 微信推送
- Server酱，密钥存于 `.sendkey`（已gitignore）

## 计划任务
Win+R → taskschd.msc → 搜索"A股"

---
name: time-check
description: Financial time context checker - always confirm current time, trading session, and data timestamps before any stock/financial analysis
trigger:
  - keywords: [选股, 涨停, 复盘, 回测, 简报, 持仓, 分析, 股票, A股, 龙头, 盘前, 盘中, 尾盘, 收盘, 竞价, 开盘, K线, 行情, 板块, 龙虎榜, 财经, 财报]
  - always: true
---

# Time-Aware Financial Analysis Guard

## Purpose
Prevent errors caused by confusing current time, data timestamps, and trading sessions. Financial data is meaningless without correct temporal context.

## Hard Rules

### 1. ALWAYS confirm time context first
Before any financial analysis or data fetching, print:
```
【时间确认】
- 当前时间: YYYY-MM-DD HH:MM (星期X)
- 交易时段: [盘前竞价(9:15-9:25) / 早盘(9:30-11:30) / 午休(11:30-13:00) / 午盘(13:00-15:00) / 收盘后 / 非交易日]
- 上一个交易日: YYYYMMDD
```

### 2. NEVER confuse "today" vs "yesterday" for market data
- Before 9:30, all "today's" data is actually yesterday's close or pre-market quotes
- After 15:00, today's data is today's close
- During trading hours, real-time data is live but volatile

### 3. Always state the data source's timestamp
When presenting numbers, always clarify:
- "昨日收盘价" vs "今日实时价" vs "竞价阶段报价"
- Snapshot data: "快照时间: 20260602 15:05"
- Real-time data: "实时数据: 2026-06-03 09:18 (竞价中)"

### 4. Special session handling
- **盘前竞价 (9:15-9:25)**: Prices are indicative, not executed. Don't base decisions on them.
- **午休 (11:30-13:00)**: Prices frozen. Don't treat as real-time.
- **收盘后**: Use closing snapshot data, not stale real-time quotes.

### 5. Snapshot data vs live data
- Snapshot files (.json) have a `saved_at` field - always check and report it
- efinance real-time snapshots return 0 for high/low before market opens
- Never treat pre-market efinance data as reliable

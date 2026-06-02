# -*- coding: utf-8 -*-
"""本地SQLite数据库 - 支持算法版本管理"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "stock_records.db")


def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    # 先创建基础表
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS daily_picks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pick_date TEXT NOT NULL,
            stock_code TEXT NOT NULL,
            stock_name TEXT NOT NULL,
            rank INTEGER NOT NULL,
            reason TEXT,
            yesterday_close REAL,
            pick_pct REAL,
            sector TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS daily_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pick_id INTEGER,
            result_date TEXT NOT NULL,
            stock_code TEXT NOT NULL,
            stock_name TEXT NOT NULL,
            yesterday_close REAL,
            open_price REAL,
            high_30min REAL,
            close_price REAL,
            pct_change REAL,
            volume REAL,
            is_win INTEGER DEFAULT 0,
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (pick_id) REFERENCES daily_picks(id)
        );

        CREATE TABLE IF NOT EXISTS weekly_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            week_start TEXT NOT NULL,
            week_end TEXT NOT NULL,
            total_picks INTEGER,
            win_count INTEGER,
            avg_return REAL,
            best_stock TEXT,
            worst_stock TEXT,
            summary TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE INDEX IF NOT EXISTS idx_picks_date ON daily_picks(pick_date);
        CREATE INDEX IF NOT EXISTS idx_results_date ON daily_results(result_date);
        CREATE INDEX IF NOT EXISTS idx_picks_code ON daily_picks(stock_code);
    """)

    # 自动迁移：添加算法版本相关列（忽略已存在的错误）
    migrations = [
        ("ALTER TABLE daily_picks ADD COLUMN algo_version TEXT DEFAULT 'v1_baseline'", "algo_version"),
        ("ALTER TABLE daily_picks ADD COLUMN score REAL DEFAULT 0", "score"),
        ("ALTER TABLE daily_results ADD COLUMN algo_version TEXT DEFAULT ''", "algo_version"),
        ("ALTER TABLE weekly_reviews ADD COLUMN algo_comparison TEXT DEFAULT ''", "algo_comparison"),
        ("ALTER TABLE weekly_reviews ADD COLUMN winner_algo TEXT DEFAULT ''", "winner_algo"),
    ]
    for sql, col_name in migrations:
        try:
            conn.execute(sql)
        except:
            pass  # 列已存在

    # 创建新索引
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_picks_algo ON daily_picks(algo_version)")
    except:
        pass

    conn.commit()
    conn.close()


def save_picks(picks: list):
    """保存每日选股（含算法版本）"""
    conn = get_db()
    for p in picks:
        conn.execute("""
            INSERT INTO daily_picks (pick_date, stock_code, stock_name, rank, reason,
                yesterday_close, pick_pct, sector, score, algo_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            p.get("date"), p.get("code"), p.get("name"), p.get("rank"),
            p.get("reason"), p.get("yesterday_close"), p.get("pct"),
            p.get("sector"), p.get("score"), p.get("algo_version", "unknown"),
        ))
    conn.commit()
    conn.close()


def get_picks_by_date(date: str, algo_version: str = None):
    """按日期查询选股，可指定算法版本"""
    conn = get_db()
    if algo_version:
        rows = conn.execute(
            "SELECT * FROM daily_picks WHERE pick_date = ? AND algo_version = ? ORDER BY rank",
            (date, algo_version)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM daily_picks WHERE pick_date = ? ORDER BY algo_version, rank", (date,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_picks_for_backtest(date: str):
    """获取待回测的选股"""
    conn = get_db()
    rows = conn.execute("""
        SELECT p.* FROM daily_picks p
        WHERE p.pick_date = ?
        AND NOT EXISTS (
            SELECT 1 FROM daily_results r WHERE r.pick_id = p.id
        )
        ORDER BY p.algo_version, p.rank
    """, (date,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_results(results: list):
    """保存T+1回测结果"""
    conn = get_db()
    for r in results:
        conn.execute("""
            INSERT INTO daily_results (pick_id, result_date, stock_code, stock_name, algo_version,
                yesterday_close, open_price, high_30min, close_price, pct_change, volume, is_win)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            r.get("pick_id"), r.get("result_date"), r.get("code"), r.get("name"),
            r.get("algo_version", ""),
            r.get("yesterday_close"), r.get("open_price"), r.get("high_30min"),
            r.get("close_price"), r.get("pct_change"), r.get("volume"),
            1 if r.get("pct_change", 0) > 0 else 0,
        ))
    conn.commit()
    conn.close()


def get_week_stats(week_start: str, week_end: str):
    """获取一周统计数据（含算法版本）"""
    conn = get_db()
    rows = conn.execute("""
        SELECT p.pick_date, p.stock_code, p.stock_name, p.rank, p.reason, p.sector,
               p.algo_version, p.score,
               r.open_price, r.high_30min, r.close_price, r.pct_change, r.is_win
        FROM daily_picks p
        LEFT JOIN daily_results r ON p.id = r.pick_id
        WHERE p.pick_date BETWEEN ? AND ?
        ORDER BY p.pick_date, p.algo_version, p.rank
    """, (week_start, week_end)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_algo_comparison(week_start: str, week_end: str) -> dict:
    """对比两个算法的周表现"""
    stats = get_week_stats(week_start, week_end)

    algo_stats = {}
    for s in stats:
        algo = s.get('algo_version', 'unknown')
        if algo not in algo_stats:
            algo_stats[algo] = {
                'total': 0, 'wins': 0, 'returns': [],
                'best': None, 'worst': None,
            }
        as_ = algo_stats[algo]
        as_['total'] += 1
        if s.get('pct_change') is not None:
            pct = s['pct_change']
            as_['returns'].append(pct)
            if pct > 0:
                as_['wins'] += 1
            if as_['best'] is None or pct > as_['best']['pct_change']:
                as_['best'] = s
            if as_['worst'] is None or pct < as_['worst']['pct_change']:
                as_['worst'] = s

    # 计算汇总指标
    for algo, as_ in algo_stats.items():
        returns = as_['returns']
        as_['avg_return'] = sum(returns) / len(returns) if returns else 0
        as_['win_rate'] = as_['wins'] / len(returns) * 100 if returns else 0
        as_['max_win'] = max(returns) if returns else 0
        as_['max_loss'] = min(returns) if returns else 0
        as_['total_return'] = sum(returns)  # 组合总收益

    return algo_stats


def save_weekly_review(week_start: str, week_end: str, stats: dict,
                       algo_comparison: str, winner: str, summary: str):
    """保存周复盘（含算法比较）"""
    conn = get_db()
    conn.execute("""
        INSERT INTO weekly_reviews (week_start, week_end, total_picks, win_count, avg_return,
            best_stock, worst_stock, algo_comparison, winner_algo, summary)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        week_start, week_end,
        stats.get("total", 0), stats.get("wins", 0), stats.get("avg_return", 0),
        stats.get("best_stock", ""), stats.get("worst_stock", ""),
        algo_comparison, winner, summary,
    ))
    conn.commit()
    conn.close()


def get_all_time_stats(algo_version: str = None):
    """全时段统计，可选指定算法"""
    conn = get_db()
    if algo_version:
        total = conn.execute(
            "SELECT COUNT(*) as cnt FROM daily_results WHERE algo_version=?", (algo_version,)
        ).fetchone()["cnt"]
        wins = conn.execute(
            "SELECT COUNT(*) as cnt FROM daily_results WHERE is_win=1 AND algo_version=?", (algo_version,)
        ).fetchone()["cnt"]
        avg = conn.execute(
            "SELECT AVG(pct_change) as avg_pct FROM daily_results WHERE algo_version=?", (algo_version,)
        ).fetchone()["avg_pct"]
    else:
        total = conn.execute("SELECT COUNT(*) as cnt FROM daily_results").fetchone()["cnt"]
        wins = conn.execute("SELECT COUNT(*) as cnt FROM daily_results WHERE is_win=1").fetchone()["cnt"]
        avg = conn.execute("SELECT AVG(pct_change) as avg_pct FROM daily_results").fetchone()["avg_pct"]

    conn.close()
    return {
        "total": total, "wins": wins,
        "win_rate": wins / total * 100 if total > 0 else 0,
        "avg_return": avg or 0,
    }


# 初始化
init_db()

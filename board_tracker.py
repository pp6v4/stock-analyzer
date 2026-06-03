# -*- coding: utf-8 -*-
"""
板1追踪模块 — 发现连板妖股的"板1→横盘→板2"形态

核心逻辑（来自圣阳股份7连板+春秋电子5连板复盘）：
  规律1: 板1前有"静默期"（长时间窄幅横盘）→ 筹码集中
  规律2: 板1后回调温和（<15%，不破板1低点）→ 不是出货
  规律3: 真正的妖股在主升前有一次暴力洗盘（-7~-10%单日）→ 次日立即企稳

状态机:
  observing → consolidating → board2_candidate → board2_confirmed
                                                      ↓
                                                   failed (跌穿板1低点/连续大跌)

不与选股主流程耦合，独立运行。
"""

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import sqlite3
import os
import efinance as ef
import akshare as ak
import time
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "board_track.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS board_track (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            board1_date TEXT NOT NULL,
            board1_close REAL,
            board1_open REAL,
            board1_high REAL,
            board1_low REAL,
            board1_break_count INTEGER DEFAULT 0,
            board1_lock_fund REAL DEFAULT 0,
            board1_turnover REAL DEFAULT 0,
            board1_lock_time TEXT,
            board1_pct REAL,
            sector TEXT,
            status TEXT DEFAULT 'observing',
            max_drawdown REAL DEFAULT 0,
            max_drawdown_date TEXT,
            consolidation_days INTEGER DEFAULT 0,
            shakeout_flag INTEGER DEFAULT 0,
            board2_date TEXT,
            board2_close REAL,
            board2_quality TEXT,
            current_price REAL,
            current_pct REAL,
            last_update TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            notes TEXT DEFAULT ''
        );

        CREATE INDEX IF NOT EXISTS idx_bt_code ON board_track(code);
        CREATE INDEX IF NOT EXISTS idx_bt_status ON board_track(status);
        CREATE INDEX IF NOT EXISTS idx_bt_date ON board_track(board1_date);
    """)
    conn.commit()
    conn.close()


def get_kline_history(code, days=60):
    """拉取个股日K线历史"""
    if code.startswith(('0', '3')):
        symbol = 'sz' + code
    elif code.startswith(('6', '9')):
        symbol = 'sh' + code
    else:
        return None
    try:
        df = ak.stock_zh_a_hist_tx(symbol=symbol,
                                    start_date=(datetime.now() - timedelta(days=days*2)).strftime('%Y%m%d'),
                                    end_date=datetime.now().strftime('%Y%m%d'))
        return df
    except Exception:
        return None


def estimate_pre_board1_consolidation(code, board1_date):
    """
    估算板1前的静默期（横盘天数）
    静默期定义：板1前连续多日振幅<3%，价格在窄幅区间
    """
    df = get_kline_history(code, days=60)
    if df is None or df.empty:
        return 0

    b1_str = board1_date.replace('-', '')
    df['date_str'] = df['date'].astype(str).str.replace('-', '').str[:8]

    # 找板1位置
    b1_idx = df[df['date_str'] == b1_str].index
    if len(b1_idx) == 0:
        return 0
    b1_pos = b1_idx[0]

    # 向前数静默天数
    quiet_days = 0
    for i in range(b1_pos - 1, max(b1_pos - 30, 0), -1):
        row = df.iloc[i]
        daily_range = (row['high'] - row['low']) / row['close'] * 100
        if daily_range < 3.5:
            quiet_days += 1
        else:
            break

    return quiet_days


def scan_new_boards(date=None):
    """
    扫描当日涨停池，发现新的板1（连板数=1且不在已有追踪中）
    """
    if date is None:
        date = datetime.now().strftime('%Y%m%d')

    conn = get_db()
    existing = set(r['code'] for r in conn.execute("SELECT code FROM board_track").fetchall())

    try:
        zt = ak.stock_zt_pool_em(date=date)
    except Exception as e:
        print(f"  [WARN] 涨停池获取失败: {e}")
        conn.close()
        return []

    if zt is None or zt.empty:
        conn.close()
        return []

    new_boards = []
    for _, r in zt.iterrows():
        code = str(r.get('代码', ''))
        lb = int(r.get('连板数', 0))

        # 只追踪首板（连板数=1）且不在已有列表中的
        if lb == 1 and code not in existing:
            new_boards.append({
                'code': code,
                'name': str(r.get('名称', '')),
                'board1_date': date,
                'board1_close': float(r.get('最新价', 0)),
                'board1_pct': float(r.get('涨跌幅', 0)),
                'board1_break_count': int(r.get('炸板次数', 0)),
                'board1_lock_fund': float(r.get('封板资金', 0)),
                'board1_turnover': float(r.get('换手率', 0)),
                'board1_lock_time': str(r.get('首次封板时间', '')),
                'sector': str(r.get('所属行业', '')),
            })

    # 保存新发现的板1（静默期分析延迟到update时做，避免首次扫描太慢）
    for nb in new_boards:
        # 板1质量评估
        quality_flags = []
        if nb['board1_break_count'] <= 1:
            quality_flags.append('封板稳')
        else:
            quality_flags.append('炸板{}次'.format(nb['board1_break_count']))

        lock_yi = nb['board1_lock_fund'] / 1e8
        if lock_yi > 3:
            quality_flags.append('封单充足')
        elif lock_yi > 1:
            quality_flags.append('封单一般')
        else:
            quality_flags.append('封单薄弱')

        if nb['board1_turnover'] < 5:
            quality_flags.append('换手低')
        elif nb['board1_turnover'] < 10:
            quality_flags.append('换手适中')
        else:
            quality_flags.append('换手偏高')

        conn.execute("""
            INSERT INTO board_track (code, name, board1_date, board1_close, board1_pct,
                board1_break_count, board1_lock_fund, board1_turnover, board1_lock_time,
                sector, status, consolidation_days, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'observing', 0, ?)
        """, (
            nb['code'], nb['name'], nb['board1_date'], nb['board1_close'],
            nb['board1_pct'], nb['board1_break_count'], nb['board1_lock_fund'],
            nb['board1_turnover'], nb['board1_lock_time'], nb['sector'],
            '; '.join(quality_flags)
        ))

    conn.commit()
    added = len(new_boards)
    conn.close()
    return new_boards


def update_tracked():
    """
    更新所有活跃追踪股的状态：
    - 获取最新快照
    - 计算板1后最大回撤
    - 检测板2
    - 检测洗盘信号
    - 更新状态机
    """
    conn = get_db()
    active = conn.execute("""
        SELECT * FROM board_track
        WHERE status IN ('observing', 'consolidating', 'board2_candidate')
    """).fetchall()

    today = datetime.now().strftime('%Y-%m-%d')
    updated = 0

    for row in active:
        code = row['code']
        b1_date = row['board1_date']
        b1_close = row['board1_close'] or 0
        b1_turnover = row['board1_turnover'] or 0

        # 获取快照
        try:
            snap = ef.stock.get_quote_snapshot(code)
            if snap is None or snap.empty:
                continue
            price = float(snap.get('最新价', 0))
            pct = float(snap.get('涨跌幅', 0))
            high = float(snap.get('最高', 0))
            low = float(snap.get('最低', 0))
            volume = float(snap.get('成交量', 0))
            turnover = float(snap.get('换手率', 0))
            open_price = float(snap.get('开盘', 0))
        except Exception:
            continue

        if price == 0:
            continue

        # 计算板1后回撤
        drawdown = (price / b1_close - 1) * 100
        max_dd = min(row['max_drawdown'] or 0, drawdown)

        # 回撤超15%视为失败
        if drawdown < -15:
            conn.execute("""
                UPDATE board_track SET status='failed', notes=notes||' | 回撤超15%已跌穿板1',
                max_drawdown=?, max_drawdown_date=?, current_price=?, last_update=?
                WHERE id=?
            """, (drawdown, today, price, today, row['id']))
            updated += 1
            continue

        # 检测板2（今日涨停 且 涨停日不是板1当天）
        is_board2 = pct >= 9.5 and b1_date != datetime.now().strftime('%Y%m%d')
        if is_board2:
            # 判断板2质量
            b2_quality = '强'
            if volume > 0 and turnover < 15:
                b2_quality = '强(缩量板)'
            elif turnover > 20:
                b2_quality = '一般(放量板)'

            conn.execute("""
                UPDATE board_track SET status='board2_confirmed',
                board2_date=?, board2_close=?, board2_quality=?,
                current_price=?, last_update=?, notes=notes||' | 板2确认!'
                WHERE id=?
            """, (today, price, b2_quality, price, today, row['id']))
            updated += 1
            continue

        # 状态升级逻辑
        days_since_b1 = (datetime.strptime(today, '%Y-%m-%d') -
                         datetime.strptime(b1_date, '%Y%m%d')).days

        new_status = row['status']
        new_notes = row['notes'] or ''

        # 检测洗盘信号（单日>5%跌幅，但不破板1）
        if pct <= -5 and drawdown > -15:
            new_notes += ' | 疑似洗盘({:.1f}%)'.format(pct)
            conn.execute("UPDATE board_track SET shakeout_flag=1 WHERE id=?", (row['id'],))

        # 状态机
        if row['status'] == 'observing' and days_since_b1 >= 2:
            if drawdown > -8:
                new_status = 'consolidating'
                new_notes += ' | 回调温和，进入横盘观察'
            elif drawdown > -15:
                new_status = 'consolidating'
                new_notes += ' | 回调偏深但未破位，继续观察'

        if row['status'] == 'consolidating' and days_since_b1 >= 3:
            # 如果横盘3天以上+回调<10%+换手缩小 → 板2候选
            if drawdown > -10 and turnover < b1_turnover * 0.7:
                new_status = 'board2_candidate'
                new_notes += ' | 缩量横盘，板2候选!'

        conn.execute("""
            UPDATE board_track SET status=?, max_drawdown=?,
            consolidation_days=?, current_price=?, current_pct=?,
            last_update=?, notes=?
            WHERE id=?
        """, (new_status, max_dd, days_since_b1, price, pct, today, new_notes, row['id']))
        updated += 1

    conn.commit()
    conn.close()
    return updated


def get_active_candidates() -> list:
    """获取板2候选股（用于推送）"""
    conn = get_db()
    rows = conn.execute("""
        SELECT * FROM board_track
        WHERE status IN ('board2_candidate', 'consolidating')
        ORDER BY
            CASE status
                WHEN 'board2_candidate' THEN 0
                WHEN 'consolidating' THEN 1
            END,
            consolidation_days DESC
        LIMIT 10
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_recent_board2() -> list:
    """获取最近确认板2的股"""
    conn = get_db()
    rows = conn.execute("""
        SELECT * FROM board_track
        WHERE status = 'board2_confirmed'
        AND board2_date >= ?
        ORDER BY board2_date DESC
        LIMIT 5
    """, (datetime.now().strftime('%Y%m%d'),)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_active_count() -> dict:
    """各状态计数"""
    conn = get_db()
    counts = {}
    for row in conn.execute("""
        SELECT status, COUNT(*) as cnt FROM board_track GROUP BY status
    """).fetchall():
        counts[row['status']] = row['cnt']
    conn.close()
    return counts


def format_report() -> str:
    """生成板1追踪日报"""
    today = datetime.now().strftime('%Y-%m-%d')
    lines = [
        f"## 板1追踪日报 ({today})",
        "",
        "> 追踪首板→横盘→板2的连板形态",
        "",
    ]

    # 状态统计
    counts = get_active_count()
    if counts:
        parts = []
        for s, c in sorted(counts.items()):
            labels = {
                'observing': '观察中', 'consolidating': '横盘中',
                'board2_candidate': '板2候选', 'board2_confirmed': '板2确认',
                'failed': '已失败'
            }
            parts.append('{}:{}'.format(labels.get(s, s), c))
        lines.append('**池中**: ' + ' | '.join(parts))
        lines.append('')

    # 板2候选
    candidates = get_active_candidates()
    if candidates:
        lines.append('### 板2候选')
        lines.append('')
        lines.append('| 代码 | 名称 | 板1日期 | 板1价 | 现价 | 回撤 | 横盘天数 | 备注 |')
        lines.append('|------|------|----------|-------|------|------|----------|------|')
        for c in candidates:
            dd = ((c['current_price'] or 0) / c['board1_close'] - 1) * 100
            lines.append('| {} | {} | {} | {:.2f} | {:.2f} | {:.1f}% | {}天 | {} |'.format(
                c['code'], c['name'], c['board1_date'],
                c['board1_close'], c['current_price'] or 0,
                dd, c['consolidation_days'] or 0,
                c.get('notes', '')[:40]
            ))
        lines.append('')

    # 最近板2确认
    confirmed = get_recent_board2()
    if confirmed:
        lines.append('### 近期板2确认')
        lines.append('')
        lines.append('| 代码 | 名称 | 板1日期 | 板2日期 | 板2价 | 质量 |')
        lines.append('|------|------|----------|----------|-------|------|')
        for c in confirmed:
            lines.append('| {} | {} | {} | {} | {:.2f} | {} |'.format(
                c['code'], c['name'], c['board1_date'],
                c['board2_date'] or '?', c['board2_close'] or 0,
                c.get('board2_quality', '?')
            ))
        lines.append('')

    if not candidates and not confirmed:
        lines.append('当前无板2候选股。等待新的板1进入追踪池。')
        lines.append('')

    lines.append('---')
    lines.append('> 板1追踪 | 圣阳+春秋模式验证 | 不构成投资建议')
    return '\n'.join(lines)


def run_daily():
    """每日运行：扫描新板1 + 更新追踪状态"""
    today_str = datetime.now().strftime('%Y%m%d')
    print(f"\n=== 板1追踪 ({today_str}) ===\n")

    # 1. 扫描新板1
    today = datetime.now()
    if today.weekday() >= 5:
        print("[SKIP] 周末，跳过扫描")
        return

    print("[1/2] 扫描新板1...")
    new_boards = scan_new_boards(today_str)
    if new_boards:
        print(f"      发现 {len(new_boards)} 只新股:")
        for nb in new_boards:
            lock_yi = nb['board1_lock_fund'] / 1e8
            print(f"      {nb['code']} {nb['name']} | 封板:{lock_yi:.1f}亿 | "
                  f"炸板:{nb['board1_break_count']}次 | 换手:{nb['board1_turnover']:.1f}% | "
                  f"{nb['sector']}")
    else:
        print("      无新板1")

    # 2. 更新已有追踪
    print("[2/2] 更新追踪状态...")
    updated = update_tracked()
    print(f"      更新 {updated} 条记录")

    return new_boards


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", action="store_true", help="输出日报")
    parser.add_argument("--push", action="store_true", help="推送到微信")
    args = parser.parse_args()

    init_db()
    run_daily()

    if args.report or args.push:
        report = format_report()
        print(report[:500])
        if args.push:
            from push_wechat import push as wx_push
            try:
                wx_push("【板1追踪】" + datetime.now().strftime("%m-%d"), report)
                print("[PUSH] OK")
            except Exception as e:
                print("[PUSH ERROR]", e)

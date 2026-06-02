# -*- coding: utf-8 -*-
"""
选股算法版本管理 - 支持多版本并行 + A/B测试
每个版本是一个独立的打分函数，返回0-100的评分
"""

import pandas as pd
from typing import Optional

# ============================================================
# 算法版本注册表
# ============================================================
# 新增算法：在下面添加函数，然后注册到 ALGO_VERSIONS 即可
# 旧版本不删除，保留用于对比

ALGO_VERSIONS = {}  # {version_name: score_function}


def register(version: str):
    """装饰器：注册算法版本"""
    def decorator(func):
        ALGO_VERSIONS[version] = func
        func.version = version
        return func
    return decorator


# ============================================================
# V1: 基础版（2026-06-02初始版本）
# 因子：板块效应(50) + 涨幅位置(25) + 涨停基因(25) + 可买性(10)
# ============================================================

@register("v1_baseline")
def score_v1(row, sector_counts: dict, zt_codes: set) -> float:
    """
    V1 基础评分
    - 板块效应权重50%：同板块涨停数越多越好
    - 涨幅位置权重25%：3-8%最佳，过低没动量，过高买不到
    - 涨停基因权重25%：近期涨停次数越多越好
    - 可买性加分：非涨停+10，涨停-20
    """
    score = 0.0

    # --- 数据提取 ---
    pct = float(row.get('涨跌幅', 0)) if pd.notna(row.get('涨跌幅', 0)) else 0
    code = str(row.get('代码', ''))
    name = str(row.get('名称', ''))
    sector = str(row.get('所属行业', ''))
    stat = str(row.get('涨停统计', '0/0'))

    # 涨停基因解析
    try:
        parts = stat.split('/')
        recent_boards = int(parts[0]) if parts[0].isdigit() else 0
    except:
        recent_boards = 0

    sector_zt_count = sector_counts.get(sector, 0)
    is_zt = code in zt_codes

    # --- 排除规则 ---
    if '退市' in name or 'ST' in name or '*ST' in name:
        return -999
    if code.startswith('920'):  # 北交所
        return -999

    # --- 因子1: 板块效应 (0-50分) ---
    if sector_zt_count >= 5:
        score += 50
    elif sector_zt_count >= 4:
        score += 45
    elif sector_zt_count >= 3:
        score += 35
    elif sector_zt_count >= 2:
        score += 20
    elif sector_zt_count >= 1:
        score += 8

    # --- 因子2: 涨幅位置 (0-25分) ---
    if 3.0 <= pct <= 8.0:
        score += 25
    elif 1.5 <= pct < 3.0:
        score += 15
    elif 8.0 < pct <= 9.5:
        score += 12
    elif 0 <= pct < 1.5:
        score += 5
    elif pct > 9.5:
        score -= 30  # 快封板了买不到
    elif pct < 0:
        score -= 20  # 跌的

    # --- 因子3: 涨停基因 (0-25分) ---
    if recent_boards >= 10:
        score += 25
    elif recent_boards >= 7:
        score += 22
    elif recent_boards >= 5:
        score += 18
    elif recent_boards >= 3:
        score += 14
    elif recent_boards >= 1:
        score += 8

    # --- 因子4: 可买性 (+10/-20) ---
    if not is_zt:
        score += 10
    else:
        score -= 20

    return round(score, 1)


# ============================================================
# V2: 增强版（2026-06-02优化）
# 新增因子：量能(15) + 流通市值偏好(10)
# 调整因子权重：板块效应(40) + 涨幅位置(20) + 涨停基因(15) + 量能(15) + 可买性(10)
# ============================================================

@register("v2_enhanced")
def score_v2(row, sector_counts: dict, zt_codes: set) -> float:
    """
    V2 增强评分
    相比V1的改进：
    1. 新增量能因子：换手率适中最好（太低没资金关注，太高出货嫌疑）
    2. 新增市值因子：偏好中小市值（弹性大），排除过大市值
    3. 板块效应权重调降（50→40），分散风险
    4. 涨停基因权重调降（25→15），避免过度追妖
    5. 可买性精准化：已在涨停的彻底排除
    """
    score = 0.0

    # --- 数据提取 ---
    pct = float(row.get('涨跌幅', 0)) if pd.notna(row.get('涨跌幅', 0)) else 0
    code = str(row.get('代码', ''))
    name = str(row.get('名称', ''))
    sector = str(row.get('所属行业', ''))
    stat = str(row.get('涨停统计', '0/0'))

    # V2新增数据
    turnover = float(row.get('换手率', 0)) if pd.notna(row.get('换手率', 0)) else 0
    # 流通市值（单位：元）
    float_mv = float(row.get('流通市值', 0)) if pd.notna(row.get('流通市值', 0)) else 0
    # 成交额
    volume_amount = float(row.get('成交额', 0)) if pd.notna(row.get('成交额', 0)) else 0

    # 涨停基因解析
    try:
        parts = stat.split('/')
        recent_boards = int(parts[0]) if parts[0].isdigit() else 0
    except:
        recent_boards = 0

    sector_zt_count = sector_counts.get(sector, 0)
    is_zt = code in zt_codes

    # --- 排除规则 ---
    if '退市' in name or 'ST' in name or '*ST' in name:
        return -999
    if code.startswith('920'):
        return -999

    # --- 因子1: 板块效应 (0-40分) ---
    if sector_zt_count >= 5:
        score += 40
    elif sector_zt_count >= 4:
        score += 36
    elif sector_zt_count >= 3:
        score += 28
    elif sector_zt_count >= 2:
        score += 18
    elif sector_zt_count >= 1:
        score += 8

    # --- 因子2: 涨幅位置 (0-20分) ---
    if 3.0 <= pct <= 7.0:
        score += 20
    elif 1.5 <= pct < 3.0:
        score += 12
    elif 7.0 < pct <= 9.5:
        score += 10
    elif 0 <= pct < 1.5:
        score += 5
    elif pct > 9.5:
        score -= 40  # V2更严格惩罚封板买不到的
    elif pct < 0:
        score -= 25

    # --- 因子3: 涨停基因 (0-15分) ---
    if 5 <= recent_boards <= 12:  # 活跃但不太妖
        score += 15
    elif 3 <= recent_boards <= 4:
        score += 12
    elif 1 <= recent_boards <= 2:
        score += 8
    elif recent_boards > 12:  # 太妖了，风险大
        score += 5

    # --- 因子4: 量能 (0-15分) [V2新增] ---
    # 换手率2-10%最佳（有资金但不太疯狂）
    if 3 <= turnover <= 8:
        score += 15
    elif 1.5 <= turnover < 3:
        score += 10
    elif 8 < turnover <= 15:
        score += 8
    elif turnover < 1.5:
        score += 3
    elif turnover > 15:
        score -= 10  # 换手过高风险

    # --- 因子5: 市值偏好 (0-10分) [V2新增] ---
    # 偏好20亿-200亿流通市值（小盘弹性好，又不至于太迷你）
    if float_mv > 0:
        mv_yi = float_mv / 1e8  # 转为亿元
        if 20 <= mv_yi <= 100:
            score += 10
        elif 100 < mv_yi <= 200:
            score += 8
        elif 10 <= mv_yi < 20:
            score += 5
        elif mv_yi > 500:
            score += 2  # 太大盘子弹性差
        elif mv_yi < 10:
            score -= 5  # 太迷你流动性风险
    else:
        score += 5  # 市值数据缺失给中性分

    # --- 因子6: 可买性 (0-10分) ---
    if not is_zt:
        score += 10
    else:
        score -= 50  # V2涨停下重手排除

    return round(score, 1)


# ============================================================
# V3: 自适应版（2026-06-02 v1.1）
# 综合V1+V2优点 + 新增因子
# 权重：板块(30) + 涨幅(15) + 涨停基因(12) + 量能(12) + 市值(8) + 封板质量(13) + 可买性(10)
# ============================================================

@register("v3_adaptive")
def score_v3(row, sector_counts: dict, zt_codes: set) -> float:
    """
    V3 自适应评分
    相比V2的改进：
    1. 新增封板质量因子：炸板次数少 → 逻辑硬，资金认可度高
    2. 新增封板时间因子：早盘封板 → 主动性买盘，尾盘封板 → 跟风
    3. 板块效应进一步精细化：区分主线(>=4)和跟风板块
    4. 涨幅因子引入"甜点区"概念：3-7%为最佳
    5. 综合V1的高弹性 + V2的风控
    """
    score = 0.0

    # --- 数据提取 ---
    pct = float(row.get('涨跌幅', 0)) if pd.notna(row.get('涨跌幅', 0)) else 0
    code = str(row.get('代码', ''))
    name = str(row.get('名称', ''))
    sector = str(row.get('所属行业', ''))
    stat = str(row.get('涨停统计', '0/0'))

    # V3数据
    turnover = float(row.get('换手率', 0)) if pd.notna(row.get('换手率', 0)) else 0
    float_mv = float(row.get('流通市值', 0)) if pd.notna(row.get('流通市值', 0)) else 0

    # V3新增: 炸板次数和封板时间（从涨停板数据中获取，非涨停股给默认值）
    break_count = int(row.get('炸板次数', 0)) if pd.notna(row.get('炸板次数', 0)) else 0
    lock_time = str(row.get('首次封板时间', ''))

    # 涨停基因解析
    try:
        parts = stat.split('/')
        recent_boards = int(parts[0]) if parts[0].isdigit() else 0
    except:
        recent_boards = 0

    sector_zt_count = sector_counts.get(sector, 0)
    is_zt = code in zt_codes

    # --- 排除规则 ---
    if '退市' in name or 'ST' in name or '*ST' in name:
        return -999
    if code.startswith('920'):
        return -999

    # --- 因子1: 板块效应 (0-30分) ---
    if sector_zt_count >= 6:
        score += 30
    elif sector_zt_count >= 4:
        score += 26
    elif sector_zt_count >= 3:
        score += 20
    elif sector_zt_count >= 2:
        score += 13
    elif sector_zt_count >= 1:
        score += 6

    # --- 因子2: 涨幅位置 (0-15分) ---
    if 3.0 <= pct <= 7.0:
        score += 15
    elif 1.5 <= pct < 3.0:
        score += 10
    elif 7.0 < pct <= 9.0:
        score += 8
    elif 0 <= pct < 1.5:
        score += 4
    elif pct > 9.0:
        score -= 35
    elif pct < 0:
        score -= 20

    # --- 因子3: 涨停基因 (0-12分) ---
    if 3 <= recent_boards <= 8:
        score += 12
    elif 1 <= recent_boards <= 2:
        score += 8
    elif 9 <= recent_boards <= 15:
        score += 6
    elif recent_boards > 15:
        score += 2

    # --- 因子4: 量能 (0-12分) ---
    if 2 <= turnover <= 10:
        score += 12
    elif 1 <= turnover < 2:
        score += 8
    elif 10 < turnover <= 15:
        score += 6
    elif turnover < 1:
        score += 2
    elif turnover > 15:
        score -= 8

    # --- 因子5: 市值偏好 (0-8分) ---
    if float_mv > 0:
        mv_yi = float_mv / 1e8
        if 15 <= mv_yi <= 150:
            score += 8
        elif 150 < mv_yi <= 300:
            score += 5
        elif 5 <= mv_yi < 15:
            score += 3
        elif mv_yi > 500:
            score += 1
        elif mv_yi < 5:
            score -= 3
    else:
        score += 4

    # --- 因子6: 封板质量 (0-13分) [V3新增] ---
    # 6a. 炸板次数（非涨停股给中性分）
    if is_zt:
        if break_count == 0:
            score += 8  # 封死没炸过，最强
        elif break_count == 1:
            score += 5
        elif break_count <= 3:
            score += 2
        else:
            score -= 5  # 炸板太多，封板质量差
    else:
        score += 4  # 非涨停股中性

    # 6b. 封板时间（非涨停股给中性分）
    if is_zt and lock_time:
        try:
            time_min = int(lock_time[:2]) * 60 + int(lock_time[2:4]) if len(lock_time) >= 4 else 600
            if time_min <= 580:  # 9:40前封板
                score += 5
            elif time_min <= 600:  # 10:00前
                score += 3
            elif time_min <= 630:  # 10:30前
                score += 1
        except:
            score += 2
    else:
        score += 2

    # --- 因子7: 可买性 (0-10分) ---
    if not is_zt:
        score += 10
    else:
        score -= 40  # V3涨停股坚决排除（买不到）

    return round(score, 1)


# ============================================================
# 通用选股引擎：用指定算法版本选股
# ============================================================

def select_stocks(algorithm_version: str, strong_df: pd.DataFrame,
                  sector_counts: dict, zt_codes: set, max_picks: int = 5) -> list:
    """
    用指定的算法版本从强势股池中选股
    返回: [{"code","name","pct","sector","score","algo_version","rank",...}, ...]
    """
    score_func = ALGO_VERSIONS.get(algorithm_version)
    if score_func is None:
        raise ValueError(f"未知算法版本: {algorithm_version}. 可用: {list(ALGO_VERSIONS.keys())}")

    candidates = []
    for _, row in strong_df.iterrows():
        score = score_func(row, sector_counts, zt_codes)
        if score <= 0:
            continue

        code = str(row.get('代码', ''))
        name = str(row.get('名称', ''))
        pct = float(row.get('涨跌幅', 0)) if pd.notna(row.get('涨跌幅', 0)) else 0
        sector = str(row.get('所属行业', ''))
        stat = str(row.get('涨停统计', '0/0'))

        candidates.append({
            'code': code,
            'name': name,
            'pct': round(pct, 2),
            'sector': sector,
            'sector_zt_count': sector_counts.get(sector, 0),
            'stat': stat,
            'score': score,
        })

    # 按评分排序
    candidates.sort(key=lambda x: x['score'], reverse=True)

    # 同板块最多2只
    picks = []
    sector_count = {}
    for c in candidates:
        sec = c['sector']
        if sector_count.get(sec, 0) >= 2:
            continue
        c['rank'] = len(picks) + 1
        c['algo_version'] = algorithm_version
        c['reason'] = generate_reason(c)
        picks.append(c)
        sector_count[sec] = sector_count.get(sec, 0) + 1
        if len(picks) >= max_picks:
            break

    # 不足补足
    if len(picks) < max_picks:
        used = {p['code'] for p in picks}
        for c in candidates:
            if c['code'] not in used and len(picks) < max_picks:
                c['rank'] = len(picks) + 1
                c['algo_version'] = algorithm_version
                c['reason'] = generate_reason(c)
                picks.append(c)
                used.add(c['code'])

    return picks


def generate_reason(pick: dict) -> str:
    """生成入选理由"""
    parts = []
    if pick['sector_zt_count'] >= 3:
        parts.append(f"{pick['sector']}主线（{pick['sector_zt_count']}只涨停）")
    elif pick['sector_zt_count'] >= 1:
        parts.append(f"{pick['sector']}板块")
    parts.append(f"涨幅+{pick['pct']}%")
    parts.append(f"活跃度{pick['stat']}")
    parts.append(f"评分{pick['score']}")
    return "，".join(parts)


def list_versions():
    """列出所有可用算法版本"""
    return list(ALGO_VERSIONS.keys())


if __name__ == "__main__":
    print("已注册算法版本:")
    for v in ALGO_VERSIONS:
        print(f"  - {v}: {ALGO_VERSIONS[v].__doc__[:60]}...")

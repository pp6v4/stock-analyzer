"""
A股短线数据拉取模块
依赖: akshare, pandas
"""

import time
from datetime import datetime, timedelta
from typing import Optional
import akshare as ak
import pandas as pd


def _retry(func, max_retries=2, delay=1.5):
    for i in range(max_retries):
        try:
            return func()
        except Exception:
            if i < max_retries - 1:
                time.sleep(delay)
            else:
                raise


def get_limit_up_stocks(date: Optional[str] = None) -> pd.DataFrame:
    """涨停板列表"""
    if date is None:
        date = datetime.now().strftime("%Y%m%d")
    try:
        return _retry(lambda: ak.stock_zt_pool_em(date=date))
    except Exception as e:
        print(f"[WARN] 涨停板: {e}")
        return pd.DataFrame()


def get_continuous_limit_up() -> pd.DataFrame:
    """连板天梯"""
    try:
        return _retry(lambda: ak.stock_zt_pool_strong_em(date=datetime.now().strftime("%Y%m%d")))
    except Exception as e:
        print(f"[WARN] 连板天梯: {e}")
        return pd.DataFrame()


def get_industry_rank() -> pd.DataFrame:
    """
    行业板块涨幅排行
    优先用同花顺（快），备用东方财富
    """
    # THS版 - 90个行业，几秒就完
    try:
        df = ak.stock_board_industry_name_ths()
        if df is not None and not df.empty:
            return df
    except Exception:
        pass

    # EM版备用
    try:
        return _retry(lambda: ak.stock_board_industry_name_em())
    except Exception:
        pass

    print("[WARN] 行业排行拉取失败")
    return pd.DataFrame()


def get_concept_rank() -> pd.DataFrame:
    """
    概念板块涨幅排行
    EM的spot接口（有实时涨跌幅和资金流向）
    """
    try:
        df = ak.stock_board_concept_spot_em()
        if df is not None and not df.empty:
            return df
    except Exception:
        pass

    # fallback: EM name list
    try:
        df = ak.stock_board_concept_name_em()
        if df is not None and not df.empty:
            return df
    except Exception:
        pass

    print("[WARN] 概念板块拉取失败")
    return pd.DataFrame()


def get_billboard(date: Optional[str] = None) -> pd.DataFrame:
    """龙虎榜"""
    if date is None:
        date = datetime.now().strftime("%Y%m%d")
    try:
        return _retry(lambda: ak.stock_lhb_detail_em(start_date=date, end_date=date))
    except Exception:
        pass
    try:
        return _retry(lambda: ak.stock_lhb_detail_em())
    except Exception as e:
        print(f"[WARN] 龙虎榜: {e}")
        return pd.DataFrame()


def get_hot_rank() -> pd.DataFrame:
    """个股热度排行"""
    try:
        return _retry(lambda: ak.stock_hot_rank_em())
    except Exception as e:
        print(f"[WARN] 热度排行: {e}")
        return pd.DataFrame()


def get_fund_flow() -> pd.DataFrame:
    """
    资金流向（可选，可能被限速）
    """
    for func in [
        lambda: ak.stock_individual_fund_flow_rank(indicator="今日"),
        lambda: ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流"),
    ]:
        try:
            return _retry(func, max_retries=1, delay=1)
        except Exception:
            continue
    print("[WARN] 资金流向拉取失败（不影响主流程）")
    return pd.DataFrame()


def get_stock_kline(code: str, days: int = 30) -> pd.DataFrame:
    """个股K线"""
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=days * 2)).strftime("%Y%m%d")
    try:
        df = ak.stock_zh_a_hist(symbol=code, period="daily",
                                start_date=start_date, end_date=end_date,
                                adjust="qfq")
        return df.tail(days) if df is not None and not df.empty else pd.DataFrame()
    except Exception as e:
        print(f"[WARN] K线({code}): {e}")
        return pd.DataFrame()


def fetch_all(date: Optional[str] = None) -> dict:
    """一键拉取所有短线数据"""
    if date is None:
        date = datetime.now().strftime("%Y%m%d")

    print(f"=== A股短线数据 ({date}) ===\n")

    print("[1/6] 涨停板...")
    limit_up = get_limit_up_stocks(date)
    print(f"      {len(limit_up)} 只涨停")

    print("[2/6] 连板天梯...")
    continuous = get_continuous_limit_up()
    print(f"      {len(continuous)} 只在榜")

    print("[3/6] 概念板块...")
    concept = get_concept_rank()
    print(f"      {len(concept)} 个概念")

    print("[4/6] 行业板块...")
    industry = get_industry_rank()
    print(f"      {len(industry)} 个行业")

    print("[5/6] 龙虎榜...")
    billboard = get_billboard(date)
    print(f"      {len(billboard)} 条记录")

    print("[6/6] 热度排行...")
    hot = get_hot_rank()
    print(f"      {len(hot)} 只热门")

    print("\n=== 完成 ===")
    return {
        "date": date,
        "limit_up": limit_up,
        "continuous_limit_up": continuous,
        "concept_rank": concept,
        "industry_rank": industry,
        "billboard": billboard,
        "hot_rank": hot,
    }

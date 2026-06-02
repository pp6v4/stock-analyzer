# -*- coding: utf-8 -*-
"""
AI分析模块 - 把原始数据格式化为结构化prompt
"""

import json
from datetime import datetime
from typing import Optional
import pandas as pd


def _top(df, n=10):
    """安全取前N行"""
    if df is None or df.empty:
        return "暂无数据"
    return df.head(n).to_string()


def _top_cols(df, cols, n=15):
    """按指定列取前N行，列不存在则全部输出"""
    if df is None or df.empty:
        return "暂无数据"
    available = [c for c in cols if c in df.columns]
    if available:
        return df.head(n)[available].to_string(index=False)
    return df.head(n).to_string()


def build_analysis_prompt(data: dict) -> str:
    """打包成完整分析prompt"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    date = data.get("date", "")

    # 涨停板摘要
    lu = data.get("limit_up", pd.DataFrame())
    if not lu.empty:
        lu_summary = f"涨停家数: {len(lu)} 只\n\n"
        if "连板数" in lu.columns:
            cb = lu["连板数"].value_counts().sort_index(ascending=False)
            cb_str = " | ".join(f"{int(d)}连板: {c}只" for d, c in cb.items() if d >= 2)
            if cb_str:
                lu_summary += f"连板梯队: {cb_str}\n\n"
        if "所属行业" in lu.columns:
            ti = lu["所属行业"].value_counts().head(5)
            ti_str = " | ".join(f"{i}({c}只)" for i, c in ti.items())
            lu_summary += f"涨停集中行业: {ti_str}\n"
        lu_summary += f"\n涨停板列表:\n{_top_cols(lu, ['代码','名称','涨跌幅','连板数','首次封板时间','所属行业'], 20)}"
    else:
        lu_summary = "暂无涨停数据（可能非交易日）"

    # 连板天梯摘要
    cl = data.get("continuous_limit_up", pd.DataFrame())
    if cl.empty:
        cl_summary = "暂无数据"
    else:
        top_cl = cl.head(20)
        max_cb = top_cl.iloc[:, 2] if top_cl.shape[1] > 2 else "?"
        cl_summary = f"连板高度统计: {len(cl)} 只在榜\n\n"
        cl_summary += f"{_top_cols(top_cl, ['代码','名称','涨跌幅','涨停统计','所属行业'], 20)}"

    # 构建完整prompt
    prompt = f"""# A股短线市场分析数据 ({now})

## 一、涨停板概况
{lu_summary}

## 二、连板天梯（高标股）
{cl_summary}

## 三、概念板块涨幅排行（前20）
{_top_cols(data.get('concept_rank'), ['代码','名称','涨跌幅','主力净流入'], 20)}

## 四、行业板块涨幅排行（前20）
{_top_cols(data.get('industry_rank'), ['代码','名称'], 20)}

## 五、龙虎榜动向（前20）
{_top(data.get('billboard'), 20)}

## 六、个股热度排行（前20）
{_top(data.get('hot_rank'), 20)}

---

请基于以上数据，分析当前A股短线市场：

1. **市场情绪**：涨停家数、连板高度反映的市场阶段和情绪
2. **主线题材**：当前资金聚焦的核心题材，判断其持续性
3. **人气龙头**：连板天梯中的高标股，哪些题材支撑强
4. **低位机会**：首板/二板中题材有持续性的补涨标的
5. **风险提示**：需要警惕的高位股和市场风险

（以上为数据分析参考，不构成投资建议）
"""
    return prompt


def save_report(prompt: str, filepath: Optional[str] = None):
    if filepath is None:
        filepath = f"stock_report_{datetime.now().strftime('%Y%m%d_%H%M')}.md"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(prompt)
    print(f"[INFO] 报告: {filepath}")
    return filepath


def save_raw_data(data: dict, filepath: Optional[str] = None):
    if filepath is None:
        filepath = f"raw_data_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    serializable = {}
    for key, df in data.items():
        if isinstance(df, pd.DataFrame) and not df.empty:
            serializable[key] = df.head(50).to_dict(orient="records")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(serializable, f, ensure_ascii=False, indent=2, default=str)
    print(f"[INFO] 数据: {filepath}")
    return filepath

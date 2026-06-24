from __future__ import annotations

from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd


CYCLE_STRENGTH_COLUMNS = [
    "date",
    "market_cycle",
    "cycle_strength",
    "cycle_stage_confidence",
    "avg_momentum_score",
    "avg_trend_score",
    "momentum_change_rate",
    "limit_up_count",
    "top_score_concentration",
    "market_divergence_std",
    "trading_mode",
    "recommended_position_ratio",
    "risk_level",
    "risk_action",
]

LEADER_COLUMNS = [
    "date",
    "code",
    "name",
    "momentum_score",
    "trend_score",
    "combined_score",
    "is_leader",
    "leader_rank",
    "leader_strength_score",
    "breakout_strength",
    "continuation_score",
    "acceleration_score",
    "pool_type",
    "risk_level",
    "risk_reason",
]

RISK_CONTROL_COLUMNS = [
    "date",
    "market_cycle",
    "cycle_strength",
    "recommended_position_ratio",
    "risk_level",
    "risk_action",
    "risk_reason",
    "leader_count",
    "trend_count",
    "watch_count",
    "risk_count",
]

MARKET_MASTER_SIGNAL_COLUMNS = [
    "date",
    "market_regime_final",
    "one_sentence_summary",
    "master_score_mean",
    "top_master_score",
    "cycle",
    "cycle_strength",
    "avg_momentum_score",
    "avg_trend_score",
    "avg_continuation_score",
    "leader_count",
    "money_attack_status",
    "mainline_status",
    "style_switch_status",
    "tide_status",
    "allow_open_position",
    "risk_gate_reason",
]

LEADER_TIER_COLUMNS = [
    "date",
    "code",
    "name",
    "leader_tier",
    "leader_rank",
    "leader_strength_score",
    "master_score",
    "momentum_score",
    "trend_score",
    "combined_score",
    "money_continuation_score",
    "final_decision",
]

RISK_GATE_COLUMNS = [
    "date",
    "allow_open_position",
    "risk_gate_action",
    "risk_gate_reason",
    "continuation_decline",
    "leader_decline",
    "cycle_tide",
    "market_regime_final",
]


def _num(series: pd.Series | None) -> pd.Series:
    if series is None:
        return pd.Series(dtype=float)
    return pd.to_numeric(series, errors="coerce")


def _clip(value: float, low: float = 0.0, high: float = 100.0) -> float:
    if pd.isna(value):
        return low
    return round(float(max(low, min(high, value))), 2)


def _rank_score(series: pd.Series, higher_is_better: bool = True) -> pd.Series:
    numeric = _num(series)
    if numeric.dropna().empty:
        return pd.Series([50.0] * len(series), index=series.index)
    pct = numeric.rank(pct=True, ascending=not higher_is_better).fillna(0.5)
    return (30 + pct * 70).round(2)


def _read_cycle_history(project_root: Path, target_date: str) -> pd.DataFrame:
    path = project_root / "cycle_daily.csv"
    if not path.exists():
        return pd.DataFrame()
    try:
        data = pd.read_csv(path, dtype={"date": str})
    except Exception as exc:
        print(f"读取市场周期历史失败，仅使用当日数据：{exc}")
        return pd.DataFrame()
    return data[data["date"].astype(str) != target_date].copy()


def _read_previous_pool(project_root: Path, target_date: str) -> pd.DataFrame:
    processed_dir = project_root / "data" / "processed"
    if not processed_dir.exists():
        return pd.DataFrame()
    candidates = []
    for path in processed_dir.glob("trend_core_pool_*.csv"):
        date_text = path.stem.replace("trend_core_pool_", "")
        if date_text < target_date:
            candidates.append((date_text, path))
    if not candidates:
        return pd.DataFrame()
    _, latest_path = sorted(candidates)[-1]
    try:
        data = pd.read_csv(latest_path, dtype={"code": str})
    except Exception as exc:
        print(f"读取上一期趋势池失败，风格切换只使用当日数据：{exc}")
        return pd.DataFrame()
    data["code"] = data["code"].astype(str).str.zfill(6)
    return data


def _limit_up_count(pool: pd.DataFrame) -> int:
    pct = _num(pool.get("pct_chg"))
    if pct.empty:
        return 0
    # 当前数据只有日涨幅字段时，统一用 9.8% 近似统计涨停强度。
    return int((pct >= 9.8).sum())


def _top_score_concentration(pool: pd.DataFrame) -> float:
    score = _num(pool.get("combined_score")).dropna()
    if score.empty:
        return 0.0
    top5_mean = score.sort_values(ascending=False).head(5).mean()
    all_mean = score.mean()
    if all_mean <= 0:
        return 0.0
    return round(float(top5_mean / all_mean * 100), 2)


def _enhanced_cycle(target_date: str, pool: pd.DataFrame, project_root: Path, base_cycle: Dict) -> Dict:
    avg_momentum = round(float(_num(pool.get("momentum_score")).mean()), 2) if not pool.empty else 0.0
    avg_trend = round(float(_num(pool.get("trend_score")).mean()), 2) if not pool.empty else 0.0
    market_std = round(float(_num(pool.get("combined_score")).std()), 2) if len(pool) > 1 else 0.0
    limit_count = _limit_up_count(pool)
    concentration = _top_score_concentration(pool)

    history = _read_cycle_history(project_root, target_date)
    if history.empty:
        previous_momentum = 70.0
    else:
        previous_momentum = float(pd.to_numeric(history.tail(1)["avg_momentum_score"], errors="coerce").iloc[0])
        if previous_momentum == 0 or pd.isna(previous_momentum):
            previous_momentum = 70.0
    momentum_change_rate = round((avg_momentum / previous_momentum - 1) * 100, 2) if previous_momentum else 0.0

    strength = _clip(
        avg_momentum * 0.30
        + avg_trend * 0.30
        + min(limit_count * 4.0, 20.0)
        + min(concentration / 6.0, 20.0)
        + min(market_std * 1.2, 15.0)
    )

    if avg_momentum < 65 and avg_trend < 65 and momentum_change_rate <= 0:
        market_cycle = "冰点期"
    elif strength >= 88 and avg_momentum >= 82 and concentration >= 108:
        market_cycle = "加速期"
    elif avg_momentum >= 72 and avg_trend >= 72 and momentum_change_rate >= 0:
        market_cycle = "主升期"
    elif avg_momentum >= 70 and avg_trend < 72 and momentum_change_rate > 0:
        market_cycle = "启动期"
    elif momentum_change_rate < 0 and avg_trend >= 72:
        market_cycle = "退潮期"
    else:
        market_cycle = str(base_cycle.get("market_cycle", "启动期"))

    confidence = _clip(
        45.0
        + abs(momentum_change_rate) * 1.8
        + min(limit_count * 2.0, 15.0)
        + min(abs(concentration - 100.0), 20.0)
        + min(market_std, 20.0)
    )
    return {
        "date": target_date,
        "market_cycle": market_cycle,
        "cycle_strength": strength,
        "cycle_stage_confidence": confidence,
        "avg_momentum_score": avg_momentum,
        "avg_trend_score": avg_trend,
        "momentum_change_rate": momentum_change_rate,
        "limit_up_count": limit_count,
        "top_score_concentration": concentration,
        "market_divergence_std": market_std,
    }


def _stock_space_scores(pool: pd.DataFrame) -> pd.DataFrame:
    data = pool.copy()
    data["code"] = data["code"].astype(str).str.zfill(6)
    for column in ["momentum_score", "trend_score", "combined_score", "amount", "pct_5d", "pct_10d", "pct_20d", "distance_to_20d_high"]:
        data[column] = _num(data.get(column))

    distance = data["distance_to_20d_high"].fillna(10)
    data["breakout_strength"] = (100 - distance * 10).clip(0, 100).round(2)

    continuation_raw = data["pct_5d"].fillna(0) * 0.25 + data["pct_10d"].fillna(0) * 0.35 + data["pct_20d"].fillna(0) * 0.40
    data["continuation_score"] = _rank_score(continuation_raw)

    acceleration_raw = data["pct_5d"].fillna(0) - data["pct_10d"].fillna(0) / 2
    data["acceleration_score"] = _rank_score(acceleration_raw)
    return data


def _detect_leaders(pool: pd.DataFrame) -> pd.DataFrame:
    data = _stock_space_scores(pool)
    if data.empty:
        return pd.DataFrame(columns=LEADER_COLUMNS)

    data["momentum_rank"] = data["momentum_score"].rank(method="first", ascending=False)
    data["combined_rank"] = data["combined_score"].rank(method="first", ascending=False)
    combined_top_limit = max(1, int(np.ceil(len(data) * 0.05)))
    amount_mean = float(data["amount"].mean()) if "amount" in data else 0.0

    data["leader_strength_score"] = (
        data["momentum_score"].fillna(0) * 0.35
        + data["combined_score"].fillna(0) * 0.25
        + data["trend_score"].fillna(0) * 0.20
        + data["breakout_strength"].fillna(0) * 0.10
        + data["acceleration_score"].fillna(0) * 0.10
    ).round(2)

    data["is_leader"] = (
        ((data["momentum_rank"] <= 3) | (data["combined_rank"] <= combined_top_limit))
        & (data["momentum_score"] >= 85)
        & (data["trend_score"] >= 85)
        & (data["amount"] >= amount_mean * 1.2)
    )
    data["leader_rank"] = np.nan
    leader_order = data[data["is_leader"]].sort_values("leader_strength_score", ascending=False).index
    for rank, idx in enumerate(leader_order, start=1):
        data.at[idx, "leader_rank"] = rank

    data["risk_level"] = (
        (100 - data["trend_score"].fillna(50)) * 0.35
        + data["distance_to_20d_high"].fillna(10).clip(0, 20) * 2.5
        + (data["pct_5d"].fillna(0) > 35).astype(int) * 25
        + (data["combined_score"].fillna(50) < data["combined_score"].median()).astype(int) * 15
    ).clip(0, 100).round(2)

    data["risk_reason"] = ""
    data.loc[data["distance_to_20d_high"] > 8, "risk_reason"] += "距离高点偏远;"
    data.loc[data["pct_5d"] > 35, "risk_reason"] += "短期涨幅过大;"
    data.loc[data["trend_score"] < 70, "risk_reason"] += "趋势分偏弱;"
    data.loc[data["risk_reason"] == "", "risk_reason"] = "未触发主要风险"

    data["pool_type"] = "未分层"
    data.loc[data["is_leader"], "pool_type"] = "A类：龙头进攻池"
    data.loc[(data["pool_type"] == "未分层") & (data["trend_score"] >= 85) & (data["distance_to_20d_high"] <= 8), "pool_type"] = "B类：趋势持仓池"
    data.loc[(data["pool_type"] == "未分层") & ((data["momentum_score"] - data["trend_score"]).abs() >= 15), "pool_type"] = "C类：观察切换池"
    weak_mask = data["combined_score"] < data["combined_score"].median()
    data.loc[weak_mask & (data["risk_reason"] == "未触发主要风险"), "risk_reason"] = "综合分低于池内中位数，归入相对弱势"
    data.loc[(data["risk_level"] >= 60) | weak_mask, "pool_type"] = "D类：风险剔除池"

    result = data.copy()
    result["date"] = pool.get("date", pd.Series([""] * len(result))).astype(str).values
    return result[LEADER_COLUMNS].sort_values(["is_leader", "leader_strength_score"], ascending=[False, False])


def _final_convergence(target_date: str, pool: pd.DataFrame, cycle: Dict, leaders: pd.DataFrame, project_root: Path) -> Dict:
    """把所有分析收敛成唯一市场裁决和唯一股票归类，不改变交易执行。"""
    data = leaders.copy()
    if data.empty:
        empty_signal = {
            "date": target_date,
            "market_regime_final": "空仓（防守）",
            "one_sentence_summary": "数据不足，空仓观望",
            "allow_open_position": False,
            "risk_gate_reason": "趋势池为空",
        }
        return {"stocks": data, "signal": empty_signal, "leader_tier": data, "risk_gate": empty_signal}

    data["code"] = data["code"].astype(str).str.zfill(6)
    data["money_continuation_score"] = (
        pd.to_numeric(data["continuation_score"], errors="coerce").fillna(50) * 0.70
        + pd.to_numeric(data["acceleration_score"], errors="coerce").fillna(50) * 0.30
    ).round(2)
    data["master_score"] = (
        pd.to_numeric(data["momentum_score"], errors="coerce").fillna(0) * 0.25
        + pd.to_numeric(data["trend_score"], errors="coerce").fillna(0) * 0.25
        + float(cycle["cycle_strength"]) * 0.20
        + pd.to_numeric(data["leader_strength_score"], errors="coerce").fillna(0) * 0.15
        + data["money_continuation_score"] * 0.15
    ).round(2)

    previous_pool = _read_previous_pool(project_root, target_date)
    previous_scored = _stock_space_scores(previous_pool) if not previous_pool.empty else pd.DataFrame()
    previous_leaders = _detect_leaders(previous_pool) if not previous_pool.empty else pd.DataFrame()

    current_continuation = float(data["money_continuation_score"].mean()) if not data.empty else 0.0
    previous_continuation = float(previous_scored["continuation_score"].mean()) if not previous_scored.empty else current_continuation
    continuation_decline = current_continuation < previous_continuation

    current_leader_count = int(data["is_leader"].sum())
    previous_leader_count = int(previous_leaders["is_leader"].sum()) if not previous_leaders.empty else current_leader_count
    leader_decline = current_leader_count < previous_leader_count
    cycle_tide = str(cycle["market_cycle"]) == "退潮期"

    allow_open_position = not (continuation_decline or leader_decline or cycle_tide)
    gate_reasons = []
    if continuation_decline:
        gate_reasons.append("continuation下降")
    if leader_decline:
        gate_reasons.append("leader减少")
    if cycle_tide:
        gate_reasons.append("cycle进入退潮")
    risk_gate_reason = "；".join(gate_reasons) if gate_reasons else "未触发强制风控"

    momentum_strong = float(cycle["avg_momentum_score"]) >= 75
    continuation_strong = current_continuation >= 65
    divergence = float(cycle["market_divergence_std"]) >= 4
    cycle_name = str(cycle["market_cycle"])

    if not allow_open_position:
        market_regime_final = "空仓（防守）"
    elif cycle_name in ["主升期", "加速期"] and momentum_strong and continuation_strong:
        market_regime_final = "可重仓（进攻）"
    elif cycle_name == "启动期" and divergence:
        market_regime_final = "可参与（中性）"
    elif cycle_name == "退潮期":
        market_regime_final = "空仓（防守）"
    else:
        market_regime_final = "观望（轻仓）"

    data["leader_tier"] = ""
    leader_candidates = data[data["is_leader"]].sort_values("leader_strength_score", ascending=False)
    for order, idx in enumerate(leader_candidates.index, start=1):
        if order == 1 and data.at[idx, "leader_strength_score"] >= 88:
            data.at[idx, "leader_tier"] = "T0（绝对龙头）"
        elif order <= 3:
            data.at[idx, "leader_tier"] = "T1（核心龙头）"
        else:
            data.at[idx, "leader_tier"] = "T2（补涨龙头）"

    data["final_decision"] = "淘汰标的"
    attack_mask = (
        allow_open_position
        & data["is_leader"].astype(bool)
        & (data["money_continuation_score"] >= 65)
    )
    attack_indexes = data[attack_mask].sort_values("master_score", ascending=False).head(3).index
    data.loc[attack_indexes, "final_decision"] = "核心进攻标的"

    trend_mask = (
        (data["final_decision"] == "淘汰标的")
        & (pd.to_numeric(data["trend_score"], errors="coerce") >= 85)
        & (pd.to_numeric(data["risk_level"], errors="coerce") < 35)
    )
    data.loc[trend_mask, "final_decision"] = "趋势持有标的"

    if not previous_pool.empty and "combined_score" in previous_pool.columns:
        prev_score = previous_pool[["code", "combined_score"]].copy()
        prev_score["code"] = prev_score["code"].astype(str).str.zfill(6)
        prev_score = prev_score.rename(columns={"combined_score": "previous_combined_score"})
        data = data.merge(prev_score, on="code", how="left")
        data["score_change"] = pd.to_numeric(data["combined_score"], errors="coerce") - pd.to_numeric(data["previous_combined_score"], errors="coerce")
    else:
        data["score_change"] = pd.to_numeric(data["acceleration_score"], errors="coerce")

    observe_indexes = data[data["final_decision"] == "淘汰标的"].sort_values("score_change", ascending=False).head(10).index
    data.loc[observe_indexes, "final_decision"] = "观察标的"
    risk_mask = (pd.to_numeric(data["risk_level"], errors="coerce") >= 60) | (data["money_continuation_score"] < 45)
    data.loc[risk_mask, "final_decision"] = "淘汰标的"

    leader_tier = data[data["leader_tier"] != ""].copy()
    money_attack_status = "资金进攻" if current_continuation >= 65 and float(cycle["avg_momentum_score"]) >= 75 else "资金观望"
    mainline_status = "出现主线" if current_leader_count >= 2 and float(cycle["top_score_concentration"]) >= 105 else "主线不清晰"
    style_switch_status = "发生切换" if float(cycle["market_divergence_std"]) >= 8 else "未见明显切换"
    tide_status = "进入退潮" if cycle_tide else "未确认退潮"

    if market_regime_final == "可重仓（进攻）":
        one_sentence = "主升延续，可重仓核心龙头"
    elif market_regime_final == "可参与（中性）":
        one_sentence = "情绪分歧，可参与核心趋势"
    elif market_regime_final == "观望（轻仓）":
        one_sentence = "信号未共振，轻仓观察核心趋势"
    else:
        one_sentence = "退潮或风控触发，禁止开仓"

    signal = {
        "date": target_date,
        "market_regime_final": market_regime_final,
        "one_sentence_summary": one_sentence,
        "master_score_mean": round(float(data["master_score"].mean()), 2),
        "top_master_score": round(float(data["master_score"].max()), 2),
        "cycle": cycle_name,
        "cycle_strength": cycle["cycle_strength"],
        "avg_momentum_score": cycle["avg_momentum_score"],
        "avg_trend_score": cycle["avg_trend_score"],
        "avg_continuation_score": round(current_continuation, 2),
        "leader_count": current_leader_count,
        "money_attack_status": money_attack_status,
        "mainline_status": mainline_status,
        "style_switch_status": style_switch_status,
        "tide_status": tide_status,
        "allow_open_position": allow_open_position,
        "risk_gate_reason": risk_gate_reason,
    }
    risk_gate = {
        "date": target_date,
        "allow_open_position": allow_open_position,
        "risk_gate_action": "允许模拟开仓" if allow_open_position else "禁止开仓",
        "risk_gate_reason": risk_gate_reason,
        "continuation_decline": continuation_decline,
        "leader_decline": leader_decline,
        "cycle_tide": cycle_tide,
        "market_regime_final": market_regime_final,
    }
    return {"stocks": data, "signal": signal, "leader_tier": leader_tier, "risk_gate": risk_gate}


def _position_plan(cycle: Dict, leaders: pd.DataFrame) -> Dict:
    cycle_name = str(cycle["market_cycle"])
    base_position = {
        "冰点期": 30,
        "启动期": 60,
        "主升期": 80,
        "加速期": 90,
        "退潮期": 10,
    }.get(cycle_name, 50)

    leader_count = int(leaders["is_leader"].sum()) if not leaders.empty else 0
    high_risk_count = int((pd.to_numeric(leaders.get("risk_level", pd.Series(dtype=float)), errors="coerce") > 70).sum()) if not leaders.empty else 0
    risk_level = _clip(
        (100 - float(cycle["cycle_strength"])) * 0.45
        + (20 if cycle_name in ["退潮期", "冰点期"] else 0)
        + min(high_risk_count * 5, 25)
        - min(leader_count * 4, 12)
    )

    recommended = base_position
    reason = "按市场周期映射仓位"
    if cycle_name == "退潮期" or risk_level > 70:
        recommended = min(recommended, 20)
        reason = "退潮期或风险等级过高，强制降仓"
    elif risk_level > 55:
        recommended = min(recommended, 50)
        reason = "风险偏高，降低进攻仓位"

    if recommended <= 20:
        action = "空仓" if cycle_name == "退潮期" else "减仓"
    elif recommended < 50:
        action = "减仓"
    elif recommended > 75:
        action = "加仓"
    else:
        action = "维持"

    if cycle_name == "退潮期":
        mode = "防守（空仓）"
    elif cycle_name in ["主升期", "加速期"]:
        mode = "进攻（游资）"
    else:
        mode = "稳健（机构）"

    return {
        "recommended_position_ratio": int(recommended),
        "risk_level": risk_level,
        "risk_action": action,
        "risk_reason": reason,
        "trading_mode": mode,
    }


def _format_table(df: pd.DataFrame, columns: list[str], limit: int = 20) -> str:
    if df.empty:
        return "暂无数据"
    view = df[[column for column in columns if column in df.columns]].head(limit).fillna("")
    if view.empty:
        return "暂无数据"
    rows = [[str(value) for value in row] for row in view.to_numpy().tolist()]
    headers = list(view.columns)
    widths = [max(len(headers[i]), *(len(row[i]) for row in rows)) for i in range(len(headers))]
    lines = [
        "| " + " | ".join(headers[i].ljust(widths[i]) for i in range(len(headers))) + " |",
        "| " + " | ".join("-" * widths[i] for i in range(len(headers))) + " |",
    ]
    lines.extend("| " + " | ".join(row[i].ljust(widths[i]) for i in range(len(headers))) + " |" for row in rows)
    return "\n".join(lines)


def _write_decision_report(path: Path, cycle: Dict, risk: Dict, leaders: pd.DataFrame) -> None:
    attack = leaders[leaders["pool_type"] == "A类：龙头进攻池"].copy()
    trend = leaders[leaders["pool_type"] == "B类：趋势持仓池"].copy()
    watch = leaders[leaders["pool_type"] == "C类：观察切换池"].copy()
    risk_pool = leaders[leaders["pool_type"] == "D类：风险剔除池"].copy()

    content = f"""# 五合一交易决策报告

> 本报告只做【模拟】市场结构识别、风格识别、龙头识别、仓位控制和风险控制，不预测市场，不自动下单。

## 一、市场结构

- 当前市场周期：{cycle['market_cycle']}
- 当前情绪阶段强度：{cycle['cycle_strength']}
- 周期置信度：{cycle['cycle_stage_confidence']}%
- 动量均值变化率：{cycle['momentum_change_rate']}%
- 涨停家数估算：{cycle['limit_up_count']}
- Top score集中度：{cycle['top_score_concentration']}
- 市场分歧度：{cycle['market_divergence_std']}

## 二、仓位与风险

- 推荐仓位比例：{risk['recommended_position_ratio']}%
- 风险等级：{risk['risk_level']}
- 风险动作：{risk['risk_action']}
- 当前交易模式：{risk['trading_mode']}
- 风险原因：{risk['risk_reason']}

## 三、A类：龙头进攻池

{_format_table(attack, ['code', 'name', 'momentum_score', 'trend_score', 'combined_score', 'leader_rank', 'leader_strength_score'], 20)}

## 四、B类：趋势持仓池

{_format_table(trend.sort_values('trend_score', ascending=False), ['code', 'name', 'trend_score', 'combined_score', 'continuation_score', 'risk_level'], 20)}

## 五、C类：观察切换池

{_format_table(watch.sort_values('leader_strength_score', ascending=False), ['code', 'name', 'momentum_score', 'trend_score', 'combined_score', 'acceleration_score'], 20)}

## 六、D类：风险剔除池

{_format_table(risk_pool.sort_values('risk_level', ascending=False), ['code', 'name', 'combined_score', 'risk_level', 'risk_reason'], 20)}

## 七、最终回答

- 买什么：优先看 A 类龙头进攻池，其次看 B 类趋势持仓池。
- 什么时候买：只在当前周期允许的交易模式下做模拟观察，退潮期和高风险状态降低出手权限。
- 买多少：按推荐仓位比例执行模拟仓位约束，风险等级超过 70 或退潮期强制降仓。
"""
    path.write_text(content, encoding="utf-8")


def _write_final_decision_report(path: Path, final: Dict) -> None:
    stocks = final["stocks"]
    signal = final["signal"]
    risk_gate = final["risk_gate"]
    attack = stocks[stocks["final_decision"] == "核心进攻标的"].sort_values("master_score", ascending=False)
    trend = stocks[stocks["final_decision"] == "趋势持有标的"].sort_values("master_score", ascending=False)
    observe = stocks[stocks["final_decision"] == "观察标的"].sort_values("score_change", ascending=False)
    eliminate = stocks[stocks["final_decision"] == "淘汰标的"].sort_values(["risk_level", "master_score"], ascending=[False, True])

    content = f"""# 一体化交易决策报告

> 本报告只输出【模拟】统一裁决：今天是否值得参与市场。不预测市场，不自动下单，不连接券商。

## 今日市场一句话总结

{signal['one_sentence_summary']}

## 唯一核心结论

- 今日是否值得参与市场：{signal['market_regime_final']}
- 风控闸门：{risk_gate['risk_gate_action']}
- 风控原因：{risk_gate['risk_gate_reason']}
- master_score均值：{signal['master_score_mean']}
- 最高master_score：{signal['top_master_score']}

## 资金行为解释

- 当前资金是否进攻：{signal['money_attack_status']}
- 是否出现主线：{signal['mainline_status']}
- 是否发生切换：{signal['style_switch_status']}
- 是否进入退潮：{signal['tide_status']}

## 核心进攻标的（最多3只）

{_format_table(attack, ['code', 'name', 'master_score', 'leader_tier', 'leader_strength_score', 'money_continuation_score'], 3)}

## 趋势持有标的

{_format_table(trend, ['code', 'name', 'master_score', 'trend_score', 'money_continuation_score', 'risk_level'], 20)}

## 观察标的

{_format_table(observe, ['code', 'name', 'master_score', 'score_change', 'acceleration_score', 'money_continuation_score'], 20)}

## 淘汰标的

{_format_table(eliminate, ['code', 'name', 'master_score', 'risk_level', 'risk_reason'], 20)}

## 强制风控规则

- continuation下降：{risk_gate['continuation_decline']}
- leader减少：{risk_gate['leader_decline']}
- cycle进入退潮：{risk_gate['cycle_tide']}
- 任一触发时：禁止开仓
"""
    path.write_text(content, encoding="utf-8")


def build_trade_decision(target_date: str, pool: pd.DataFrame, base_cycle: Dict, project_root: Path) -> Dict:
    """五合一决策引擎：只做分析输出，不改变选股、回测、成交执行逻辑。"""
    report_dir = project_root
    cycle_report_path = report_dir / "cycle_strength_report.csv"
    leader_path = report_dir / "leader_detection.csv"
    risk_path = report_dir / "risk_control_report.csv"
    decision_path = report_dir / "trade_decision_report.md"
    final_decision_path = report_dir / "final_decision_report.md"
    master_signal_path = report_dir / "market_master_signal.csv"
    leader_tier_path = report_dir / "leader_tier.csv"
    risk_gate_path = report_dir / "risk_gate.csv"

    enhanced_cycle = _enhanced_cycle(target_date, pool, project_root, base_cycle)
    leaders = _detect_leaders(pool)
    position = _position_plan(enhanced_cycle, leaders)
    final = _final_convergence(target_date, pool, enhanced_cycle, leaders, project_root)

    cycle_row = enhanced_cycle | {
        "trading_mode": position["trading_mode"],
        "recommended_position_ratio": position["recommended_position_ratio"],
        "risk_level": position["risk_level"],
        "risk_action": position["risk_action"],
    }

    attack_count = int((leaders["pool_type"] == "A类：龙头进攻池").sum()) if not leaders.empty else 0
    trend_count = int((leaders["pool_type"] == "B类：趋势持仓池").sum()) if not leaders.empty else 0
    watch_count = int((leaders["pool_type"] == "C类：观察切换池").sum()) if not leaders.empty else 0
    risk_count = int((leaders["pool_type"] == "D类：风险剔除池").sum()) if not leaders.empty else 0
    risk_row = {
        "date": target_date,
        "market_cycle": enhanced_cycle["market_cycle"],
        "cycle_strength": enhanced_cycle["cycle_strength"],
        "recommended_position_ratio": position["recommended_position_ratio"],
        "risk_level": position["risk_level"],
        "risk_action": position["risk_action"],
        "risk_reason": position["risk_reason"],
        "leader_count": attack_count,
        "trend_count": trend_count,
        "watch_count": watch_count,
        "risk_count": risk_count,
    }

    pd.DataFrame([cycle_row], columns=CYCLE_STRENGTH_COLUMNS).to_csv(cycle_report_path, index=False, encoding="utf-8-sig")
    leaders.to_csv(leader_path, index=False, encoding="utf-8-sig")
    pd.DataFrame([risk_row], columns=RISK_CONTROL_COLUMNS).to_csv(risk_path, index=False, encoding="utf-8-sig")
    _write_decision_report(decision_path, enhanced_cycle, position, leaders)
    pd.DataFrame([final["signal"]], columns=MARKET_MASTER_SIGNAL_COLUMNS).to_csv(master_signal_path, index=False, encoding="utf-8-sig")
    final["leader_tier"].to_csv(leader_tier_path, index=False, encoding="utf-8-sig")
    pd.DataFrame([final["risk_gate"]], columns=RISK_GATE_COLUMNS).to_csv(risk_gate_path, index=False, encoding="utf-8-sig")
    _write_final_decision_report(final_decision_path, final)

    return {
        "cycle": enhanced_cycle,
        "position": position,
        "leaders": leaders,
        "final": final,
        "paths": {
            "cycle_strength_report": cycle_report_path,
            "leader_detection": leader_path,
            "risk_control_report": risk_path,
            "trade_decision_report": decision_path,
            "final_decision_report": final_decision_path,
            "market_master_signal": master_signal_path,
            "leader_tier": leader_tier_path,
            "risk_gate": risk_gate_path,
        },
        "counts": {
            "leader_count": attack_count,
            "trend_count": trend_count,
            "watch_count": watch_count,
            "risk_count": risk_count,
        },
    }

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

import pandas as pd


TRADE_LOG_COLUMNS = [
    "date",
    "stock_code",
    "action",
    "position_size",
    "trigger_reason",
    "cycle_state",
    "master_score",
]

ORDER_COLUMNS = [
    "date",
    "stock_code",
    "action",
    "position_ratio",
    "score",
    "cycle",
    "reason",
]

POSITION_PLAN_COLUMNS = [
    "date",
    "stock_code",
    "name",
    "position_ratio",
    "position_type",
    "order_priority",
    "reason",
]


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _position_size(cycle_state: str, row: pd.Series) -> str:
    is_leader = bool(row.get("is_leader", False)) or str(row.get("leader_tier", "")) != ""
    is_trend = str(row.get("final_decision", "")) == "趋势持有标的" or _safe_float(row.get("trend_score")) >= 85

    if cycle_state == "退潮期":
        return "zero"
    if cycle_state in ["主升期", "加速期"] and is_leader:
        return "full"
    if cycle_state == "启动期" and is_trend:
        return "medium"
    if cycle_state in ["冰点期", "震荡期"] or not is_leader:
        return "small"
    return "medium"


def _total_position_limit(cycle_state: str) -> float:
    if cycle_state in ["主升期", "加速期"]:
        return 0.90
    if cycle_state == "启动期":
        return 0.60
    if cycle_state in ["震荡期", "冰点期"]:
        return 0.30
    if cycle_state == "退潮期":
        return 0.0
    return 0.30


def _single_position_ratio(row: pd.Series, cycle_state: str, remaining: float) -> tuple[float, str]:
    if remaining <= 0 or cycle_state == "退潮期":
        return 0.0, "zero"

    is_leader = bool(row.get("is_leader", False)) or str(row.get("leader_tier", "")) != ""
    is_trend = str(row.get("final_decision", "")) == "趋势持有标的" or _safe_float(row.get("trend_score")) >= 85

    if is_leader:
        ratio = min(0.40, remaining)
        return round(ratio, 4), "leader"
    if is_trend:
        ratio = min(0.20, remaining)
        return round(ratio, 4), "trend"
    return 0.0, "observe"


def _priority(row: pd.Series) -> int:
    score = _safe_float(row.get("master_score"))
    if score >= 90:
        return 1
    if score >= 85:
        return 2
    if score >= 80:
        return 3
    if score >= 70:
        return 4
    return 5


def _hold_action(row: pd.Series, cycle_state: str, cycle_decline: bool) -> str:
    score_change = _safe_float(row.get("score_change"))
    if cycle_state == "退潮期" or cycle_decline:
        return "清仓"
    if score_change > 0:
        return "加仓"
    if score_change < 0:
        return "减仓"
    return "持有"


def _action(row: pd.Series, cycle_state: str, allow_open_position: bool, continuation_threshold: float) -> tuple[str, str]:
    master_score = _safe_float(row.get("master_score"))
    continuation = _safe_float(row.get("money_continuation_score", row.get("continuation_score")))
    final_decision = str(row.get("final_decision", ""))
    leader_or_trend = (
        bool(row.get("is_leader", False))
        or str(row.get("leader_tier", "")) != ""
        or final_decision in ["核心进攻标的", "趋势持有标的"]
        or _safe_float(row.get("trend_score")) >= 85
    )

    if cycle_state == "退潮期":
        return "SKIP", "退潮周期，强制SKIP"
    if not allow_open_position and master_score > 85:
        return "SKIP", "风控闸门关闭，禁止开仓"
    if (
        master_score > 85
        and master_score > 80
        and leader_or_trend
        and continuation > continuation_threshold
    ):
        return "BUY", "master_score>85，leader/trend成立，资金延续达标"
    if 70 <= master_score <= 85:
        return "HOLD", "master_score位于70~85，保持观察或持有"
    if final_decision == "淘汰标的" and master_score < 70:
        return "SELL", "淘汰标的且master_score<70，模拟清仓"
    return "SKIP", "未满足BUY触发条件"


def _no_trade_check(
    cycle_state: str,
    records: pd.DataFrame,
    risk_level: float,
    continuation_threshold: float,
) -> tuple[bool, str]:
    reasons = []
    if cycle_state == "退潮期":
        reasons.append("market_cycle=退潮")
    if records.empty:
        reasons.append("无可评估标的")
    else:
        avg_continuation = pd.to_numeric(records["continuation_score"], errors="coerce").mean()
        leader_count = int((records.get("is_leader", pd.Series(dtype=bool)).fillna(False).astype(bool)).sum()) if "is_leader" in records.columns else 0
        if avg_continuation < continuation_threshold:
            reasons.append(f"continuation_score<{continuation_threshold}")
        if leader_count == 0:
            reasons.append("leader数量=0")
    if risk_level > 70:
        reasons.append("risk_level>70")
    return bool(reasons), "；".join(reasons) if reasons else "通过交易日过滤器"


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


def _write_execution_report(path: Path, execution: Dict) -> None:
    records = execution["records"]
    orders = execution["orders"]
    executable = records[records["action"] == "BUY"].sort_values("master_score", ascending=False)
    blocked = records[records["action"].isin(["SKIP", "SELL"])].sort_values(["action", "master_score"], ascending=[True, False])

    content = f"""# 交易执行闭环报告

> 本报告只生成【模拟】交易动作，不自动下单，不连接券商。

## 最终执行结论

- 今日是否可以交易：{execution['can_trade_today']}
- 今日是否 NO TRADE DAY：{execution['no_trade_day']}
- 今日交易强度：{execution['trade_intensity']}
- 可执行订单数量：{execution['order_count']}
- 最大仓位：{execution['max_position_ratio']}%
- 市场状态：{execution['market_regime_final']}
- 周期状态：{execution['cycle_state']}
- 风险等级：{execution['risk_level']}
- 风控原因：{execution['risk_gate_reason']}

## 可执行订单 Order Packet

{_format_table(orders, ['stock_code', 'action', 'position_ratio', 'score', 'cycle', 'reason'], 20)}

## 可执行标的列表

{_format_table(executable, ['stock_code', 'name', 'action', 'position_size', 'master_score', 'hold_action', 'trigger_reason'], 20)}

## 禁止交易标的列表

{_format_table(blocked, ['stock_code', 'name', 'action', 'position_size', 'master_score', 'hold_action', 'trigger_reason'], 20)}

## 仓位建议

- full：主升/加速 + 龙头，单票模拟高关注，组合仓位80~100%
- medium：启动 + 趋势，组合仓位50~80%
- small：震荡或非龙头，组合仓位10~50%
- zero：退潮或风控闸门关闭，组合仓位0
"""
    path.write_text(content, encoding="utf-8")


def _write_risk_check_report(path: Path, execution: Dict) -> None:
    content = f"""# Order Engine 风险检查报告

> 本报告只用于【模拟】订单生成前检查，不自动下单。

- 日期：{execution['date']}
- 今日是否可交易：{execution['can_trade_today']}
- 今日是否 NO TRADE DAY：{execution['no_trade_day']}
- 风险等级：{execution['risk_level']}
- 周期状态：{execution['cycle_state']}
- 风险检查结论：{execution['risk_gate_reason']}
- 可执行订单数量：{execution['order_count']}
- 最大仓位：{execution['max_position_ratio']}%

## 过滤规则

- market_cycle = 退潮：禁止交易
- continuation_score < threshold：禁止交易
- leader 数量 = 0：禁止交易
- risk_level > 70：禁止交易
"""
    path.write_text(content, encoding="utf-8")


def build_execution_layer(target_date: str, decision: Dict, project_root: Path, continuation_threshold: float = 60.0) -> Dict:
    """执行层只消费最终决策，不修改评分、回测、forward test 或已有模型。"""
    final = decision["final"]
    stocks = final["stocks"].copy()
    signal = final["signal"]
    risk_gate = final["risk_gate"]
    position = decision.get("position", {})
    cycle_state = str(signal.get("cycle", ""))
    market_regime_final = str(signal.get("market_regime_final", "空仓（防守）"))
    allow_open_position = bool(risk_gate.get("allow_open_position", False))
    risk_level = _safe_float(position.get("risk_level"))
    can_trade_today = "YES" if allow_open_position and market_regime_final != "空仓（防守）" else "NO"
    cycle_decline = bool(risk_gate.get("cycle_tide", False))

    rows = []
    if not stocks.empty:
        for _, row in stocks.iterrows():
            action, reason = _action(row, cycle_state, allow_open_position, continuation_threshold)
            hold_action = _hold_action(row, cycle_state, cycle_decline)
            position_size = _position_size(cycle_state, row)
            if can_trade_today == "NO":
                position_size = "zero"
            if can_trade_today == "NO" and action == "BUY":
                action = "SKIP"
                reason = "今日不允许交易，BUY信号降级为SKIP"
            rows.append(
                {
                    "date": target_date,
                    "stock_code": str(row.get("code", "")).zfill(6),
                    "name": row.get("name", ""),
                    "action": action,
                    "position_size": position_size,
                    "hold_action": hold_action,
                    "trigger_reason": reason,
                    "cycle_state": cycle_state,
                    "market_regime_final": market_regime_final,
                    "is_leader": bool(row.get("is_leader", False)),
                    "leader_tier": row.get("leader_tier", ""),
                    "final_decision": row.get("final_decision", ""),
                    "master_score": round(_safe_float(row.get("master_score")), 2),
                    "continuation_score": round(_safe_float(row.get("money_continuation_score", row.get("continuation_score"))), 2),
                }
            )

    records = pd.DataFrame(rows)
    if records.empty:
        records = pd.DataFrame(columns=[
            "date",
            "stock_code",
            "name",
            "action",
            "position_size",
            "hold_action",
            "trigger_reason",
            "cycle_state",
            "market_regime_final",
            "is_leader",
            "leader_tier",
            "final_decision",
            "master_score",
            "continuation_score",
        ])

    no_trade_day, no_trade_reason = _no_trade_check(cycle_state, records, risk_level, continuation_threshold)
    if not allow_open_position or market_regime_final == "空仓（防守）":
        gate_reason = risk_gate.get("risk_gate_reason", "最终风控闸门关闭")
        no_trade_day = True
        no_trade_reason = f"{no_trade_reason}；{gate_reason}" if no_trade_reason != "通过交易日过滤器" else gate_reason
    if no_trade_day:
        can_trade_today = "NO"
        records["position_size"] = "zero"
        if not records.empty:
            records.loc[records["action"] == "BUY", "action"] = "SKIP"

    total_limit = 0.0 if can_trade_today == "NO" else _total_position_limit(cycle_state)
    remaining = total_limit
    order_rows = []
    position_rows = []
    candidates = records.sort_values("master_score", ascending=False).copy()
    for _, item in candidates.iterrows():
        action = str(item.get("action", "SKIP"))
        score = _safe_float(item.get("master_score"))
        reason = str(item.get("trigger_reason", ""))
        if can_trade_today == "NO" or no_trade_day:
            order_action = "SKIP"
            ratio = 0.0
            position_type = "zero"
            reason = no_trade_reason if no_trade_day else "今日不可交易，禁止生成买入订单"
        elif action == "BUY":
            ratio, position_type = _single_position_ratio(item, cycle_state, remaining)
            remaining = max(0.0, remaining - ratio)
            order_action = "BUY" if ratio > 0 else "SKIP"
            if ratio <= 0:
                reason = "总仓位额度已用完"
        elif action == "SELL":
            ratio = 0.0
            position_type = "zero"
            order_action = "SELL"
        else:
            ratio = 0.0
            position_type = "observe"
            order_action = "SKIP"

        if order_action in ["BUY", "SELL"]:
            price_type = "limit"
        else:
            price_type = "market"

        order_rows.append(
            {
                "date": target_date,
                "stock_code": item.get("stock_code", ""),
                "action": order_action,
                "position_ratio": round(ratio, 4),
                "score": round(score, 2),
                "cycle": cycle_state,
                "reason": reason,
                "price_type": price_type,
                "priority": _priority(item),
            }
        )
        position_rows.append(
            {
                "date": target_date,
                "stock_code": item.get("stock_code", ""),
                "name": item.get("name", ""),
                "position_ratio": round(ratio, 4),
                "position_type": position_type,
                "order_priority": _priority(item),
                "reason": reason,
            }
        )

    order_packets = pd.DataFrame(order_rows)
    if order_packets.empty:
        order_packets = pd.DataFrame(columns=[*ORDER_COLUMNS, "price_type", "priority"])
    position_plan = pd.DataFrame(position_rows, columns=POSITION_PLAN_COLUMNS)

    buy_count = int((records["action"] == "BUY").sum()) if not records.empty else 0
    trade_intensity = 0 if can_trade_today == "NO" else min(100, round(buy_count * 20 + _safe_float(signal.get("top_master_score")) - 60, 2))
    order_count = int((order_packets["action"].isin(["BUY", "SELL"])).sum()) if not order_packets.empty else 0
    max_position_ratio = round(float(pd.to_numeric(order_packets.get("position_ratio", pd.Series(dtype=float)), errors="coerce").max() * 100), 2) if order_count else 0.0

    log_path = project_root / "trade_log.csv"
    report_path = project_root / "execution_report.md"
    orders_csv_path = project_root / f"orders_{target_date}.csv"
    orders_json_path = project_root / f"orders_{target_date}.json"
    position_plan_path = project_root / "position_plan.csv"
    risk_check_path = project_root / "risk_check_report.md"
    log_rows = records.rename(columns={"stock_code": "stock_code"})[
        ["date", "stock_code", "action", "position_size", "trigger_reason", "cycle_state", "master_score"]
    ]
    log_rows.to_csv(log_path, index=False, encoding="utf-8-sig")
    order_packets[ORDER_COLUMNS].to_csv(orders_csv_path, index=False, encoding="utf-8-sig")
    orders_json_path.write_text(
        json.dumps(order_packets.to_dict(orient="records"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    position_plan.to_csv(position_plan_path, index=False, encoding="utf-8-sig")

    result = {
        "date": target_date,
        "can_trade_today": can_trade_today,
        "no_trade_day": "YES" if no_trade_day else "NO",
        "trade_intensity": trade_intensity,
        "order_count": order_count,
        "max_position_ratio": max_position_ratio,
        "risk_level": risk_level,
        "market_regime_final": market_regime_final,
        "cycle_state": cycle_state,
        "risk_gate_reason": no_trade_reason if no_trade_day else risk_gate.get("risk_gate_reason", ""),
        "records": records,
        "orders": order_packets[ORDER_COLUMNS],
        "position_plan": position_plan,
        "paths": {
            "trade_log": log_path,
            "execution_report": report_path,
            "orders_csv": orders_csv_path,
            "orders_json": orders_json_path,
            "position_plan": position_plan_path,
            "risk_check_report": risk_check_path,
        },
    }
    _write_execution_report(report_path, result)
    _write_risk_check_report(risk_check_path, result)
    return result

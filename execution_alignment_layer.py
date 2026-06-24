from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict

import pandas as pd


SIGNAL_QUALITY_COLUMNS = [
    "date",
    "stock_code",
    "name",
    "original_action",
    "aligned_action",
    "signal_filled_probability",
    "signal_quality_score",
    "entry_price_slippage",
    "adjusted_entry_price",
    "signal_decay_score",
    "slippage_risk",
    "risk_level",
    "market_cycle",
    "alignment_reason",
]


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


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
    except Exception:
        return pd.DataFrame()
    data["code"] = data["code"].astype(str).str.zfill(6)
    return data


def _filled_probability(row: pd.Series) -> str:
    amount = _safe_float(row.get("amount"))
    pct_chg = _safe_float(row.get("pct_chg"))
    turnover = _safe_float(row.get("turnover"))
    pct_5d = _safe_float(row.get("pct_5d"))
    pct_20d = _safe_float(row.get("pct_20d"))
    volatility = abs(pct_20d) / 20 if pct_20d else abs(pct_5d) / 5

    is_limit = pct_chg >= 9.8 or pct_chg <= -9.8
    is_one_word_board = pct_chg >= 9.8 and turnover <= 0.03
    is_acceleration_board = pct_chg >= 7 and pct_5d >= 20

    if is_one_word_board or pct_chg <= -9.8:
        return "LOW"
    if amount >= 1_000_000_000 and not is_limit and volatility <= 5:
        return "HIGH"
    if amount >= 500_000_000 and not is_one_word_board and not is_acceleration_board:
        return "MEDIUM"
    return "LOW"


def _slippage(row: pd.Series) -> tuple[float, str]:
    leader_tier = str(row.get("leader_tier", ""))
    final_decision = str(row.get("final_decision", ""))
    if leader_tier or final_decision == "核心进攻标的":
        return 0.015, "HIGH"
    if final_decision == "趋势持有标的" or _safe_float(row.get("trend_score")) >= 85:
        return 0.008, "MEDIUM"
    return 0.003, "LOW"


def _signal_decay(row: pd.Series, previous: pd.DataFrame, signal_date: str) -> float:
    try:
        signal_age = max(0, (datetime.now() - datetime.strptime(signal_date, "%Y%m%d")).days)
    except Exception:
        signal_age = 0

    price_deviation = _safe_float(row.get("distance_to_20d_high"))
    momentum_change = 0.0
    continuation_change = 0.0
    code = str(row.get("stock_code", "")).zfill(6)
    if not previous.empty and code:
        match = previous[previous["code"].astype(str).str.zfill(6) == code]
        if not match.empty:
            prev = match.iloc[0]
            momentum_change = _safe_float(row.get("momentum_score")) - _safe_float(prev.get("momentum_score"))
            current_continuation = _safe_float(row.get("money_continuation_score", row.get("continuation_score")))
            prev_continuation = (
                _safe_float(prev.get("pct_5d")) * 0.25
                + _safe_float(prev.get("pct_10d")) * 0.35
                + _safe_float(prev.get("pct_20d")) * 0.40
            )
            continuation_change = current_continuation - prev_continuation

    decay = signal_age * 2 + max(0.0, price_deviation) * 2 + max(0.0, -momentum_change) * 1.5 + max(0.0, -continuation_change) * 0.8
    return round(min(100.0, max(0.0, decay)), 2)


def _quality_score(filled_probability: str, decay: float, slippage_rate: float, risk_level: float, market_cycle: str) -> float:
    base = {"HIGH": 90, "MEDIUM": 70, "LOW": 35}.get(filled_probability, 35)
    score = base - decay * 0.45 - slippage_rate * 1000 - max(0.0, risk_level - 40) * 0.5
    if market_cycle == "退潮期":
        score -= 40
    return round(min(100.0, max(0.0, score)), 2)


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


def _write_report(path: Path, alignment: Dict) -> None:
    quality = alignment["quality"]
    executable = quality[quality["aligned_action"].isin(["BUY", "SELL"])] if not quality.empty else pd.DataFrame()
    blocked = quality[quality["aligned_action"] == "SKIP"] if not quality.empty else pd.DataFrame()
    content = f"""# Execution Alignment 实盘对齐报告

> 本报告只验证【模拟】订单信号在真实市场中的可执行性，不接券商、不自动下单。

## 最终对齐结论

- 今日信号是否真实可交易：{alignment['real_tradable_today']}
- 信号质量评分：{alignment['signal_quality_score']}
- 是否存在滑点风险：{alignment['has_slippage_risk']}
- 是否建议放弃交易：{alignment['should_abandon_trade']}
- 对齐原因：{alignment['alignment_reason']}

## 可真实执行信号

{_format_table(executable, ['stock_code', 'name', 'aligned_action', 'signal_filled_probability', 'signal_quality_score', 'entry_price_slippage', 'adjusted_entry_price'], 20)}

## 被实盘过滤信号

{_format_table(blocked, ['stock_code', 'name', 'original_action', 'aligned_action', 'signal_filled_probability', 'signal_decay_score', 'alignment_reason'], 20)}
"""
    path.write_text(content, encoding="utf-8")


def build_execution_alignment(
    target_date: str,
    pool: pd.DataFrame,
    decision: Dict,
    execution: Dict,
    project_root: Path,
    decay_threshold: float = 60.0,
) -> Dict:
    """实盘对齐层：只验证订单可执行性，不修改订单引擎和交易框架。"""
    orders = execution.get("orders", pd.DataFrame()).copy()
    final_stocks = decision["final"]["stocks"].copy()
    market_cycle = str(decision["cycle"].get("market_cycle", ""))
    risk_level = _safe_float(decision.get("position", {}).get("risk_level"))
    previous = _read_previous_pool(project_root, target_date)

    pool_view = pool.copy()
    if not pool_view.empty:
        pool_view["code"] = pool_view["code"].astype(str).str.zfill(6)
    if not final_stocks.empty:
        final_stocks["code"] = final_stocks["code"].astype(str).str.zfill(6)
    if not orders.empty:
        orders["stock_code"] = orders["stock_code"].astype(str).str.zfill(6)

    merged = orders.merge(final_stocks, left_on="stock_code", right_on="code", how="left", suffixes=("", "_final"))
    merged = merged.merge(pool_view, left_on="stock_code", right_on="code", how="left", suffixes=("", "_pool"))

    rows = []
    for _, row in merged.iterrows():
        filled = _filled_probability(row)
        slippage_rate, slippage_risk = _slippage(row)
        close_price = _safe_float(row.get("close"))
        adjusted_price = round(close_price * (1 + slippage_rate), 2) if close_price else 0.0
        decay = _signal_decay(row, previous, target_date)
        row_risk = max(risk_level, _safe_float(row.get("risk_level")))
        quality_score = _quality_score(filled, decay, slippage_rate, row_risk, market_cycle)

        original_action = str(row.get("action", "SKIP"))
        reasons = []
        aligned_action = original_action
        if filled == "LOW":
            reasons.append("可成交性LOW")
        if decay >= decay_threshold:
            reasons.append("信号衰减超阈值")
        if row_risk >= 70:
            reasons.append("risk_level>=70")
        if market_cycle == "退潮期":
            reasons.append("market_cycle=退潮")
        if original_action == "SKIP":
            reasons.append("原始订单为SKIP")
        if reasons:
            aligned_action = "SKIP"
        rows.append(
            {
                "date": target_date,
                "stock_code": row.get("stock_code", ""),
                "name": row.get("name", row.get("name_pool", "")),
                "original_action": original_action,
                "aligned_action": aligned_action,
                "signal_filled_probability": filled,
                "signal_quality_score": quality_score,
                "entry_price_slippage": round(slippage_rate * 100, 2),
                "adjusted_entry_price": adjusted_price,
                "signal_decay_score": decay,
                "slippage_risk": slippage_risk,
                "risk_level": round(row_risk, 2),
                "market_cycle": market_cycle,
                "alignment_reason": "；".join(reasons) if reasons else "通过实盘可执行过滤器",
            }
        )

    quality = pd.DataFrame(rows, columns=SIGNAL_QUALITY_COLUMNS)
    if quality.empty:
        real_tradable = "NO"
        score = 0.0
        has_slippage_risk = "NO"
        abandon = "YES"
        reason = "无订单信号"
    else:
        executable_count = int(quality["aligned_action"].isin(["BUY", "SELL"]).sum())
        score = round(float(pd.to_numeric(quality["signal_quality_score"], errors="coerce").mean()), 2)
        has_slippage_risk = "YES" if (quality["slippage_risk"] == "HIGH").any() else "NO"
        real_tradable = "YES" if executable_count > 0 and score >= 60 else "NO"
        abandon = "YES" if real_tradable == "NO" or has_slippage_risk == "YES" else "NO"
        reason = "存在真实可执行订单" if real_tradable == "YES" else "没有通过实盘过滤的订单"

    quality_path = project_root / "signal_quality_report.csv"
    report_path = project_root / "execution_feasibility_report.md"
    quality.to_csv(quality_path, index=False, encoding="utf-8-sig")
    result = {
        "real_tradable_today": real_tradable,
        "signal_quality_score": score,
        "has_slippage_risk": has_slippage_risk,
        "should_abandon_trade": abandon,
        "alignment_reason": reason,
        "quality": quality,
        "paths": {
            "signal_quality_report": quality_path,
            "execution_feasibility_report": report_path,
        },
    }
    _write_report(report_path, result)
    return result

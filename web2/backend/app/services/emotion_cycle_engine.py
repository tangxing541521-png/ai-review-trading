from __future__ import annotations

import csv
import json
from pathlib import Path

from app.core.config import settings


def _read_csv_rows(path: Path) -> list[dict]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            return list(csv.DictReader(file))
    except Exception:
        return []


def _latest_csv_rows(pattern: str) -> list[dict]:
    paths = sorted(settings.project_root.glob(pattern))
    return _read_csv_rows(paths[-1]) if paths else []


def _latest_json(pattern: str) -> dict:
    paths = sorted(settings.project_root.glob(pattern))
    if not paths:
        return {}
    try:
        return json.loads(paths[-1].read_text(encoding="utf-8"))
    except Exception:
        return {}


def _last_row(path: Path) -> dict:
    rows = _read_csv_rows(path)
    return rows[-1] if rows else {}


def _to_float(value, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except Exception:
        return default


def _to_bool(value) -> bool | None:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y", "允许", "可交易"}:
        return True
    if text in {"false", "0", "no", "n", "禁止", "禁止开仓"}:
        return False
    return None


def _risk_label(score: float) -> str:
    if score >= 70:
        return "高"
    if score >= 35:
        return "中"
    return "低"


def _trade_mode(stage: str, risk_score: float, allow_open: bool) -> tuple[str, str]:
    if not allow_open or stage in {"退潮", "冰点"} or risk_score >= 75:
        return "空仓", "0%"
    if stage == "分歧":
        return "观察", "0%"
    if stage == "修复":
        return "轻仓", "30%"
    if stage == "一致":
        return "进攻", "60%"
    if stage == "高潮":
        return "轻仓", "30%"
    return "观察", "0%"


def build_emotion_cycle(user: dict | None = None) -> dict:
    cycle_row = _last_row(settings.project_root / "cycle_strength_report.csv")
    master_row = _last_row(settings.project_root / "market_master_signal.csv")
    risk_row = _last_row(settings.project_root / "risk_gate.csv")
    health_row = _last_row(settings.project_root / "strategy_health_score.csv")
    frozen = _latest_json("frozen_decisions/orders_*.json")
    leader_rows = _read_csv_rows(settings.project_root / "leader_detection.csv")
    trend_rows = _latest_csv_rows("data/processed/trend_core_pool_*.csv")

    allow_from_master = _to_bool(master_row.get("allow_open_position"))
    allow_from_risk = _to_bool(risk_row.get("allow_open_position"))
    allow_open = allow_from_master if allow_from_master is not None else True
    if allow_from_risk is False:
        allow_open = False

    orders = frozen.get("orders", []) if isinstance(frozen, dict) else []
    if orders and all(str(order.get("action", "")).upper() in {"SKIP", "NO_TRADE"} for order in orders):
        allow_open = False

    cycle_name = str(master_row.get("cycle") or cycle_row.get("market_cycle") or "")
    market_regime = str(master_row.get("market_regime_final") or risk_row.get("market_regime_final") or "")
    risk_gate_reason = str(risk_row.get("risk_gate_reason") or master_row.get("risk_gate_reason") or "")
    cycle_tide = _to_bool(risk_row.get("cycle_tide")) is True or "退潮" in cycle_name or "退潮" in market_regime

    cycle_strength = _to_float(cycle_row.get("cycle_strength") or master_row.get("cycle_strength"))
    master_mean = _to_float(master_row.get("master_score_mean"))
    top_master = _to_float(master_row.get("top_master_score"))
    avg_momentum = _to_float(cycle_row.get("avg_momentum_score") or master_row.get("avg_momentum_score"))
    avg_trend = _to_float(cycle_row.get("avg_trend_score") or master_row.get("avg_trend_score"))
    concentration = _to_float(cycle_row.get("top_score_concentration"))
    divergence = _to_float(cycle_row.get("market_divergence_std"))
    health_score = _to_float(health_row.get("strategy_health_score"))
    risk_score = _to_float(cycle_row.get("risk_level"))

    leader_count = int(_to_float(master_row.get("leader_count")))
    if leader_count <= 0:
        leader_count = sum(1 for row in leader_rows if str(row.get("is_leader", "")).lower() == "true")

    high_score_count = sum(
        1
        for row in trend_rows
        if max(
            _to_float(row.get("combined_score")),
            _to_float(row.get("trend_score")),
            _to_float(row.get("momentum_score")),
        )
        >= 85
    )
    hot_theme_count = 0
    if high_score_count >= 12:
        hot_theme_count = 2
    elif high_score_count >= 5:
        hot_theme_count = 1

    stage_reason: list[str] = []
    warning: list[str] = []

    if not allow_open:
        if cycle_tide or "退潮" in risk_gate_reason:
            stage = "退潮"
            stage_reason.append("交易许可为 NO，且风控或周期信号指向退潮。")
        elif cycle_strength < 45 or health_score < 40:
            stage = "冰点"
            stage_reason.append("交易许可为 NO，同时市场强度或策略健康分偏低。")
        else:
            stage = "分歧"
            stage_reason.append("交易许可为 NO，但市场强度尚未进入冰点，按分歧处理。")
    elif health_score and health_score < 40 and cycle_strength < 60:
        stage = "冰点"
        stage_reason.append("策略健康分低且市场强度不足，情绪偏冰点。")
    elif cycle_tide:
        stage = "退潮"
        stage_reason.append("周期字段或风险闸门显示退潮。")
    elif leader_count >= 3 and hot_theme_count >= 1 and risk_score < 35 and cycle_strength >= 55:
        stage = "修复"
        stage_reason.append("T1/龙头数量增加且主线热度恢复，市场处于修复。")
    elif concentration >= 90 and risk_score >= 35:
        stage = "分歧"
        stage_reason.append("高分股集中但风险同步升高，强势内部存在分歧。")
    elif hot_theme_count >= 2 and risk_score < 35 and cycle_strength >= 75:
        stage = "一致"
        stage_reason.append("多个主线维持高热且风险低，市场一致性较强。")
    elif cycle_strength >= 90 and risk_score >= 35:
        stage = "高潮"
        stage_reason.append("高热后风险升高，进入高潮风险区。")
    elif cycle_strength >= 55 or leader_count > 0:
        stage = "修复"
        stage_reason.append("市场强度或龙头数量出现修复迹象。")
    else:
        stage = "分歧"
        stage_reason.append("市场强度不足且主线确认度有限，按分歧处理。")

    if not allow_open:
        stage_reason.append("风险闸门不允许开仓，操作层必须优先防守。")
    if health_score and health_score < 60:
        stage_reason.append(f"策略健康分为 {health_score:g}，验证样本或表现仍偏弱。")
    if leader_count:
        stage_reason.append(f"当前识别到龙头数量 {leader_count}。")
    if high_score_count:
        stage_reason.append(f"趋势池高分股数量 {high_score_count}。")

    if not allow_open:
        risk_score = max(risk_score, 60)
        warning.append("交易许可为 NO，禁止把观察信号当成交易信号。")
    if health_score and health_score < 60:
        risk_score = max(risk_score, 60)
        warning.append("策略健康分偏低，继续以前向验证为主。")
    if stage == "高潮":
        risk_score = max(risk_score, 55)
        warning.append("高潮阶段容易出现一致后分歧，不追弱分支。")
    if stage == "退潮":
        warning.append("退潮阶段以控制回撤为第一优先级。")
    if not warning:
        warning.append("所有结论仅用于学习研究和模拟验证，不构成投资建议。")

    score = max(cycle_strength, master_mean, top_master, avg_momentum, avg_trend)
    if stage in {"退潮", "冰点"}:
        score = max(score, 20)
    score = round(min(100, max(0, score)), 2)
    risk_score = round(min(100, max(0, risk_score)), 2)
    trade_mode, position = _trade_mode(stage, risk_score, allow_open)

    if stage == "冰点":
        next_stage_guess = "可能修复"
    elif stage == "修复":
        next_stage_guess = "进入分歧"
    elif stage == "分歧":
        next_stage_guess = "可能修复"
    elif stage == "一致":
        next_stage_guess = "高潮后风险"
    elif stage == "高潮":
        next_stage_guess = "高潮后风险"
    else:
        next_stage_guess = "继续退潮" if not allow_open else "可能修复"

    return {
        "stage": stage,
        "score": score,
        "stage_reason": stage_reason[:5],
        "risk_level": _risk_label(risk_score),
        "risk_score": risk_score,
        "trade_mode": trade_mode,
        "position_suggestion": position,
        "next_stage_guess": next_stage_guess,
        "warning": warning[:4],
        "raw": {
            "allow_open_position": allow_open,
            "cycle": cycle_name,
            "cycle_strength": cycle_strength,
            "master_score_mean": master_mean,
            "top_master_score": top_master,
            "leader_count": leader_count,
            "high_score_count": high_score_count,
            "strategy_health_score": health_score,
            "risk_gate_reason": risk_gate_reason,
            "market_divergence_std": divergence,
            "top_score_concentration": concentration,
        },
    }

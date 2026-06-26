from __future__ import annotations

from app.core.config import settings
from app.services.report_service import (
    build_dashboard,
    read_leaders,
    read_strategy_judge,
    read_validation_report,
)


def _to_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _emotion_from_leaders(leaders: list[dict]) -> str:
    if not leaders:
        return "偏弱"
    top_score = _to_float(leaders[0].get("master_score"))
    avg_risk = sum(_to_float(item.get("risk_level")) for item in leaders[:3]) / max(1, min(3, len(leaders)))
    if top_score >= 85 and avg_risk < 30:
        return "偏强"
    if top_score >= 75:
        return "中性"
    return "偏弱"


def _risk_label(risk_level: str) -> str:
    value = _to_float(risk_level)
    if value >= 70:
        return "高"
    if value >= 30:
        return "中等"
    return "低"


def _position_from_advice(position_advice: str) -> str:
    text = str(position_advice or "")
    if "max_position=" in text:
        return text.split("max_position=", 1)[-1].strip()
    if "空仓" in text:
        return "0%"
    return "等待系统确认"


def build_decision_center(user: dict) -> dict:
    dashboard = build_dashboard(user).model_dump()
    leaders_payload = read_leaders(user)
    leaders = leaders_payload.get("items", []) if leaders_payload.get("allowed", True) else []
    judge_payload = read_strategy_judge(user)
    judge = judge_payload.get("health", {}) if judge_payload.get("allowed", True) else {}
    validation = read_validation_report(user).model_dump()

    market_status = dashboard.get("market_status", "暂无")
    allow_trade = dashboard.get("allow_trade", "NO")
    risk = _risk_label(dashboard.get("risk_level", ""))
    position = _position_from_advice(dashboard.get("position_advice", ""))
    emotion = _emotion_from_leaders(leaders)
    score = _to_float(judge.get("strategy_health_score"))

    if allow_trade == "YES":
        summary = "今天允许交易，但仍需按冻结订单和仓位上限执行。"
    elif "空仓" in market_status or "防守" in market_status:
        summary = "今天系统处于防守状态，不建议主动开仓。"
    else:
        summary = "今天信号不完整，建议等待收盘确认。"

    reasons = [
        f"市场状态为：{market_status}。",
        f"系统允许交易标记为：{allow_trade}。",
        f"当前策略健康分为：{score:g}。",
    ]
    if leaders:
        top = leaders[0]
        reasons.append(f"当前最高分核心标的为 {top.get('name', '')}，master_score 为 {top.get('master_score', '')}。")
    while len(reasons) < 3:
        reasons.append("当前样本仍在积累，需继续观察前向验证结果。")

    warnings = []
    if allow_trade != "YES":
        warnings.append("系统未给出交易许可，禁止主观开仓。")
    if risk in {"中等", "高"}:
        warnings.append(f"当前风险等级为{risk}，仓位必须受控。")
    if score < 60:
        warnings.append("策略健康分不足60，暂不适合扩大模拟盘或进入实盘。")
    if validation.get("allowed") is False:
        warnings.append("当前用户无完整验证报告权限。")
    while len(warnings) < 2:
        warnings.append("所有结论仅供学习研究和模拟验证，不构成投资建议。")

    return {
        "summary": summary,
        "market_cycle": market_status,
        "emotion": emotion,
        "risk": risk,
        "position": position,
        "reason": reasons[:3],
        "warning": warnings[:2],
        "disclaimer": settings.disclaimer,
    }

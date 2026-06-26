from __future__ import annotations

from app.core.config import settings
from app.services.market_brain import build_market_brain


def build_decision_center(user: dict) -> dict:
    """AI 决策中心适配层：复用 Market Brain，保持原 API 字段不变。"""
    brain = build_market_brain(user)
    emotion = brain.get("emotion", {})
    theme = brain.get("theme", {})
    risk = brain.get("risk", {})
    position = brain.get("position", {})
    decision = brain.get("decision", {})

    reasons = [
        f"市场情绪阶段：{emotion.get('stage', '暂无数据')}，强度分：{emotion.get('score', 0)}。",
        f"当前主线：{theme.get('main_theme', '暂无主线')}。",
        f"系统动作：{decision.get('action', '观察')}，建议仓位：{position.get('suggested_position', '0%')}。",
    ]
    warnings = risk.get("warnings", [])[:2]
    while len(warnings) < 2:
        warnings.append("所有结论仅供学习研究和模拟验证，不构成投资建议。")

    return {
        "summary": decision.get("summary", "暂无结论，请先运行今日策略。"),
        "market_cycle": emotion.get("stage", "暂无数据"),
        "emotion": emotion.get("stage", "暂无数据"),
        "risk": risk.get("risk_label", "暂无数据"),
        "position": position.get("suggested_position", "0%"),
        "reason": reasons,
        "warning": warnings,
        "disclaimer": settings.disclaimer,
    }

from __future__ import annotations

from app.core.config import settings
from app.services.market_brain import build_market_brain


def build_mainline_analysis(user: dict) -> dict:
    """主线分析适配层：复用 Market Brain，保持 /api/mainline 原有字段不变。"""
    brain = build_market_brain(user)
    theme_rank = brain.get("theme", {}).get("theme_rank", [])
    tiers = brain.get("leader", {}).get("tier_summary", {})
    decision = brain.get("decision", {})
    position = brain.get("position", {})
    risk = brain.get("risk", {})

    mainlines = []
    for item in theme_rank:
        reason_text = item.get("reason", "")
        mainlines.append(
            {
                "theme": item.get("name", ""),
                "heat_score": item.get("score", 0),
                "leader": _first_name(tiers.get("T1", [])),
                "core_trend": _first_name(tiers.get("trend_core", [])),
                "reason": [reason_text] if reason_text else [],
            }
        )

    action = decision.get("action", "观察")
    suggested_position = position.get("suggested_position", "0%")
    if action == "防守":
        buy_condition = "仅观察，不主动开仓；等待市场周期脱离退潮并重新出现核心主线。"
        risk_condition = "若冻结订单继续显示 SKIP 或市场周期维持退潮，保持防守。"
    else:
        buy_condition = "只观察冻结订单中的高分核心标的，必须等待次日真实走势确认。"
        risk_condition = "若主线热度下降、龙头减少、风险等级升高，则降低仓位或放弃交易。"

    return {
        "market_emotion": brain.get("emotion", {}).get("stage", "暂无数据"),
        "mainlines": mainlines,
        "leader_tiers": {
            "T1": tiers.get("T1", []),
            "T2": tiers.get("T2", []),
            "trend_core": tiers.get("trend_core", []),
        },
        "leader_lifecycle": brain.get("leader", {}).get("lifecycle", []),
        "leader_lifecycle_summary": brain.get("leader", {}).get("lifecycle_summary", ""),
        "tomorrow_plan": {
            "action": action,
            "position": suggested_position,
            "watchlist": decision.get("watchlist", []),
            "buy_condition": buy_condition,
            "risk_condition": risk_condition,
        },
        "data_status": brain.get("data_status", {}),
        "risk": risk,
        "disclaimer": settings.disclaimer,
    }


def _first_name(items: list[dict]) -> str:
    if not items:
        return ""
    return items[0].get("name", "")

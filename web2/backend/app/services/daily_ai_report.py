from __future__ import annotations

from datetime import datetime

from app.core.config import settings
from app.services.market_brain import build_market_brain
from app.services.report_service import read_frozen_orders, read_strategy_judge


def _today_text() -> str:
    return datetime.now().strftime("%Y%m%d")


def _value(value, default: str = "暂无数据") -> str:
    if value is None or value == "":
        return default
    return str(value)


def _top_names(items: list[dict], limit: int = 5) -> str:
    names = []
    for item in items[:limit]:
        name = item.get("name") or item.get("stock_code") or item.get("code")
        score = item.get("score") or item.get("master_score")
        if score not in (None, ""):
            names.append(f"{name}({score})")
        elif name:
            names.append(str(name))
    return "、".join(names) if names else "暂无数据"


def _order_summary(payload: dict) -> str:
    orders = payload.get("orders", [])
    if not orders:
        return "暂无冻结订单。"
    action_count: dict[str, int] = {}
    for order in orders:
        action = order.get("action", "UNKNOWN")
        action_count[action] = action_count.get(action, 0) + 1
    return "；".join(f"{key}: {value}" for key, value in sorted(action_count.items()))


def build_daily_ai_report(user: dict) -> dict:
    brain = build_market_brain(user)
    judge = read_strategy_judge(user)
    frozen = read_frozen_orders(user)

    date_text = _today_text()
    title = f"AI复盘日报 {date_text}"
    emotion = brain.get("emotion", {})
    theme = brain.get("theme", {})
    leader = brain.get("leader", {})
    risk = brain.get("risk", {})
    position = brain.get("position", {})
    decision = brain.get("decision", {})

    summary = _value(decision.get("summary"), "系统暂无明确结论，请先运行今日策略。")
    market_view = (
        f"当前市场情绪为 {emotion.get('stage', '暂无数据')}，"
        f"情绪强度 {emotion.get('score', 0)}。{emotion.get('description', '')}"
    )

    rank = theme.get("theme_rank", [])
    first_theme = rank[0] if rank else {}
    mainline_view = (
        f"当前主线优先观察：{theme.get('main_theme', '暂无主线')}。"
        f"热度分为 {_value(first_theme.get('score'))}，"
        f"依据：{_value(first_theme.get('reason'))}。"
    )

    tiers = leader.get("tier_summary", {})
    leader_view = (
        f"T1核心龙头：{_top_names(tiers.get('T1', []))}。\n"
        f"T2补涨龙头：{_top_names(tiers.get('T2', []))}。\n"
        f"趋势核心：{_top_names(tiers.get('trend_core', []))}。"
    )

    risk_view = "；".join(risk.get("warnings", [])) if risk.get("warnings") else "暂无额外风险提示。"
    tomorrow_plan = (
        f"明日动作：{decision.get('action', '观察')}；"
        f"建议仓位：{position.get('suggested_position', '0%')}；"
        f"仓位原因：{position.get('reason', '暂无数据')}；"
        f"观察名单：{_top_names(decision.get('watchlist', []), 8)}。"
    )

    health = judge.get("health", {}) if judge.get("allowed", True) else {}
    health_score = _value(judge.get("health_score") or health.get("strategy_health_score"))
    order_view = _order_summary(frozen if frozen.get("allowed", True) else {})

    full_report = "\n\n".join(
        [
            f"# {title}",
            "## 今日总结\n" + summary,
            "## 市场判断\n" + market_view,
            "## 主线判断\n" + mainline_view,
            "## 龙头梯队\n" + leader_view,
            "## 风险提示\n" + risk_view,
            "## 明日计划\n" + tomorrow_plan,
            "## 冻结订单概览\n" + order_view,
            f"## 策略状态\n策略健康分：{health_score}",
            "## 免责声明\n" + settings.disclaimer,
        ]
    )

    return {
        "title": title,
        "summary": summary,
        "market_view": market_view,
        "mainline_view": mainline_view,
        "leader_view": leader_view,
        "risk_view": risk_view,
        "tomorrow_plan": tomorrow_plan,
        "full_report": full_report,
        "disclaimer": settings.disclaimer,
    }

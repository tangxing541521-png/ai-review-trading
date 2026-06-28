from __future__ import annotations

from app.services.ai_decision_engine import build_ai_decision
from app.services.auction_ai import build_auction_ai
from app.services.market_data_hub import build_market_data_hub
from app.services.realtime_ai import build_realtime_ai


def _workflow(global_action: str) -> list[dict]:
    waiting_status = "RUNNING" if global_action in {"WAIT", "WATCH"} else "DONE"
    order_status = "WAIT" if global_action != "BUY" else "READY"
    return [
        {"step": "读取行情", "status": "DONE"},
        {"step": "读取AI决策", "status": "DONE"},
        {"step": "检查交易闸门", "status": "DONE"},
        {"step": "等待买点", "status": waiting_status},
        {"step": "生成订单", "status": order_status},
        {"step": "执行", "status": "WAIT"},
        {"step": "Paper Trading", "status": "WAIT"},
        {"step": "Review", "status": "WAIT"},
    ]


def _logs(market_hub: dict, auction: dict, realtime: dict, decision: dict) -> list[str]:
    heartbeat = realtime.get("market_time") or market_hub.get("market_time") or "09:31:05"
    global_action = decision.get("global_decision", {}).get("action", "WAIT")
    buy_count = decision.get("stats", {}).get("buy", 0)
    cancel_count = decision.get("stats", {}).get("cancel", 0)
    return [
        f"{market_hub.get('market_time', '09:15')} 更新MarketHub",
        f"{auction.get('auction_time', '09:25')} 更新Auction",
        "09:30 AI开始等待",
        f"{heartbeat} 当前全局动作 {global_action}",
        f"{heartbeat} BUY信号 {buy_count} 个，CANCEL信号 {cancel_count} 个",
        "继续等待" if global_action == "WAIT" else "继续观察",
    ]


def build_trader_agent(user: dict | None = None) -> dict:
    market_hub = build_market_data_hub(user)
    auction = build_auction_ai(user)
    realtime = build_realtime_ai(user)
    ai_decision = build_ai_decision(user)
    market_state = ai_decision.get("market_state", {})
    global_decision = ai_decision.get("global_decision", {})
    stats = ai_decision.get("stats", {})
    action = global_decision.get("action", "WAIT")
    allow_trade = market_state.get("allow_trade") == "YES"
    heartbeat = realtime.get("market_time") or market_hub.get("market_time") or "09:31:05"

    mode = "OBSERVE"
    if action == "BUY" and allow_trade:
        mode = "READY"
    elif action in {"CANCEL", "AVOID"}:
        mode = "DEFENSE"

    return {
        "agent": {
            "name": "AI Trader",
            "version": "1.0",
            "status": "RUNNING",
            "mode": mode,
            "market_stage": market_state.get("stage", ""),
            "allow_trade": allow_trade,
            "heartbeat": heartbeat,
        },
        "current_task": "等待机会" if action == "WAIT" else "观察信号",
        "decision": action,
        "next_action": "继续观察" if action != "BUY" else "等待人工确认",
        "order_queue": [],
        "statistics": {
            "signals": len(ai_decision.get("decisions", [])),
            "watch": stats.get("watch", 0),
            "cancel": stats.get("cancel", 0),
            "buy": stats.get("buy", 0),
            "executed": 0,
        },
        "workflow": _workflow(action),
        "log": _logs(market_hub, auction, realtime, ai_decision),
        "debug": {
            "used_sources": ["MarketHub", "AuctionAI", "RealtimeAI", "AIDecision"],
            "market_status": market_hub.get("market_status", ""),
            "ai_decision_summary": global_decision.get("summary", ""),
        },
    }

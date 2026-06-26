from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

from app.core.config import settings
from app.services.emotion_cycle_engine import build_emotion_cycle
from app.services.leader_lifecycle_engine import build_leader_lifecycle


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


def _to_float(value, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except Exception:
        return default


def _code(row: dict) -> str:
    value = str(row.get("code") or row.get("stock_code") or "")
    return value.zfill(6) if value else ""


def _score(row: dict) -> float:
    for key in ("master_score", "combined_score", "trend_score", "momentum_score", "score"):
        value = _to_float(row.get(key), -1)
        if value >= 0:
            return value
    return 0.0


def _compact_stock(row: dict) -> dict:
    return {
        "code": _code(row),
        "name": row.get("name", ""),
        "score": round(_score(row), 2),
        "momentum_score": row.get("momentum_score", ""),
        "trend_score": row.get("trend_score", ""),
        "master_score": row.get("master_score", ""),
        "leader_tier": row.get("leader_tier", ""),
        "risk_level": row.get("risk_level", ""),
    }


def _infer_theme(row: dict) -> str:
    name = str(row.get("name", ""))
    code = _code(row)
    reason = str(row.get("reason", ""))
    text = f"{name}{reason}"
    theme_rules = [
        ("AI硬件", ["存储", "芯片", "半导体", "光电", "算力", "服务器", "电子", "科技"]),
        ("通信算力", ["通信", "光缆", "光纤", "中天", "数据", "网络", "信息"]),
        ("机器人高端制造", ["机器人", "智能", "装备", "机械", "自动化", "电机"]),
        ("新能源产业链", ["电池", "锂", "光伏", "储能", "能源", "电力", "风电"]),
        ("消费医药", ["食品", "酒", "药", "医疗", "生物", "消费"]),
        ("金融地产", ["银行", "证券", "保险", "地产", "信托"]),
    ]
    for theme, words in theme_rules:
        if any(word in text for word in words):
            return theme
    if code.startswith(("688", "300", "301")):
        return "科技成长"
    if code.startswith(("600", "601", "603")):
        return "主板趋势"
    return "高分趋势"


def _build_theme_rank(rows: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[_infer_theme(row)].append(row)

    result = []
    for theme, stocks in grouped.items():
        ranked = sorted(stocks, key=_score, reverse=True)
        if not ranked:
            continue
        avg_score = sum(_score(item) for item in ranked[:10]) / max(1, min(10, len(ranked)))
        heat_score = min(100, avg_score + min(10, len(ranked)) * 1.5)
        leader = ranked[0].get("name", "")
        reason = f"主题内高分股票数 {len(ranked)}，最高分标的 {leader}，核心分均值 {avg_score:.1f}"
        result.append({"name": theme, "score": round(heat_score, 2), "reason": reason})
    return sorted(result, key=lambda item: item["score"], reverse=True)[:8]


def build_market_brain(user: dict | None = None) -> dict:
    leader_rows = _read_csv_rows(settings.project_root / "leader_tier.csv")
    detection_rows = _read_csv_rows(settings.project_root / "leader_detection.csv")
    trend_rows = _latest_csv_rows("data/processed/trend_core_pool_*.csv")
    frozen = _latest_json("frozen_decisions/orders_*.json")

    rows = leader_rows or detection_rows or trend_rows
    sorted_rows = sorted(rows, key=_score, reverse=True)
    emotion_cycle = build_emotion_cycle(user)
    lifecycle = build_leader_lifecycle(user)
    lifecycle_map = {item.get("code"): item for item in lifecycle.get("leaders", [])}
    risk_score = _to_float(emotion_cycle.get("risk_score"))

    theme_rank = _build_theme_rank(rows or trend_rows)
    main_theme = theme_rank[0]["name"] if theme_rank else "暂无主线"

    t1 = [row for row in leader_rows if "T0" in str(row.get("leader_tier", "")) or "T1" in str(row.get("leader_tier", ""))]
    t2 = [row for row in leader_rows if "T2" in str(row.get("leader_tier", ""))]
    if not t2:
        t2 = [row for row in leader_rows if row not in t1][:10]
    trend_core = sorted(trend_rows, key=lambda row: _to_float(row.get("trend_score"), _score(row)), reverse=True)[:10]
    watchlist_source = t1 or trend_core or sorted_rows

    stage = emotion_cycle.get("stage", "分歧")
    action = _action_from_trade_mode(emotion_cycle.get("trade_mode", "观察"))
    suggested_position = emotion_cycle.get("position_suggestion", "0%")
    summary = f"{stage}阶段，主线为{main_theme}，建议{action}，仓位{suggested_position}。"
    description = "；".join(emotion_cycle.get("stage_reason", [])) or "暂无情绪周期说明。"

    return {
        "emotion": {
            "stage": stage,
            "score": emotion_cycle.get("score", 0),
            "description": description,
            "stage_reason": emotion_cycle.get("stage_reason", []),
            "risk_level": emotion_cycle.get("risk_level", "中"),
            "trade_mode": emotion_cycle.get("trade_mode", "观察"),
            "position_suggestion": suggested_position,
            "next_stage_guess": emotion_cycle.get("next_stage_guess", "可能修复"),
            "warning": emotion_cycle.get("warning", []),
            "raw": emotion_cycle.get("raw", {}),
        },
        "theme": {
            "main_theme": main_theme,
            "theme_rank": theme_rank,
        },
        "leader": {
            "top_leaders": [_with_lifecycle(_compact_stock(row), lifecycle_map) for row in sorted_rows[:10]],
            "tier_summary": {
                "T1": [_with_lifecycle(_compact_stock(row), lifecycle_map) for row in t1[:10]],
                "T2": [_with_lifecycle(_compact_stock(row), lifecycle_map) for row in t2[:10]],
                "trend_core": [_with_lifecycle(_compact_stock(row), lifecycle_map) for row in trend_core[:10]],
            },
            "lifecycle": lifecycle.get("leaders", []),
            "lifecycle_summary": lifecycle.get("summary", ""),
        },
        "risk": {
            "risk_level": risk_score,
            "risk_label": emotion_cycle.get("risk_level", "中"),
            "warnings": emotion_cycle.get("warning", []),
        },
        "position": {
            "suggested_position": suggested_position,
            "reason": _position_reason(emotion_cycle),
        },
        "decision": {
            "action": action,
            "summary": summary,
            "watchlist": [_with_lifecycle(_compact_stock(row), lifecycle_map) for row in watchlist_source[:10]],
        },
        "data_status": {
            "leader_rows": len(leader_rows),
            "trend_rows": len(trend_rows),
            "frozen_order_count": len(frozen.get("orders", [])) if isinstance(frozen, dict) else 0,
            "strategy_health_score": emotion_cycle.get("raw", {}).get("strategy_health_score", 0),
        },
        "disclaimer": settings.disclaimer,
    }


def _action_from_trade_mode(trade_mode: str) -> str:
    if trade_mode == "空仓":
        return "防守"
    if trade_mode == "轻仓":
        return "轻仓"
    if trade_mode == "进攻":
        return "进攻"
    return "观察"


def _position_reason(emotion_cycle: dict) -> str:
    mode = emotion_cycle.get("trade_mode", "观察")
    stage = emotion_cycle.get("stage", "分歧")
    next_stage = emotion_cycle.get("next_stage_guess", "")
    if mode == "空仓":
        return f"情绪周期为{stage}，下阶段推演为{next_stage}，当前不支持开仓。"
    if mode == "轻仓":
        return f"情绪周期为{stage}，只允许轻仓跟踪核心方向。"
    if mode == "进攻":
        return f"情绪周期为{stage}，主线确认度较高，可围绕核心主线进攻。"
    return f"情绪周期为{stage}，等待更明确的主线和风险确认。"


def _with_lifecycle(stock: dict, lifecycle_map: dict[str, dict]) -> dict:
    item = lifecycle_map.get(stock.get("code"), {})
    if not item:
        return stock
    return {
        **stock,
        "life_stage": item.get("life_stage", ""),
        "stage_score": item.get("stage_score", ""),
        "days_in_stage": item.get("days_in_stage", 0),
        "lifecycle_risk": item.get("risk", ""),
        "lifecycle_action": item.get("action", ""),
        "lifecycle_reason": item.get("reason", []),
        "lifecycle_warning": item.get("warning", []),
    }

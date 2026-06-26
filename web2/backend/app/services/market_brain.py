from __future__ import annotations

import csv
import json
from collections import defaultdict
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


def _to_float(value, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
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


def _risk_label(value: float) -> str:
    if value >= 70:
        return "高"
    if value >= 30:
        return "中"
    return "低"


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


def _emotion_stage(cycle_row: dict, rows: list[dict]) -> tuple[str, float, str]:
    cycle = str(cycle_row.get("market_cycle", ""))
    strength = _to_float(cycle_row.get("cycle_strength"))
    top_scores = [_score(row) for row in rows[:5]]
    avg_top = sum(top_scores) / len(top_scores) if top_scores else 0.0
    raw_score = max(strength, avg_top)

    if "退潮" in cycle:
        return "退潮", round(raw_score or 20, 2), "市场周期处于退潮，交易权限应以防守为主。"
    if "冰点" in cycle:
        return "冰点", round(raw_score or 15, 2), "市场情绪处于冰点，优先观察修复信号。"
    if raw_score >= 90:
        return "高潮", round(raw_score, 2), "高分股票集中，情绪接近高潮，需防止一致后的分歧。"
    if raw_score >= 78:
        return "一致", round(raw_score, 2), "核心标的强度较高，市场一致性较强。"
    if raw_score >= 55:
        return "修复", round(raw_score, 2), "市场出现修复迹象，但仍需等待主线确认。"
    return "分歧", round(raw_score, 2), "强弱分化明显，暂不适合扩大交易。"


def _position(stage: str, risk_level: float) -> tuple[str, str, str]:
    if stage in {"退潮", "冰点"} or risk_level >= 70:
        return "0%", "防守", "市场风险或周期状态不支持开仓。"
    if stage == "分歧":
        return "20%", "观察", "市场分歧较大，仅保留观察权限。"
    if stage == "修复":
        return "30%", "轻仓", "市场修复中，只允许小仓位跟踪核心。"
    if stage == "一致":
        return "60%", "进攻", "市场一致性提升，可围绕主线核心进攻。"
    return "60%", "进攻", "情绪高位时只关注核心，不追弱分支。"


def build_market_brain(user: dict | None = None) -> dict:
    leader_rows = _read_csv_rows(settings.project_root / "leader_tier.csv")
    detection_rows = _read_csv_rows(settings.project_root / "leader_detection.csv")
    trend_rows = _latest_csv_rows("data/processed/trend_core_pool_*.csv")
    cycle_rows = _read_csv_rows(settings.project_root / "cycle_strength_report.csv")
    health_rows = _read_csv_rows(settings.project_root / "strategy_health_score.csv")
    frozen = _latest_json("frozen_decisions/orders_*.json")

    rows = leader_rows or detection_rows or trend_rows
    sorted_rows = sorted(rows, key=_score, reverse=True)
    cycle_row = cycle_rows[-1] if cycle_rows else {}
    health_row = health_rows[-1] if health_rows else {}

    stage, emotion_score, description = _emotion_stage(cycle_row, sorted_rows)
    risk_level = _to_float(cycle_row.get("risk_level"))
    health_score = _to_float(health_row.get("strategy_health_score"))
    if health_score and health_score < 40:
        risk_level = max(risk_level, 60)

    suggested_position, action, position_reason = _position(stage, risk_level)
    theme_rank = _build_theme_rank(rows or trend_rows)
    main_theme = theme_rank[0]["name"] if theme_rank else "暂无主线"

    t1 = [row for row in leader_rows if "T0" in str(row.get("leader_tier", "")) or "T1" in str(row.get("leader_tier", ""))]
    t2 = [row for row in leader_rows if "T2" in str(row.get("leader_tier", ""))]
    if not t2:
        t2 = [row for row in leader_rows if row not in t1][:10]
    trend_core = sorted(trend_rows, key=lambda row: _to_float(row.get("trend_score"), _score(row)), reverse=True)[:10]

    warnings = []
    if stage in {"退潮", "冰点"}:
        warnings.append("周期偏弱，禁止把观察信号当成交易信号。")
    if risk_level >= 70:
        warnings.append("风险等级高，应保持防守。")
    if health_score and health_score < 60:
        warnings.append("策略健康分不足，继续以前向验证为主。")
    if not warnings:
        warnings.append("所有信号仅用于学习研究和模拟验证，不构成投资建议。")

    watchlist_source = t1 or trend_core or sorted_rows
    summary = f"{stage}阶段，主线为{main_theme}，建议{action}，仓位{suggested_position}。"

    return {
        "emotion": {
            "stage": stage,
            "score": emotion_score,
            "description": description,
        },
        "theme": {
            "main_theme": main_theme,
            "theme_rank": theme_rank,
        },
        "leader": {
            "top_leaders": [_compact_stock(row) for row in sorted_rows[:10]],
            "tier_summary": {
                "T1": [_compact_stock(row) for row in t1[:10]],
                "T2": [_compact_stock(row) for row in t2[:10]],
                "trend_core": [_compact_stock(row) for row in trend_core[:10]],
            },
        },
        "risk": {
            "risk_level": round(risk_level, 2),
            "risk_label": _risk_label(risk_level),
            "warnings": warnings,
        },
        "position": {
            "suggested_position": suggested_position,
            "reason": position_reason,
        },
        "decision": {
            "action": action,
            "summary": summary,
            "watchlist": [_compact_stock(row) for row in watchlist_source[:10]],
        },
        "data_status": {
            "leader_rows": len(leader_rows),
            "trend_rows": len(trend_rows),
            "frozen_order_count": len(frozen.get("orders", [])) if isinstance(frozen, dict) else 0,
            "strategy_health_score": health_score,
        },
        "disclaimer": settings.disclaimer,
    }

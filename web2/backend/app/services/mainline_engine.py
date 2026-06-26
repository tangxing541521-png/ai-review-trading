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


def _market_emotion(cycle_row: dict, leaders: list[dict]) -> str:
    cycle = str(cycle_row.get("market_cycle", ""))
    strength = _to_float(cycle_row.get("cycle_strength"))
    top_scores = [_score(row) for row in leaders[:5]]
    avg_top = sum(top_scores) / len(top_scores) if top_scores else 0
    if "退潮" in cycle or "冰点" in cycle:
        return "退潮"
    if strength >= 90 and avg_top >= 85:
        return "高潮"
    if strength >= 75 and avg_top >= 80:
        return "一致"
    if strength >= 55:
        return "修复"
    return "分歧"


def _tomorrow_action(emotion: str, cycle_row: dict) -> tuple[str, str]:
    cycle = str(cycle_row.get("market_cycle", ""))
    risk = _to_float(cycle_row.get("risk_level"))
    if emotion == "退潮" or "退潮" in cycle or risk >= 70:
        return "防守", "0%"
    if emotion == "分歧":
        return "观察", "20%"
    if emotion == "修复":
        return "轻仓", "30%"
    if emotion == "一致":
        return "进攻", "60%"
    return "轻仓", "30%"


def _compact_stock(row: dict) -> dict:
    return {
        "code": _code(row),
        "name": row.get("name", ""),
        "score": round(_score(row), 2),
        "momentum_score": row.get("momentum_score", ""),
        "trend_score": row.get("trend_score", ""),
        "leader_tier": row.get("leader_tier", ""),
    }


def _build_mainlines(rows: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[_infer_theme(row)].append(row)

    mainlines = []
    for theme, stocks in grouped.items():
        ranked = sorted(stocks, key=_score, reverse=True)
        if not ranked:
            continue
        leader = max(ranked, key=lambda item: _to_float(item.get("momentum_score"), _score(item)))
        core_trend = max(ranked, key=lambda item: _to_float(item.get("trend_score"), _score(item)))
        avg_score = sum(_score(item) for item in ranked[:10]) / max(1, min(10, len(ranked)))
        heat_score = min(100, avg_score + min(10, len(ranked)) * 1.5)
        reasons = [
            f"主题内高分股票数：{len(ranked)}",
            f"核心分均值：{avg_score:.1f}",
            f"最高分标的：{ranked[0].get('name', '')}",
        ]
        mainlines.append(
            {
                "theme": theme,
                "heat_score": round(heat_score, 2),
                "leader": leader.get("name", ""),
                "core_trend": core_trend.get("name", ""),
                "reason": reasons,
            }
        )
    return sorted(mainlines, key=lambda item: item["heat_score"], reverse=True)[:8]


def build_mainline_analysis(user: dict) -> dict:
    leader_rows = _read_csv_rows(settings.project_root / "leader_tier.csv")
    detection_rows = _read_csv_rows(settings.project_root / "leader_detection.csv")
    trend_rows = _latest_csv_rows("data/processed/trend_core_pool_*.csv")
    cycle_rows = _read_csv_rows(settings.project_root / "cycle_strength_report.csv")
    health_rows = _read_csv_rows(settings.project_root / "strategy_health_score.csv")
    frozen_orders = _latest_json("frozen_decisions/orders_*.json")

    combined_rows = leader_rows or detection_rows or trend_rows
    cycle_row = cycle_rows[-1] if cycle_rows else {}
    health_row = health_rows[-1] if health_rows else {}
    market_emotion = _market_emotion(cycle_row, combined_rows)
    mainlines = _build_mainlines(combined_rows or trend_rows)

    t1 = [row for row in leader_rows if "T0" in str(row.get("leader_tier", "")) or "T1" in str(row.get("leader_tier", ""))]
    t2 = [row for row in leader_rows if "T2" in str(row.get("leader_tier", ""))]
    if not t2:
        t2 = [row for row in leader_rows if row not in t1][:10]
    trend_core = sorted(trend_rows, key=lambda row: _to_float(row.get("trend_score"), _score(row)), reverse=True)[:10]

    action, position = _tomorrow_action(market_emotion, cycle_row)
    watch_source = t1 or trend_core or combined_rows
    watchlist = [_compact_stock(row) for row in watch_source[:10]]
    health_score = _to_float(health_row.get("strategy_health_score"))

    if market_emotion == "退潮":
        buy_condition = "仅观察，不主动开仓；等待市场周期脱离退潮并重新出现核心主线。"
        risk_condition = "若冻结订单继续显示 SKIP 或市场周期维持退潮，保持防守。"
    else:
        buy_condition = "只观察冻结订单中的高分核心标的，必须等待次日真实走势确认。"
        risk_condition = "若主线热度下降、龙头减少、风险等级升高，则降低仓位或放弃交易。"

    return {
        "market_emotion": market_emotion,
        "mainlines": mainlines,
        "leader_tiers": {
            "T1": [_compact_stock(row) for row in t1[:10]],
            "T2": [_compact_stock(row) for row in t2[:10]],
            "trend_core": [_compact_stock(row) for row in trend_core[:10]],
        },
        "tomorrow_plan": {
            "action": action,
            "position": position,
            "watchlist": watchlist,
            "buy_condition": buy_condition,
            "risk_condition": risk_condition,
        },
        "data_status": {
            "leader_rows": len(leader_rows),
            "trend_rows": len(trend_rows),
            "frozen_order_count": len(frozen_orders.get("orders", [])) if isinstance(frozen_orders, dict) else 0,
            "strategy_health_score": health_score,
        },
        "disclaimer": settings.disclaimer,
    }

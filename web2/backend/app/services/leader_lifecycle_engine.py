from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
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


def _all_pool_rows() -> list[dict]:
    rows: list[dict] = []
    for path in sorted(settings.project_root.glob("data/processed/trend_core_pool_*.csv")):
        rows.extend(_read_csv_rows(path))
    return rows


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


def _code(row: dict) -> str:
    value = str(row.get("code") or row.get("stock_code") or "")
    return value.zfill(6) if value else ""


def _score(row: dict) -> float:
    for key in ("master_score", "combined_score", "trend_score", "momentum_score", "score"):
        value = _to_float(row.get(key), -1)
        if value >= 0:
            return value
    return 0.0


def _tier(row: dict) -> str:
    text = str(row.get("leader_tier") or row.get("pool_type") or "")
    if "T1" in text or "T0" in text:
        return "T1"
    if "T2" in text:
        return "T2"
    return "trend_core"


def _risk_label(value: float) -> str:
    if value >= 70:
        return "高"
    if value >= 35:
        return "中"
    return "低"


def _order_defensive() -> bool:
    payload = _latest_json("frozen_decisions/orders_*.json")
    orders = payload.get("orders", []) if isinstance(payload, dict) else []
    return bool(orders) and all(str(order.get("action", "")).upper() in {"SKIP", "NO_TRADE"} for order in orders)


def _pool_appearance_count() -> Counter:
    counter: Counter = Counter()
    for row in _all_pool_rows():
        code = _code(row)
        if code:
            counter[code] += 1
    return counter


def _merge_core_rows() -> list[dict]:
    by_code: dict[str, dict] = {}
    for row in _latest_csv_rows("data/processed/trend_core_pool_*.csv"):
        code = _code(row)
        if code:
            by_code[code] = {**by_code.get(code, {}), **row, "tier": "trend_core"}
    for row in _read_csv_rows(settings.project_root / "leader_detection.csv"):
        code = _code(row)
        if code:
            by_code[code] = {**by_code.get(code, {}), **row}
    for row in _read_csv_rows(settings.project_root / "leader_tier.csv"):
        code = _code(row)
        if code:
            by_code[code] = {**by_code.get(code, {}), **row}
    return sorted(by_code.values(), key=_score, reverse=True)[:30]


def _classify(row: dict, pool_days: int, defensive: bool, market_tide: bool) -> tuple[str, float, str, str, list[str], list[str]]:
    score = _score(row)
    tier = _tier(row)
    momentum = _to_float(row.get("momentum_score"))
    trend = _to_float(row.get("trend_score"))
    risk_value = _to_float(row.get("risk_level"))
    continuation = _to_float(row.get("continuation_score"))
    acceleration = _to_float(row.get("acceleration_score"))
    is_leader = str(row.get("is_leader", "")).lower() == "true" or tier in {"T1", "T2"}

    reason: list[str] = []
    warning: list[str] = []

    if score >= 85 and tier == "T1" and trend >= 85 and momentum >= 85:
        if acceleration >= 60 or continuation >= 60:
            life_stage = "加速期"
            action = "持有"
            stage_score = min(100, score + 5)
            reason.append("高分T1龙头，趋势与动量双强。")
        else:
            life_stage = "确认期"
            action = "持有"
            stage_score = score
            reason.append("高分T1龙头，趋势确认但加速程度仍需观察。")
    elif score >= 80 and is_leader:
        life_stage = "确认期"
        action = "观察" if defensive else "持有"
        stage_score = score
        reason.append("高分核心股已具备龙头候选地位。")
    elif tier == "trend_core" and pool_days >= 3:
        life_stage = "二波期" if score >= 80 else "确认期"
        action = "持有" if not defensive else "观察"
        stage_score = min(100, score + min(10, pool_days))
        reason.append(f"趋势核心连续在池，累计出现 {pool_days} 次。")
    elif score >= 75:
        life_stage = "启动期"
        action = "观察"
        stage_score = score
        reason.append("分数进入核心区，但龙头地位仍需确认。")
    else:
        life_stage = "启动期"
        action = "观察"
        stage_score = max(40, score)
        reason.append("仍处早期观察阶段。")

    if (score >= 85 and risk_value >= 35 and market_tide) or (score >= 85 and defensive):
        life_stage = "分歧期"
        action = "减仓" if not defensive else "回避"
        stage_score = min(100, score + risk_value * 0.2)
        warning.append("高分核心遇到退潮或防守订单，容易从一致转向分歧。")
    if score >= 88 and risk_value >= 60:
        life_stage = "见顶期"
        action = "减仓"
        stage_score = min(100, score + 8)
        warning.append("高分同时伴随高风险，需警惕见顶。")
    if market_tide and score < 80:
        life_stage = "退潮期"
        action = "回避"
        stage_score = max(50, risk_value)
        warning.append("市场退潮且个股强度不足，回避弱核心。")

    if defensive:
        warning.append("冻结订单整体偏防守，生命周期判断只作观察，不作为开仓依据。")
    if risk_value >= 35:
        warning.append(f"个股风险分 {risk_value:g}，需控制仓位。")

    risk = _risk_label(max(risk_value, 60 if defensive and life_stage in {"分歧期", "退潮期"} else risk_value))
    if not reason:
        reason.append("依据分数、梯队、趋势池出现次数和市场周期综合判断。")
    if not warning:
        warning.append("仅用于学习研究和模拟验证，不构成投资建议。")

    return life_stage, round(min(100, max(0, stage_score)), 2), risk, action, reason[:3], warning[:3]


def build_leader_lifecycle(user: dict | None = None) -> dict:
    rows = _merge_core_rows()
    pool_counter = _pool_appearance_count()
    defensive = _order_defensive()
    master_row = _last_row(settings.project_root / "market_master_signal.csv")
    cycle_row = _last_row(settings.project_root / "cycle_strength_report.csv")
    market_tide = "退潮" in str(master_row.get("cycle") or master_row.get("market_regime_final") or cycle_row.get("market_cycle") or "")

    leaders = []
    stage_counter: defaultdict[str, int] = defaultdict(int)
    for row in rows:
        code = _code(row)
        if not code:
            continue
        days = int(pool_counter.get(code, 0))
        life_stage, stage_score, risk, action, reason, warning = _classify(row, days, defensive, market_tide)
        stage_counter[life_stage] += 1
        leaders.append(
            {
                "code": code,
                "name": row.get("name", ""),
                "score": round(_score(row), 2),
                "tier": _tier(row),
                "life_stage": life_stage,
                "stage_score": stage_score,
                "days_in_stage": days,
                "risk": risk,
                "action": action,
                "reason": reason,
                "warning": warning,
            }
        )

    if not leaders:
        summary = "暂无可分析龙头，请先运行今日策略。"
    elif defensive:
        summary = f"冻结订单偏防守，当前龙头生命周期以观察和回避为主，共识别 {len(leaders)} 只核心股。"
    else:
        top_stage = max(stage_counter.items(), key=lambda item: item[1])[0]
        summary = f"当前共识别 {len(leaders)} 只核心股，生命周期主要集中在{top_stage}。"

    return {
        "leaders": leaders,
        "summary": summary,
    }

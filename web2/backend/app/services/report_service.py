import csv
import json
from pathlib import Path

from app.core.config import settings
from app.schemas.dashboard import DashboardResponse
from app.schemas.report import ReportResponse
from app.services.auth_service import user_has_member_access


def _read_latest_csv_row(path: Path) -> dict:
    if not path.exists() or path.stat().st_size == 0:
        return {}
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            rows = list(csv.DictReader(file))
        return rows[-1] if rows else {}
    except Exception:
        return {}


def _read_text(path: Path) -> str:
    if not path.exists() or path.stat().st_size == 0:
        return "暂无报告，请先运行本地交易员流程。"
    return path.read_text(encoding="utf-8", errors="ignore")


def _read_csv_rows(path: Path) -> list[dict]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            return list(csv.DictReader(file))
    except Exception:
        return []


def _latest_json(path_pattern: str) -> tuple[dict, Path | None]:
    paths = sorted(settings.project_root.glob(path_pattern))
    if not paths:
        return {}, None
    path = paths[-1]
    try:
        return json.loads(path.read_text(encoding="utf-8")), path
    except Exception:
        return {}, path


def _latest_meta() -> dict:
    payload, _ = _latest_json("frozen_decisions/decision_meta_*.json")
    return payload


def _masked(title: str, user: dict) -> ReportResponse:
    return ReportResponse(
        title=title,
        allowed=False,
        content="请升级会员后查看完整报告、订单详情、虚拟账户和验证结果。",
        membership_level=user.get("membership_level", "free"),
        disclaimer=settings.disclaimer,
    )


def build_dashboard(user: dict) -> DashboardResponse:
    validation = _read_latest_csv_row(settings.project_root / "forward_validation.csv")
    risk = _read_latest_csv_row(settings.project_root / "risk_control_report.csv")
    account = _read_latest_csv_row(settings.project_root / "paper_account.csv")
    equity = _read_latest_csv_row(settings.project_root / "paper_equity_curve.csv")
    final_report = _read_text(settings.project_root / "final_report.md")
    one_sentence = "暂无结论，请先运行本地交易员流程。"
    for line in final_report.splitlines():
        if "今日市场一句话总结" in line or "一句话" in line:
            one_sentence = line.replace("#", "").replace("-", "").strip()
            break
    if one_sentence.startswith("暂无"):
        one_sentence = validation.get("market_regime_final", "暂无结论")
    return DashboardResponse(
        market_status=validation.get("market_regime_final", "暂无"),
        allow_trade=validation.get("allow_trade", "暂无"),
        risk_level=risk.get("risk_level", "暂无"),
        position_advice=validation.get("position_advice", "暂无"),
        total_assets=account.get("total_assets", "暂无"),
        daily_return=equity.get("daily_return", "暂无"),
        cumulative_return=equity.get("cumulative_return", "暂无"),
        one_sentence_summary=one_sentence,
        membership_level=user.get("membership_level", "free"),
        disclaimer=settings.disclaimer,
    )


def read_final_report(user: dict) -> ReportResponse:
    if not user_has_member_access(user):
        return _masked("最终日报", user)
    return ReportResponse(
        title="最终日报",
        allowed=True,
        content=_read_text(settings.project_root / "final_report.md"),
        membership_level=user.get("membership_level", "free"),
        disclaimer=settings.disclaimer,
    )


def read_paper_report(user: dict) -> ReportResponse:
    if not user_has_member_access(user):
        return _masked("Paper Trading 账户", user)
    return ReportResponse(
        title="Paper Trading 账户",
        allowed=True,
        content=_read_text(settings.project_root / "paper_report.md"),
        membership_level=user.get("membership_level", "free"),
        disclaimer=settings.disclaimer,
    )


def read_paper_data(user: dict) -> dict:
    if not user_has_member_access(user):
        return {
            "allowed": False,
            "account": {},
            "positions": [],
            "equity_curve": [],
            "message": "请升级会员后查看 Paper Trading 账户。",
            "membership_level": user.get("membership_level", "free"),
            "disclaimer": settings.disclaimer,
        }
    equity_curve = _read_csv_rows(settings.project_root / "paper_equity_curve.csv")
    drawdown_curve = [
        {
            "date": row.get("date", ""),
            "max_drawdown": row.get("max_drawdown", "0"),
        }
        for row in equity_curve
    ]
    return {
        "allowed": True,
        "account": _read_latest_csv_row(settings.project_root / "paper_account.csv"),
        "positions": _read_csv_rows(settings.project_root / "paper_positions.csv"),
        "equity_curve": equity_curve,
        "drawdown_curve": drawdown_curve,
        "membership_level": user.get("membership_level", "free"),
        "disclaimer": settings.disclaimer,
    }


def read_validation_report(user: dict) -> ReportResponse:
    if not user_has_member_access(user):
        return _masked("Forward Validation 验证结果", user)
    return ReportResponse(
        title="Forward Validation 验证结果",
        allowed=True,
        content=_read_text(settings.project_root / "validation_report.md"),
        membership_level=user.get("membership_level", "free"),
        disclaimer=settings.disclaimer,
    )


def read_leaders(user: dict) -> dict:
    if not user_has_member_access(user):
        return {
            "allowed": False,
            "items": [],
            "message": "请升级会员后查看龙头排行榜。",
            "membership_level": user.get("membership_level", "free"),
            "disclaimer": settings.disclaimer,
        }
    rows = _read_csv_rows(settings.project_root / "leader_tier.csv")
    items = []
    for row in rows[:50]:
        items.append(
            {
                "code": row.get("code", ""),
                "name": row.get("name", ""),
                "master_score": row.get("master_score", ""),
                "leader_tier": row.get("leader_tier", ""),
                "momentum_score": row.get("momentum_score", ""),
                "trend_score": row.get("trend_score", ""),
                "risk_level": row.get("risk_level", ""),
            }
        )
    return {
        "allowed": True,
        "items": items,
        "membership_level": user.get("membership_level", "free"),
        "disclaimer": settings.disclaimer,
    }


def read_frozen_orders(user: dict) -> dict:
    if not user_has_member_access(user):
        return {
            "allowed": False,
            "is_frozen": False,
            "freeze_time": "",
            "orders": [],
            "message": "请升级会员后查看冻结订单。",
            "membership_level": user.get("membership_level", "free"),
            "disclaimer": settings.disclaimer,
        }
    payload, path = _latest_json("frozen_decisions/orders_*.json")
    meta = _latest_meta()
    orders = payload.get("orders", []) if isinstance(payload, dict) else []
    clean_orders = [
        {
            "stock_code": str(order.get("stock_code", "")).zfill(6),
            "action": order.get("action", ""),
            "position_ratio": order.get("position_ratio", ""),
            "score": order.get("score", ""),
            "cycle": order.get("cycle", ""),
            "reason": order.get("reason", ""),
        }
        for order in orders[:100]
    ]
    return {
        "allowed": True,
        "date": payload.get("date", meta.get("date", "")),
        "is_frozen": bool(payload.get("is_frozen", meta.get("is_frozen", False))),
        "freeze_time": meta.get("freeze_time", payload.get("frozen_at", "")),
        "source_file": str(path) if path else "",
        "order_count": len(orders),
        "orders": clean_orders,
        "membership_level": user.get("membership_level", "free"),
        "disclaimer": settings.disclaimer,
    }


def read_strategy_judge(user: dict) -> dict:
    if not user_has_member_access(user):
        return {
            "allowed": False,
            "health": {},
            "metrics": [],
            "message": "请升级会员后查看策略评分。",
            "membership_level": user.get("membership_level", "free"),
            "disclaimer": settings.disclaimer,
        }
    health = _read_latest_csv_row(settings.project_root / "strategy_health_score.csv")
    metrics = _read_csv_rows(settings.project_root / "strategy_metrics.csv")
    metric_map = {row.get("metric", ""): row.get("value", "") for row in metrics}
    return {
        "allowed": True,
        "health": health,
        "metrics": metrics,
        "health_score": health.get("strategy_health_score", "0"),
        "win_rate": metric_map.get("胜率", "0"),
        "profit_loss_ratio": metric_map.get("盈亏比", "0"),
        "max_drawdown": metric_map.get("最大回撤", "0"),
        "report": _read_text(settings.project_root / "strategy_judge_report.md"),
        "membership_level": user.get("membership_level", "free"),
        "disclaimer": settings.disclaimer,
    }


def read_membership(user: dict) -> dict:
    return {
        "username": user.get("username", ""),
        "membership_level": user.get("membership_level", "free"),
        "expire_date": user.get("expire_date", ""),
        "is_active": user.get("is_active", False),
        "plans": [
            {
                "name": "免费版",
                "features": ["Dashboard 摘要", "市场状态", "风险等级", "免责声明"],
            },
            {
                "name": "会员版",
                "features": ["完整报告", "Paper Trading", "冻结订单", "策略评分", "验证结果"],
            },
            {
                "name": "VIP版",
                "features": ["全部会员功能", "多账户视图预留", "管理员审计预留", "高级导出预留"],
            },
        ],
        "upgrade_note": "当前只做本地权限展示，不接真实支付。",
        "disclaimer": settings.disclaimer,
    }


def read_disclaimer() -> dict:
    return {
        "title": "免责声明",
        "content": settings.disclaimer,
        "details": [
            "本系统仅用于学习研究与模拟验证。",
            "不构成任何投资建议。",
            "不承诺收益。",
            "不接券商、不自动下单、不控制交易软件。",
            "交易风险由使用者自行承担。",
        ],
    }

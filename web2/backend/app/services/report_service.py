import csv
import importlib.util
import json
import shutil
from datetime import datetime
from pathlib import Path

from app.core.config import settings
from app.schemas.dashboard import DashboardResponse
from app.schemas.report import ReportResponse
from app.services.auth_service import user_has_member_access
from app.services.data_center import data_center


def _load_ledger_rebuilder():
    path = settings.project_root / "ledger_rebuilder.py"
    spec = importlib.util.spec_from_file_location("ledger_rebuilder", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载 ledger_rebuilder.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def _read_ledger_rebuild_status() -> dict:
    path = settings.project_root / "portfolio" / "ledger_rebuild_status.json"
    if not path.exists() or path.stat().st_size == 0:
        return {}
    for encoding in ("utf-8", "utf-8-sig", "gbk", "gb18030"):
        try:
            return json.loads(path.read_text(encoding=encoding))
        except UnicodeDecodeError:
            continue
        except Exception:
            return {}
    return {}


def _masked(title: str, user: dict) -> ReportResponse:
    return ReportResponse(
        title=title,
        allowed=False,
        content="请升级会员后查看完整报告、订单详情、虚拟账户和验证结果。",
        membership_level=user.get("membership_level", "free"),
        disclaimer=settings.disclaimer,
    )


def build_dashboard(user: dict) -> DashboardResponse:
    context = data_center.get_latest_context()
    paper = context.get("paper", {})
    account = paper.get("account", {})
    equity_curve = paper.get("equity_curve", [])
    latest_equity = equity_curve[-1] if equity_curve else {}
    equity = latest_equity
    validation = _read_latest_csv_row(settings.project_root / "forward_validation.csv")
    risk = _read_latest_csv_row(settings.project_root / "risk_control_report.csv")
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
    context = data_center.get_latest_context()
    return ReportResponse(
        title="Paper Trading 账户",
        allowed=True,
        content=_build_paper_markdown(context),
        membership_level=user.get("membership_level", "free"),
        disclaimer=settings.disclaimer,
    )


def read_paper_data(user: dict) -> dict:
    # Paper Trading API must use DataCenter plus ledger rebuild status.
    # Do not read old markdown reports as account truth; markdown is display output only.
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
    context = data_center.get_latest_context()
    paper = context.get("paper", {})
    ledger_status = _read_ledger_rebuild_status()
    equity_curve = paper.get("equity_curve", [])
    valuation_debug = paper.get("valuation_debug", {})
    positions = paper.get("positions", [])
    trades = _normalize_paper_trades(paper.get("trades", []))
    ledger_audit = _build_ledger_audit(trades, positions)
    closed_trades = _build_closed_trades(trades, positions)
    holding_explain = _build_holding_explain(trades, positions, closed_trades)
    chart_markers = _build_chart_markers(trades)
    stock_trade_points = _build_stock_trade_points(trades, positions)
    drawdown_curve = [
        {
            "date": row.get("date", ""),
            "max_drawdown": row.get("max_drawdown", "0"),
        }
        for row in equity_curve
    ]
    return {
        "allowed": True,
        "latest_report_date": context.get("latest_report_date", ""),
        "data_updated_at": context.get("data_updated_at", ""),
        "ledger_source": ledger_status.get("ledger_source", "positions.csv"),
        "ledger_rebuild_status": ledger_status,
        "source_files": context.get("source_files", {}),
        "debug": {
            **context.get("debug", {}),
            **valuation_debug,
            "valuation_debug": valuation_debug,
        },
        "account": paper.get("account", {}),
        "paper_summary": {
            "total_assets": paper.get("total_assets", ""),
            "cash": paper.get("cash", ""),
            "holding_value": paper.get("holding_value", ""),
            "cumulative_return": paper.get("cumulative_return", ""),
        },
        "positions": positions,
        "trades": trades[-50:],
        "closed_trades": closed_trades,
        "sold_positions": closed_trades,
        "holding_explain": holding_explain,
        "ledger_audit": ledger_audit,
        "chart_markers": chart_markers,
        "stock_trade_points": stock_trade_points,
        "intraday_status": {
            "available": False,
            "reason": "当前系统未接入分钟/分时行情，暂只支持日线买卖点展示",
        },
        "equity_curve": equity_curve,
        "drawdown_curve": drawdown_curve,
        "markdown_report": _build_paper_markdown(context),
        "membership_level": user.get("membership_level", "free"),
        "disclaimer": settings.disclaimer,
    }


def read_paper_ledger_audit(user: dict) -> dict:
    if not user_has_member_access(user):
        return {
            "allowed": False,
            "ledger_audit": {},
            "message": "请升级会员后查看 Paper Trading 账本审计。",
            "membership_level": user.get("membership_level", "free"),
            "disclaimer": settings.disclaimer,
        }
    context = data_center.get_latest_context()
    paper = context.get("paper", {})
    positions = paper.get("positions", [])
    trades = _normalize_paper_trades(paper.get("trades", []))
    return {
        "allowed": True,
        "latest_report_date": context.get("latest_report_date", ""),
        "data_updated_at": context.get("data_updated_at", ""),
        "source_files": context.get("source_files", {}),
        "ledger_audit": _build_ledger_audit(trades, positions),
        "membership_level": user.get("membership_level", "free"),
        "disclaimer": settings.disclaimer,
    }


def repair_missing_buy_trades(user: dict) -> dict:
    if not user_has_member_access(user):
        return {
            "allowed": False,
            "appended": [],
            "message": "请升级会员后执行账本修复。",
            "membership_level": user.get("membership_level", "free"),
            "disclaimer": settings.disclaimer,
        }

    context = data_center.get_latest_context()
    paper = context.get("paper", {})
    positions = paper.get("positions", [])
    trades = _normalize_paper_trades(paper.get("trades", []))
    audit = _build_ledger_audit(trades, positions)
    suggestions = audit.get("suggested_repair_trades", [])
    trades_path = settings.project_root / "portfolio" / "trades.csv"
    if not suggestions:
        return {
            "allowed": True,
            "appended": [],
            "backup_file": "",
            "message": "没有需要补齐的 BUY 流水。",
            "ledger_audit": audit,
            "membership_level": user.get("membership_level", "free"),
            "disclaimer": settings.disclaimer,
        }

    existing_keys = {
        (
            str(row.get("date", "")),
            str(row.get("code", "")).zfill(6),
            str(row.get("side", "")).upper(),
        )
        for row in trades
    }
    append_rows = []
    for item in suggestions:
        key = (str(item.get("date", "")), str(item.get("code", "")).zfill(6), "BUY")
        if key in existing_keys:
            continue
        append_rows.append(
            {
                "date": item.get("date", ""),
                "code": str(item.get("code", "")).zfill(6),
                "name": item.get("name", ""),
                "side": "BUY",
                "price": item.get("price", ""),
                "shares": item.get("shares", ""),
                "amount": item.get("amount", ""),
                "cash_after": "",
                "pnl": 0,
                "pnl_pct": 0,
                "reason": item.get("reason", "由当前持仓反推补齐缺失买入流水"),
            }
        )

    if not append_rows:
        return {
            "allowed": True,
            "appended": [],
            "backup_file": "",
            "message": "建议流水已存在，未重复追加。",
            "ledger_audit": audit,
            "membership_level": user.get("membership_level", "free"),
            "disclaimer": settings.disclaimer,
        }

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = trades_path.with_name(f"trades_backup_{timestamp}.csv")
    if trades_path.exists():
        shutil.copy2(trades_path, backup_path)

    fieldnames = [
        "date",
        "code",
        "name",
        "side",
        "price",
        "shares",
        "amount",
        "cash_after",
        "pnl",
        "pnl_pct",
        "reason",
    ]
    file_exists = trades_path.exists() and trades_path.stat().st_size > 0
    with trades_path.open("a", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerows(append_rows)

    return {
        "allowed": True,
        "appended": append_rows,
        "backup_file": str(backup_path) if backup_path.exists() else "",
        "message": "已根据当前持仓反推补齐缺失 BUY 流水；unknown_closed 未处理。",
        "ledger_audit": audit,
        "membership_level": user.get("membership_level", "free"),
        "disclaimer": settings.disclaimer,
    }


def read_paper_rebuild_ledger_preview(user: dict) -> dict:
    if not user_has_member_access(user):
        return {
            "allowed": False,
            "message": "请升级会员后查看账本重建预览。",
            "membership_level": user.get("membership_level", "free"),
            "disclaimer": settings.disclaimer,
        }
    module = _load_ledger_rebuilder()
    return {
        "allowed": True,
        **module.preview_rebuild(settings.project_root),
        "membership_level": user.get("membership_level", "free"),
        "disclaimer": settings.disclaimer,
    }


def run_paper_rebuild_ledger(user: dict) -> dict:
    if not user_has_member_access(user):
        return {
            "allowed": False,
            "message": "请升级会员后执行账本重建。",
            "membership_level": user.get("membership_level", "free"),
            "disclaimer": settings.disclaimer,
        }
    module = _load_ledger_rebuilder()
    return {
        "allowed": True,
        **module.rebuild_ledger(settings.project_root),
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


def _build_paper_markdown(context: dict) -> str:
    paper = context.get("paper", {})
    account = paper.get("account", {})
    positions = paper.get("positions", [])
    trades = _normalize_paper_trades(paper.get("trades", []))
    closed_trades = _build_closed_trades(trades, positions)
    holding_explain = _build_holding_explain(trades, positions, closed_trades)
    equity_curve = paper.get("equity_curve", [])
    latest_equity = equity_curve[-1] if equity_curve else {}
    max_drawdown = latest_equity.get("max_drawdown", "0")
    lines = [
        f"# Paper Trading 虚拟账户报告 {context.get('latest_report_date', '')}",
        "",
        "## 账户概览",
        f"- 数据更新时间：{context.get('data_updated_at', '')}",
        f"- 总资产：{account.get('total_assets', paper.get('total_assets', ''))}",
        f"- 现金：{account.get('cash', paper.get('cash', ''))}",
        f"- 持仓市值：{account.get('holding_value') or account.get('market_value') or paper.get('holding_value', '')}",
        f"- 累计收益：{account.get('cumulative_return', paper.get('cumulative_return', ''))}%",
        f"- 最大回撤：{max_drawdown}%",
        "",
        "## 当前持仓",
    ]
    if positions:
        for pos in positions:
            lines.append(
                f"- {pos.get('stock_code') or pos.get('code')} {pos.get('name', '')}："
                f"成本 {pos.get('cost_price') or pos.get('buy_price', '')}，"
                f"现价 {pos.get('latest_price', '')}，"
                f"浮盈 {pos.get('floating_pnl') or pos.get('pnl', '')}，"
                f"持仓 {pos.get('holding_days', '')} 天"
            )
    else:
        lines.append("- 暂无持仓")

    lines.extend([
        "",
        "## 持仓解释",
        f"- 当前持仓数量：{holding_explain['current_positions_count']}",
        f"- 历史买入股票数量：{holding_explain['historical_buy_codes_count']}",
        f"- 已卖出或当前未持仓数量：{len(holding_explain['closed_or_missing_codes'])}",
        f"- 说明：{holding_explain['explanation']}",
    ])

    lines.extend(["", "## 最近交易"])
    if trades:
        for trade in trades[-10:]:
            lines.append(
                f"- {trade.get('date', '')} {trade.get('stock_code') or trade.get('code')} "
                f"{trade.get('name', '')} {trade.get('action', '')} "
                f"{trade.get('shares', '')} 股，价格 {trade.get('price', '')}，金额 {trade.get('amount', '')}"
            )
    else:
        lines.append("- 暂无交易记录")

    lines.extend(["", "## 已卖出/未持仓记录"])
    if closed_trades:
        for item in closed_trades[:20]:
            lines.append(
                f"- {item.get('code')} {item.get('name')}：状态 {item.get('status')}，"
                f"买入 {item.get('buy_date', '')} @{item.get('buy_price', '')}，"
                f"卖出 {item.get('sell_date', '')} @{item.get('sell_price', '')}，"
                f"盈亏 {item.get('pnl', '')}"
            )
    else:
        lines.append("- 暂无已卖出或缺失持仓记录")

    lines.extend(["", "## 免责声明", settings.disclaimer])
    return "\n".join(lines)


def _normalize_paper_trades(trades: list[dict]) -> list[dict]:
    result = []
    for row in trades:
        code = str(row.get("code") or row.get("stock_code") or "").zfill(6)
        side = row.get("side") or row.get("action") or ""
        result.append(
            {
                **row,
                "date": row.get("date") or row.get("trade_date") or "",
                "code": code,
                "stock_code": code,
                "name": row.get("name", ""),
                "side": side,
                "action": side,
                "price": row.get("price") or row.get("trade_price") or "",
                "shares": row.get("shares") or row.get("qty") or "",
                "amount": row.get("amount", ""),
                "reason": row.get("reason", ""),
                "pnl": row.get("pnl", ""),
                "pnl_pct": row.get("pnl_pct", ""),
            }
        )
    return result


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value, default: int = 0) -> int:
    try:
        if value in (None, ""):
            return default
        return int(float(value))
    except Exception:
        return default


def _position_code(pos: dict) -> str:
    return str(pos.get("code") or pos.get("stock_code") or "").zfill(6)


def _position_buy_price(pos: dict) -> float:
    return _safe_float(pos.get("buy_price") or pos.get("cost_price"))


def _build_ledger_audit(trades: list[dict], positions: list[dict]) -> dict:
    holding_map = {_position_code(pos): pos for pos in positions if _position_code(pos).strip("0")}
    buys_by_code: dict[str, list[dict]] = {}
    sells_by_code: dict[str, list[dict]] = {}
    for trade in trades:
        code = str(trade.get("code") or trade.get("stock_code") or "").zfill(6)
        if not code.strip("0"):
            continue
        side = str(trade.get("side") or trade.get("action") or "").upper()
        if side == "BUY":
            buys_by_code.setdefault(code, []).append(trade)
        elif side == "SELL":
            sells_by_code.setdefault(code, []).append(trade)

    matched_positions = []
    orphan_positions = []
    suggested_repair_trades = []
    for code, pos in holding_map.items():
        item = {
            "code": code,
            "name": pos.get("name", ""),
            "buy_date": pos.get("buy_date", ""),
            "buy_price": pos.get("buy_price") or pos.get("cost_price", ""),
            "shares": pos.get("shares", ""),
            "latest_price": pos.get("latest_price", ""),
            "market_value": pos.get("market_value", ""),
            "status": pos.get("status", "holding"),
        }
        if code in buys_by_code:
            latest_buy = buys_by_code[code][-1]
            item["matched_buy_date"] = latest_buy.get("date", "")
            item["matched_buy_price"] = latest_buy.get("price", "")
            matched_positions.append(item)
            continue

        orphan_positions.append(item)
        buy_date = str(pos.get("buy_date") or "").strip()
        price = _position_buy_price(pos)
        shares = _safe_int(pos.get("shares"))
        if buy_date and price > 0 and shares > 0:
            suggested_repair_trades.append(
                {
                    "date": buy_date,
                    "code": code,
                    "name": pos.get("name", ""),
                    "side": "BUY",
                    "price": round(price, 2),
                    "shares": shares,
                    "amount": round(price * shares, 2),
                    "reason": "由当前持仓反推补齐缺失买入流水",
                }
            )

    unknown_closed = []
    for code, buys in buys_by_code.items():
        if code in holding_map or sells_by_code.get(code):
            continue
        latest_buy = buys[-1]
        unknown_closed.append(
            {
                "code": code,
                "name": latest_buy.get("name", ""),
                "buy_date": latest_buy.get("date", ""),
                "buy_price": latest_buy.get("price", ""),
                "shares": latest_buy.get("shares", ""),
                "amount": latest_buy.get("amount", ""),
                "status": "UNKNOWN",
                "warning": "交易流水存在买入，但当前持仓缺失且无卖出记录，需要检查是否漏记SELL或positions被覆盖",
            }
        )

    ledger_consistent = not orphan_positions and not unknown_closed
    warning = "" if ledger_consistent else "交易账本不一致，收益与买卖点仅供排查，不可作为真实验证结果。"
    return {
        "ledger_consistent": ledger_consistent,
        "matched_positions": matched_positions,
        "orphan_positions": orphan_positions,
        "unknown_closed": unknown_closed,
        "suggested_repair_trades": suggested_repair_trades,
        "warning": warning,
        "summary": {
            "matched_positions_count": len(matched_positions),
            "orphan_positions_count": len(orphan_positions),
            "unknown_closed_count": len(unknown_closed),
            "suggested_repair_count": len(suggested_repair_trades),
        },
    }


def _build_closed_trades(trades: list[dict], positions: list[dict]) -> list[dict]:
    holding_codes = {str(pos.get("code") or pos.get("stock_code") or "").zfill(6) for pos in positions}
    buys_by_code: dict[str, list[dict]] = {}
    sells_by_code: dict[str, list[dict]] = {}
    for trade in trades:
        code = str(trade.get("code") or "").zfill(6)
        side = str(trade.get("side") or "").upper()
        if side == "BUY":
            buys_by_code.setdefault(code, []).append(trade)
        elif side == "SELL":
            sells_by_code.setdefault(code, []).append(trade)

    rows = []
    for code, buys in buys_by_code.items():
        if code in holding_codes:
            continue
        latest_buy = buys[-1]
        latest_sell = sells_by_code.get(code, [])[-1] if sells_by_code.get(code) else {}
        status = "sold" if latest_sell else "unknown_closed"
        rows.append(
            {
                "code": code,
                "name": latest_buy.get("name", "") or latest_sell.get("name", ""),
                "buy_date": latest_buy.get("date", ""),
                "buy_price": latest_buy.get("price", ""),
                "buy_amount": latest_buy.get("amount", ""),
                "sell_date": latest_sell.get("date", ""),
                "sell_price": latest_sell.get("price", ""),
                "sell_amount": latest_sell.get("amount", ""),
                "pnl": latest_sell.get("pnl", ""),
                "pnl_pct": latest_sell.get("pnl_pct", ""),
                "status": status,
                "explain": "已有SELL记录，当前不在持仓中" if status == "sold" else "历史交易存在但当前持仓文件无该票，需检查交易流水",
            }
        )
    return rows


def _build_holding_explain(trades: list[dict], positions: list[dict], closed_trades: list[dict]) -> dict:
    holding_codes = {str(pos.get("code") or pos.get("stock_code") or "").zfill(6) for pos in positions}
    buy_codes = {str(trade.get("code") or "").zfill(6) for trade in trades if str(trade.get("side") or "").upper() == "BUY"}
    closed_codes = [row.get("code", "") for row in closed_trades]
    if closed_codes:
        explanation = "历史买入数量大于当前持仓数量，因为部分股票已卖出，或当前持仓文件中已不再保留该股票。缺少SELL流水的记录会标记为 unknown_closed。"
    else:
        explanation = "当前持仓与历史买入记录暂未发现缺口。"
    return {
        "current_positions_count": len(holding_codes),
        "historical_buy_codes_count": len(buy_codes),
        "closed_or_missing_codes": closed_codes,
        "explanation": explanation,
    }


def _build_chart_markers(trades: list[dict]) -> list[dict]:
    markers = []
    for trade in trades:
        side = str(trade.get("side") or "").upper()
        if side not in {"BUY", "SELL"}:
            continue
        markers.append(
            {
                "date": trade.get("date", ""),
                "code": trade.get("code", ""),
                "name": trade.get("name", ""),
                "side": side,
                "price": trade.get("price", ""),
                "label": f"{trade.get('date', '')} {side} {trade.get('code', '')} {trade.get('name', '')} {trade.get('price', '')}",
            }
        )
    return markers


def _build_stock_trade_points(trades: list[dict], positions: list[dict]) -> list[dict]:
    position_map = {str(pos.get("code") or pos.get("stock_code") or "").zfill(6): pos for pos in positions}
    grouped: dict[str, dict] = {}
    for trade in trades:
        code = str(trade.get("code") or "").zfill(6)
        if not code:
            continue
        item = grouped.setdefault(
            code,
            {
                "code": code,
                "name": trade.get("name", ""),
                "buy_points": [],
                "sell_points": [],
                "is_holding": code in position_map,
                "current_price": position_map.get(code, {}).get("latest_price", ""),
                "current_pnl": position_map.get(code, {}).get("pnl", ""),
            },
        )
        side = str(trade.get("side") or "").upper()
        point = {
            "date": trade.get("date", ""),
            "price": trade.get("price", ""),
            "shares": trade.get("shares", ""),
            "amount": trade.get("amount", ""),
            "reason": trade.get("reason", ""),
        }
        if side == "BUY":
            item["buy_points"].append(point)
        elif side == "SELL":
            item["sell_points"].append(point)
    return list(grouped.values())


def _build_closed_trades(trades: list[dict], positions: list[dict]) -> list[dict]:
    """按账本审计口径展示已卖出或未知缺口，避免把缺 SELL 的记录误判为已平仓。"""
    holding_codes = {_position_code(pos) for pos in positions}
    buys_by_code: dict[str, list[dict]] = {}
    sells_by_code: dict[str, list[dict]] = {}
    for trade in trades:
        code = str(trade.get("code") or "").zfill(6)
        side = str(trade.get("side") or "").upper()
        if side == "BUY":
            buys_by_code.setdefault(code, []).append(trade)
        elif side == "SELL":
            sells_by_code.setdefault(code, []).append(trade)

    rows = []
    for code, buys in buys_by_code.items():
        if code in holding_codes:
            continue
        latest_buy = buys[-1]
        latest_sell = sells_by_code.get(code, [])[-1] if sells_by_code.get(code) else {}
        status = "SOLD" if latest_sell else "UNKNOWN"
        rows.append(
            {
                "code": code,
                "name": latest_buy.get("name", "") or latest_sell.get("name", ""),
                "buy_date": latest_buy.get("date", ""),
                "buy_price": latest_buy.get("price", ""),
                "buy_amount": latest_buy.get("amount", ""),
                "sell_date": latest_sell.get("date", ""),
                "sell_price": latest_sell.get("price", ""),
                "sell_amount": latest_sell.get("amount", ""),
                "pnl": latest_sell.get("pnl", ""),
                "pnl_pct": latest_sell.get("pnl_pct", ""),
                "status": status,
                "explain": "已有 SELL 记录，当前不在持仓中"
                if status == "SOLD"
                else "交易流水存在买入，但当前持仓缺失且无卖出记录，需要检查是否漏记SELL或positions被覆盖",
            }
        )
    return rows


def read_leaders(user: dict) -> dict:
    if not user_has_member_access(user):
        return {
            "allowed": False,
            "items": [],
            "message": "请升级会员后查看龙头排行榜。",
            "membership_level": user.get("membership_level", "free"),
            "disclaimer": settings.disclaimer,
        }
    context = data_center.get_latest_context()
    latest_report_date = context.get("latest_report_date", "")
    trend_rows = context.get("trend_core", [])
    leader_rows = context.get("leader_tier", []) or context.get("leader_detection", [])
    leader_dates = {
        str(row.get("date", "")).strip()
        for row in leader_rows
        if str(row.get("date", "")).strip()
    }
    # 龙头页必须优先展示最新复盘结果。leader_tier.csv 可能是旧日快照，
    # 如果日期落后，则使用最新 trend_core_pool 生成展示型梯队，不改变任何策略逻辑。
    if trend_rows and latest_report_date and latest_report_date not in leader_dates:
        rows = trend_rows
        source_type = "trend_core_pool_latest"
    else:
        rows = leader_rows or trend_rows
        source_type = "leader_tier"
    items = []
    for row in rows[:50]:
        rank = str(row.get("rank", "")).strip()
        try:
            rank_number = int(float(rank)) if rank else len(items) + 1
        except Exception:
            rank_number = len(items) + 1
        score = row.get("master_score") or row.get("combined_score") or row.get("trend_score") or ""
        tier = row.get("leader_tier", "")
        if not tier:
            if rank_number <= 3:
                tier = "T1（核心龙头）"
            elif rank_number <= 10:
                tier = "T2（趋势前排）"
            else:
                tier = "trend_core"
        items.append(
            {
                "code": row.get("code", ""),
                "name": row.get("name", ""),
                "master_score": score,
                "leader_tier": tier,
                "momentum_score": row.get("momentum_score", ""),
                "trend_score": row.get("trend_score", ""),
                "risk_level": row.get("risk_level", ""),
                "rank": rank_number,
                "source_date": row.get("date", latest_report_date),
            }
        )
    return {
        "allowed": True,
        "latest_report_date": latest_report_date,
        "data_updated_at": context.get("data_updated_at", ""),
        "source_files": context.get("source_files", {}),
        "source_type": source_type,
        "debug": context.get("debug", {}),
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
    context = data_center.get_latest_context()
    payload = context.get("frozen_payload", {})
    path_text = context.get("source_files", {}).get("frozen_orders", "")
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
        "latest_report_date": context.get("latest_report_date", ""),
        "data_updated_at": context.get("data_updated_at", ""),
        "date": payload.get("date", meta.get("date", "")),
        "is_frozen": bool(payload.get("is_frozen", meta.get("is_frozen", False))),
        "freeze_time": meta.get("freeze_time", payload.get("frozen_at", "")),
        "source_file": path_text,
        "source_files": context.get("source_files", {}),
        "debug": context.get("debug", {}),
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

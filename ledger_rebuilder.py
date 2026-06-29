from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import datetime
from pathlib import Path


INITIAL_CASH = 100000.0
CSV_ENCODINGS = ["utf-8", "utf-8-sig", "gbk", "gb18030"]
# Source of Truth:
# portfolio/trades.csv is the only executable Paper Trading ledger.
# portfolio/positions.csv and portfolio/equity_curve.csv are reconstructed outputs.
POSITION_COLUMNS = [
    "date",
    "code",
    "name",
    "buy_date",
    "buy_price",
    "shares",
    "latest_price",
    "market_value",
    "pnl",
    "pnl_pct",
    "holding_days",
    "miss_days",
    "status",
]
EQUITY_COLUMNS = [
    "date",
    "total_assets",
    "cash",
    "market_value",
    "daily_pnl",
    "daily_return",
    "cumulative_return",
    "max_drawdown",
    "holding_count",
]


def preview_rebuild(project_root: str | Path | None = None, target_date: str | None = None) -> dict:
    root = Path(project_root) if project_root else Path(__file__).resolve().parent
    paths = _paths(root)
    trades = _read_csv(paths["trades"])
    current_positions = _read_csv(paths["positions"])
    target_date = target_date or _latest_quote_date(root) or _latest_trade_date(trades)
    quote_map, quote_file, missing_quote_codes = _read_latest_quotes(root, target_date)
    replay = _replay_trades(trades, target_date, quote_map)
    orphan_positions = _find_orphan_positions(current_positions, trades)
    return {
        "mode": "preview",
        "ledger_source": "trades replay",
        "target_date": target_date,
        "initial_cash": INITIAL_CASH,
        "quote_file": str(quote_file) if quote_file else "",
        "trades_file": str(paths["trades"]),
        "positions_file": str(paths["positions"]),
        "equity_curve_file": str(paths["equity"]),
        "reconstructed_positions": replay["positions"],
        "reconstructed_equity_curve": replay["equity_curve"],
        "orphan_positions": orphan_positions,
        "missing_quote_codes": missing_quote_codes,
        "total_assets": replay["summary"]["total_assets"],
        "cash": replay["summary"]["cash"],
        "market_value": replay["summary"]["market_value"],
        "ledger_consistent": not orphan_positions,
        "warning": "当前 positions.csv 存在无 BUY 流水持仓，重建时不会纳入正式持仓。"
        if orphan_positions
        else "",
    }


def rebuild_ledger(project_root: str | Path | None = None, target_date: str | None = None) -> dict:
    root = Path(project_root) if project_root else Path(__file__).resolve().parent
    preview = preview_rebuild(root, target_date)
    paths = _paths(root)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backups = {}
    for key in ["positions", "equity", "trades"]:
        path = paths[key]
        if path.exists():
            backup_path = path.with_name(f"{path.stem}_backup_{timestamp}{path.suffix}")
            shutil.copy2(path, backup_path)
            backups[key] = str(backup_path)

    _write_csv(paths["positions"], preview["reconstructed_positions"], POSITION_COLUMNS)
    _write_csv(paths["equity"], preview["reconstructed_equity_curve"], EQUITY_COLUMNS)

    report_path = paths["portfolio"] / f"ledger_rebuild_report_{timestamp}.md"
    report_text = _build_report(preview, backups)
    report_path.write_text(report_text, encoding="utf-8")

    status_path = paths["portfolio"] / "ledger_rebuild_status.json"
    status_payload = {
        "ledger_source": "trades replay",
        "target_date": preview["target_date"],
        "rebuild_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "report_file": str(report_path),
        "backups": backups,
    }
    status_path.write_text(json.dumps(status_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        **preview,
        "mode": "rebuild",
        "backups": backups,
        "report_file": str(report_path),
        "status_file": str(status_path),
        "ledger_consistent": True,
        "warning": "已按 trades replay 重建 positions/equity；orphan_positions 已排除，未补流水。",
    }


def _paths(root: Path) -> dict[str, Path]:
    portfolio = root / "portfolio"
    return {
        "portfolio": portfolio,
        "trades": portfolio / "trades.csv",
        "positions": portfolio / "positions.csv",
        "equity": portfolio / "equity_curve.csv",
    }


def _read_csv(path: Path) -> list[dict]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    for encoding in CSV_ENCODINGS:
        try:
            with path.open("r", encoding=encoding, newline="") as file:
                return [{str(k).lstrip("\ufeff").strip(): v for k, v in row.items()} for row in csv.DictReader(file)]
        except UnicodeDecodeError:
            continue
    return []


def _write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def _latest_trade_date(trades: list[dict]) -> str:
    dates = sorted(str(row.get("date", "")) for row in trades if row.get("date"))
    return dates[-1] if dates else datetime.now().strftime("%Y%m%d")


def _latest_quote_date(root: Path) -> str:
    quote_paths = sorted((root / "data" / "raw").glob("daily_quotes_*.csv"))
    if not quote_paths:
        return ""
    return quote_paths[-1].stem.replace("daily_quotes_", "")


def _read_latest_quotes(root: Path, target_date: str) -> tuple[dict[str, dict], Path | None, list[str]]:
    candidates = [
        root / "data" / "raw" / f"daily_quotes_{target_date}.csv",
        root / "data" / "processed" / f"daily_quotes_{target_date}.csv",
        root / f"daily_quotes_{target_date}.csv",
    ]
    for path in candidates:
        rows = _read_csv(path)
        if not rows:
            continue
        result = {}
        for row in rows:
            code = _code(row)
            price = _first_number(row, ["close", "latest_price", "current_price", "price"])
            if code and price > 0:
                result[code] = {
                    "price": price,
                    "name": row.get("name", ""),
                    "date": str(row.get("date") or target_date),
                    "source": str(path),
                }
        return result, path, []
    return {}, None, []


def _replay_trades(trades: list[dict], target_date: str, quote_map: dict[str, dict]) -> dict:
    cash = INITIAL_CASH
    positions: dict[str, dict] = {}
    equity_rows = []
    previous_assets = INITIAL_CASH
    peak = INITIAL_CASH
    max_drawdown = 0.0
    sorted_trades = sorted(trades, key=lambda row: (str(row.get("date", "")), str(row.get("code", ""))))

    current_date = ""
    for trade in sorted_trades:
        date = str(trade.get("date", "")).strip()
        if current_date and date != current_date:
            equity_rows.append(_equity_row(current_date, cash, positions, previous_assets, peak, max_drawdown))
            previous_assets = _number(equity_rows[-1]["total_assets"])
            peak = max(peak, previous_assets)
            max_drawdown = min(max_drawdown, _number(equity_rows[-1]["max_drawdown"]))
        current_date = date or current_date
        _apply_trade(trade, cash_ref := {"cash": cash}, positions)
        cash = cash_ref["cash"]

    if current_date:
        equity_rows.append(_equity_row(current_date, cash, positions, previous_assets, peak, max_drawdown))
        previous_assets = _number(equity_rows[-1]["total_assets"])
        peak = max(peak, previous_assets)
        max_drawdown = min(max_drawdown, _number(equity_rows[-1]["max_drawdown"]))

    final_positions = _position_rows(positions, target_date, quote_map)
    market_value = sum(_number(row["market_value"]) for row in final_positions)
    total_assets = cash + market_value
    daily_pnl = total_assets - previous_assets
    daily_return = daily_pnl / previous_assets * 100 if previous_assets else 0.0
    cumulative_return = (total_assets / INITIAL_CASH - 1) * 100 if INITIAL_CASH else 0.0
    peak = max(peak, total_assets)
    drawdown = (total_assets - peak) / peak * 100 if peak else 0.0
    max_drawdown = min(max_drawdown, drawdown)
    final_row = {
        "date": target_date,
        "total_assets": _fmt(total_assets),
        "cash": _fmt(cash),
        "market_value": _fmt(market_value),
        "daily_pnl": _fmt(daily_pnl),
        "daily_return": _fmt(daily_return),
        "cumulative_return": _fmt(cumulative_return),
        "max_drawdown": _fmt(max_drawdown),
        "holding_count": len(final_positions),
    }
    if not equity_rows or equity_rows[-1]["date"] != target_date:
        equity_rows.append(final_row)
    else:
        equity_rows[-1] = final_row

    return {
        "positions": final_positions,
        "equity_curve": equity_rows,
        "summary": {
            "cash": _fmt(cash),
            "market_value": _fmt(market_value),
            "total_assets": _fmt(total_assets),
            "cumulative_return": _fmt(cumulative_return),
            "max_drawdown": _fmt(max_drawdown),
        },
    }


def _apply_trade(trade: dict, cash_ref: dict, positions: dict[str, dict]) -> None:
    code = _code(trade)
    if not code:
        return
    side = str(trade.get("side") or trade.get("action") or "").upper()
    price = _number(trade.get("price"))
    shares = int(_number(trade.get("shares")))
    amount = _number(trade.get("amount")) or price * shares
    if side == "BUY" and shares > 0 and price > 0:
        cash_ref["cash"] -= amount
        pos = positions.setdefault(
            code,
            {
                "code": code,
                "name": trade.get("name", ""),
                "buy_date": str(trade.get("date", "")),
                "shares": 0,
                "cost_amount": 0.0,
                "last_price": price,
            },
        )
        pos["name"] = pos.get("name") or trade.get("name", "")
        pos["buy_date"] = min(str(pos.get("buy_date") or trade.get("date", "")), str(trade.get("date", "")))
        pos["shares"] += shares
        pos["cost_amount"] += amount
        pos["last_price"] = price
    elif side == "SELL" and shares > 0:
        cash_ref["cash"] += amount
        pos = positions.get(code)
        if not pos:
            return
        sell_shares = min(shares, int(pos.get("shares", 0)))
        avg_cost = pos["cost_amount"] / pos["shares"] if pos["shares"] else 0
        pos["shares"] -= sell_shares
        pos["cost_amount"] -= avg_cost * sell_shares
        pos["last_price"] = price
        if pos["shares"] <= 0:
            positions.pop(code, None)


def _equity_row(date: str, cash: float, positions: dict[str, dict], previous_assets: float, peak: float, max_drawdown: float) -> dict:
    market_value = sum(_number(pos.get("last_price")) * int(pos.get("shares", 0)) for pos in positions.values())
    total_assets = cash + market_value
    daily_pnl = total_assets - previous_assets
    daily_return = daily_pnl / previous_assets * 100 if previous_assets else 0.0
    cumulative_return = (total_assets / INITIAL_CASH - 1) * 100 if INITIAL_CASH else 0.0
    peak = max(peak, total_assets)
    drawdown = (total_assets - peak) / peak * 100 if peak else 0.0
    max_drawdown = min(max_drawdown, drawdown)
    return {
        "date": date,
        "total_assets": _fmt(total_assets),
        "cash": _fmt(cash),
        "market_value": _fmt(market_value),
        "daily_pnl": _fmt(daily_pnl),
        "daily_return": _fmt(daily_return),
        "cumulative_return": _fmt(cumulative_return),
        "max_drawdown": _fmt(max_drawdown),
        "holding_count": len(positions),
    }


def _position_rows(positions: dict[str, dict], target_date: str, quote_map: dict[str, dict]) -> list[dict]:
    rows = []
    for code, pos in sorted(positions.items()):
        shares = int(pos.get("shares", 0))
        if shares <= 0:
            continue
        avg_cost = pos["cost_amount"] / shares if shares else 0.0
        quote = quote_map.get(code, {})
        latest_price = _number(quote.get("price")) or _number(pos.get("last_price")) or avg_cost
        market_value = latest_price * shares
        pnl = (latest_price - avg_cost) * shares
        pnl_pct = (latest_price / avg_cost - 1) * 100 if avg_cost else 0.0
        rows.append(
            {
                "date": target_date,
                "code": code,
                "name": pos.get("name") or quote.get("name", ""),
                "buy_date": pos.get("buy_date", ""),
                "buy_price": _fmt(avg_cost),
                "shares": shares,
                "latest_price": _fmt(latest_price),
                "market_value": _fmt(market_value),
                "pnl": _fmt(pnl),
                "pnl_pct": _fmt(pnl_pct),
                "holding_days": _holding_days(str(pos.get("buy_date", "")), target_date),
                "miss_days": 0,
                "status": "holding",
            }
        )
    return rows


def _find_orphan_positions(current_positions: list[dict], trades: list[dict]) -> list[dict]:
    buy_codes = {_code(row) for row in trades if str(row.get("side") or row.get("action") or "").upper() == "BUY"}
    result = []
    for pos in current_positions:
        code = _code(pos)
        if code and code not in buy_codes:
            result.append(
                {
                    "code": code,
                    "name": pos.get("name", ""),
                    "buy_date": pos.get("buy_date", ""),
                    "buy_price": pos.get("buy_price") or pos.get("cost_price", ""),
                    "shares": pos.get("shares", ""),
                    "latest_price": pos.get("latest_price", ""),
                    "reason": "当前持仓存在，但 trades.csv 没有对应 BUY，重建时不纳入正式持仓。",
                }
            )
    return result


def _build_report(preview: dict, backups: dict) -> str:
    lines = [
        f"# Paper Trading 账本重建报告 {preview.get('target_date', '')}",
        "",
        "## 重建原则",
        "- 以 portfolio/trades.csv 为唯一交易流水。",
        "- BUY 扣现金并增加持仓，SELL 加现金并减少持仓。",
        "- 当前 positions.csv 中没有 BUY 流水的股票仅标记为 orphan_positions，不进入正式重建持仓。",
        "- 本次不补流水、不删除历史文件、不修改交易规则。",
        "",
        "## 备份文件",
    ]
    for key, path in backups.items():
        lines.append(f"- {key}: {path}")
    lines.extend([
        "",
        "## 重建后当前持仓",
    ])
    for pos in preview.get("reconstructed_positions", []):
        lines.append(f"- {pos['code']} {pos['name']} shares={pos['shares']} latest={pos['latest_price']} pnl={pos['pnl']}")
    lines.extend(["", "## orphan_positions"])
    for pos in preview.get("orphan_positions", []):
        lines.append(f"- {pos['code']} {pos['name']}：{pos['reason']}")
    lines.extend([
        "",
        "## 账户汇总",
        f"- cash: {preview.get('cash')}",
        f"- market_value: {preview.get('market_value')}",
        f"- total_assets: {preview.get('total_assets')}",
    ])
    return "\n".join(lines)


def _code(row: dict) -> str:
    return str(row.get("code") or row.get("stock_code") or "").zfill(6)


def _number(value) -> float:
    try:
        if value in (None, ""):
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def _first_number(row: dict, keys: list[str]) -> float:
    for key in keys:
        value = _number(row.get(key))
        if value > 0:
            return value
    return 0.0


def _fmt(value: float) -> str:
    return str(round(value, 4)).rstrip("0").rstrip(".") if value else "0"


def _holding_days(start: str, end: str) -> int:
    try:
        return max(0, (datetime.strptime(end, "%Y%m%d") - datetime.strptime(start, "%Y%m%d")).days)
    except Exception:
        return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="重建 Paper Trading 账本")
    parser.add_argument("--apply", action="store_true", help="写入 positions.csv 和 equity_curve.csv")
    parser.add_argument("--date", default="", help="估值日期 YYYYMMDD")
    args = parser.parse_args()
    payload = rebuild_ledger(target_date=args.date or None) if args.apply else preview_rebuild(target_date=args.date or None)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

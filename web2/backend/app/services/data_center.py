from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.services.quote_sync import read_quote_sync_status


CSV_ENCODINGS = ["utf-8", "utf-8-sig", "gbk", "gb18030"]


class DataCenter:
    """Web2 统一数据中心：只负责读取最新本地结果，不修改任何策略和交易数据。"""

    def __init__(self) -> None:
        self.project_root = settings.project_root

    def get_latest_context(self) -> dict:
        # Source of Truth:
        # - daily_quotes_YYYYMMDD.csv provides latest valuation prices.
        # - portfolio/trades.csv is the only Paper Trading trade ledger.
        # - positions/equity are derived artifacts and must not be treated as independent truth.
        missing_files: list[str] = []
        read_errors: list[dict] = []
        selected = self._select_files(missing_files)

        leaders = self._read_csv(selected.get("leader_tier"), read_errors)
        leader_detection = self._read_csv(selected.get("leader_detection"), read_errors)
        trend_core = self._read_csv(selected.get("trend_core_pool"), read_errors)
        frozen_payload = self._read_json(selected.get("frozen_orders"), read_errors)
        frozen_orders = frozen_payload.get("orders", []) if isinstance(frozen_payload, dict) else []
        daily_report_text = self._read_text(selected.get("daily_report"), read_errors)

        source_files = {key: self._path_text(path) for key, path in selected.items()}
        latest_report_date = self._latest_report_date(selected, {}, frozen_payload)
        paper = self._build_paper(selected, read_errors, latest_report_date)
        latest_report_date = self._latest_report_date(selected, paper, frozen_payload)
        data_updated_at = self._data_updated_at(selected)

        return {
            "latest_report_date": latest_report_date,
            "data_updated_at": data_updated_at,
            "source_files": source_files,
            "paper": paper,
            "leaders": leaders or leader_detection,
            "leader_detection": leader_detection,
            "leader_tier": leaders,
            "trend_core": trend_core,
            "frozen_orders": frozen_orders,
            "frozen_payload": frozen_payload,
            "daily_report_text": daily_report_text,
            "debug": {
                "missing_files": missing_files,
                "read_errors": read_errors,
                "selected_files": source_files,
            },
        }

    def status(self) -> dict:
        context = self.get_latest_context()
        paper = context.get("paper", {})
        return {
            "latest_report_date": context.get("latest_report_date", ""),
            "data_updated_at": context.get("data_updated_at", ""),
            "source_files": context.get("source_files", {}),
            "paper_summary": {
                "total_assets": paper.get("total_assets", ""),
                "cash": paper.get("cash", ""),
                "holding_value": paper.get("holding_value", ""),
                "cumulative_return": paper.get("cumulative_return", ""),
            },
            "leader_count": len(context.get("leaders", [])),
            "trend_core_count": len(context.get("trend_core", [])),
            "frozen_order_count": len(context.get("frozen_orders", [])),
            "debug": context.get("debug", {}),
        }

    def _select_files(self, missing_files: list[str]) -> dict[str, Path | None]:
        files = {
            "daily_report": self._latest_by_name("reports/daily/daily_report_*.md"),
            "paper_account": self._existing("paper_account.csv"),
            "paper_positions": self._latest_by_mtime(["paper_positions.csv", "portfolio/positions.csv"]),
            "paper_trades": self._latest_by_mtime(["paper_trades.csv", "portfolio/trades.csv"]),
            "equity_curve": self._latest_by_mtime(["paper_equity_curve.csv", "portfolio/equity_curve.csv"]),
            "leader_detection": self._existing("leader_detection.csv"),
            "leader_tier": self._existing("leader_tier.csv"),
            "trend_core_pool": self._latest_by_name("data/processed/trend_core_pool_*.csv"),
            "frozen_orders": self._latest_by_name("frozen_decisions/orders_*.json"),
            "cycle_strength": self._existing("cycle_strength_report.csv"),
            "strategy_health_score": self._existing("strategy_health_score.csv"),
            "portfolio_positions": self._existing("portfolio/positions.csv"),
            "portfolio_trades": self._existing("portfolio/trades.csv"),
            "root_daily_quotes": self._latest_by_name("daily_quotes_*.csv"),
            "raw_daily_quotes": self._latest_by_name("data/raw/daily_quotes_*.csv"),
            "market_snapshot": self._existing("data/mock/market_snapshot.json"),
        }
        for key, path in files.items():
            if path is None:
                missing_files.append(key)
        return files

    def _build_paper(self, selected: dict[str, Path | None], read_errors: list[dict], latest_report_date: str) -> dict:
        account_rows = self._read_csv(selected.get("paper_account"), read_errors)
        positions = self._normalize_positions(self._read_csv(selected.get("paper_positions"), read_errors))
        trades = self._normalize_trades(self._read_csv(selected.get("paper_trades"), read_errors))
        equity_curve = self._normalize_equity_curve(self._read_csv(selected.get("equity_curve"), read_errors))
        account = account_rows[-1] if account_rows else {}
        price_map, valuation_debug = self.resolve_latest_price_map(latest_report_date, positions, read_errors)
        positions = self._revalue_positions(positions, price_map, latest_report_date)
        cash = self._resolve_cash(equity_curve, account)
        holding_value_number = sum(self._number(row.get("market_value")) for row in positions)
        total_assets_number = cash + holding_value_number
        initial_assets = self._resolve_initial_assets(equity_curve)
        cumulative_return_number = ((total_assets_number / initial_assets - 1) * 100) if initial_assets else 0.0
        equity_curve = self._replace_latest_equity_row(
            equity_curve,
            latest_report_date,
            cash,
            holding_value_number,
            total_assets_number,
            cumulative_return_number,
            len(positions),
        )

        return {
            "account": {
                **account,
                "total_assets": self._format_number(total_assets_number),
                "cash": self._format_number(cash),
                "market_value": self._format_number(holding_value_number),
                "holding_value": self._format_number(holding_value_number),
                "cumulative_return": self._format_number(cumulative_return_number),
                "date": latest_report_date or account.get("date") or "",
            },
            "total_assets": self._format_number(total_assets_number),
            "cash": self._format_number(cash),
            "holding_value": self._format_number(holding_value_number),
            "cumulative_return": self._format_number(cumulative_return_number),
            "positions": positions,
            "trades": trades,
            "equity_curve": equity_curve,
            "valuation_debug": valuation_debug,
        }

    def resolve_latest_price_map(
        self,
        latest_report_date: str,
        positions: list[dict] | None = None,
        read_errors: list[dict] | None = None,
    ) -> tuple[dict[str, dict], dict]:
        """按统一顺序解析最新价，供 Paper Trading 动态估值使用。"""
        read_errors = read_errors if read_errors is not None else []
        positions = positions or []
        codes = [str(row.get("code") or row.get("stock_code") or "").zfill(6) for row in positions]
        codes = [code for code in codes if code and code != "000000"]
        price_map: dict[str, dict] = {}
        missing: list[str] = []
        fallback: list[str] = []
        candidates: list[dict] = []
        selected_sources: dict[str, str] = {}

        source_defs = [
            ("root_daily_quotes", self.project_root / f"daily_quotes_{latest_report_date}.csv"),
            ("raw_daily_quotes", self.project_root / f"data/raw/daily_quotes_{latest_report_date}.csv"),
            ("processed_daily_quotes", self.project_root / f"data/processed/daily_quotes_{latest_report_date}.csv"),
            ("market_snapshot", self.project_root / "data/mock/market_snapshot.json"),
            ("trend_core_pool", self.project_root / f"data/processed/trend_core_pool_{latest_report_date}.csv"),
        ]

        for source_name, path in source_defs:
            rows = self._read_price_source(path, source_name, latest_report_date, read_errors)
            found_codes = sorted(set(rows) & set(codes))
            stale_codes = sorted(code for code in found_codes if rows[code].get("is_stale"))
            candidates.append(
                {
                    "source": source_name,
                    "path": self._path_text(path) if path.exists() else self._path_text(path),
                    "exists": path.exists(),
                    "found_codes": found_codes,
                    "stale_codes": stale_codes,
                }
            )
            for code in codes:
                if code in price_map:
                    continue
                item = rows.get(code)
                if item and not item.get("is_stale"):
                    price_map[code] = item
                    selected_sources[code] = source_name

        old_position_prices = self._position_price_map(positions)
        candidates.append(
            {
                "source": "portfolio_positions_old_latest_price",
                "path": "portfolio/positions.csv 或 paper_positions.csv",
                "exists": bool(positions),
                "found_codes": sorted(set(old_position_prices) & set(codes)),
                "stale_codes": [],
            }
        )
        for code in codes:
            if code in price_map:
                continue
            item = old_position_prices.get(code)
            if item:
                price_map[code] = item
                selected_sources[code] = "portfolio_positions_old_latest_price"
                fallback.append(code)

        cost_prices = self._cost_price_map(positions)
        candidates.append(
            {
                "source": "cost_price",
                "path": "positions.cost_price/buy_price",
                "exists": bool(positions),
                "found_codes": sorted(set(cost_prices) & set(codes)),
                "stale_codes": [],
            }
        )
        for code in codes:
            if code in price_map:
                continue
            item = cost_prices.get(code)
            if item:
                price_map[code] = item
                selected_sources[code] = "cost_price"
                fallback.append(code)
            else:
                missing.append(code)

        quote_status = read_quote_sync_status()
        stale_files = [
            {
                "source": item.get("source"),
                "path": item.get("path"),
                "stale_codes": item.get("stale_codes", []),
            }
            for item in candidates
            if item.get("stale_codes")
        ]
        stale_reason = ""
        if stale_files:
            stale_reason = "候选行情文件内部 date 与 latest_report_date 不一致，已跳过这些旧行情。"

        selected_price_source = "mixed"
        unique_sources = sorted(set(selected_sources.values()))
        if len(unique_sources) == 1:
            selected_price_source = unique_sources[0]
        elif not unique_sources:
            selected_price_source = ""

        debug = {
            "latest_report_date": latest_report_date,
            "quote_sync_status": quote_status.get("quote_sync_status", "unknown"),
            "quote_sync_error": quote_status.get("quote_sync_error", ""),
            "price_source_candidates": candidates,
            "selected_price_source": selected_price_source,
            "selected_price_sources_by_code": selected_sources,
            "position_price_map": {
                code: {
                    "price": item.get("price"),
                    "source": item.get("source"),
                    "source_date": item.get("source_date"),
                    "is_stale": item.get("is_stale", False),
                }
                for code, item in price_map.items()
            },
            "missing_price_codes": missing,
            "fallback_price_codes": sorted(set(fallback)),
            "stale_files": stale_files,
            "stale_reason": stale_reason,
        }
        return price_map, debug

    def _read_price_source(self, path: Path, source_name: str, latest_report_date: str, read_errors: list[dict]) -> dict[str, dict]:
        if not path.exists() or path.stat().st_size == 0:
            return {}
        if path.suffix.lower() == ".json":
            return self._read_price_json(path, source_name, latest_report_date, read_errors)
        rows = self._read_csv(path, read_errors)
        result: dict[str, dict] = {}
        for row in rows:
            code = str(row.get("code") or row.get("stock_code") or row.get("证券代码") or "").zfill(6)
            if not code or code == "000000":
                continue
            price = self._first_number(row, ["latest_price", "current_price", "close", "price", "收盘", "最新价"])
            if price <= 0:
                continue
            source_date = str(row.get("date") or row.get("trade_date") or row.get("day") or "").strip()
            is_stale = bool(latest_report_date and source_date and source_date != latest_report_date)
            result[code] = {
                "price": price,
                "source": source_name,
                "source_date": source_date,
                "is_stale": is_stale,
            }
        return result

    def _read_price_json(self, path: Path, source_name: str, latest_report_date: str, read_errors: list[dict]) -> dict[str, dict]:
        payload = self._read_json(path, read_errors)
        result: dict[str, dict] = {}

        def visit(value):
            if isinstance(value, dict):
                code = str(value.get("code") or value.get("stock_code") or "").zfill(6)
                price = self._first_number(value, ["latest_price", "current_price", "close", "price"])
                if code and code != "000000" and price > 0:
                    source_date = str(value.get("date") or value.get("trade_date") or latest_report_date or "").strip()
                    result[code] = {
                        "price": price,
                        "source": source_name,
                        "source_date": source_date,
                        "is_stale": bool(latest_report_date and source_date and source_date != latest_report_date),
                    }
                for child in value.values():
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)

        visit(payload)
        return result

    def _position_price_map(self, positions: list[dict]) -> dict[str, dict]:
        result = {}
        for row in positions:
            code = str(row.get("code") or row.get("stock_code") or "").zfill(6)
            price = self._first_number(row, ["latest_price", "current_price"])
            if code and code != "000000" and price > 0:
                result[code] = {
                    "price": price,
                    "source": "portfolio_positions_old_latest_price",
                    "source_date": str(row.get("date") or ""),
                    "is_stale": False,
                }
        return result

    def _cost_price_map(self, positions: list[dict]) -> dict[str, dict]:
        result = {}
        for row in positions:
            code = str(row.get("code") or row.get("stock_code") or "").zfill(6)
            price = self._first_number(row, ["cost_price", "buy_price"])
            if code and code != "000000" and price > 0:
                result[code] = {
                    "price": price,
                    "source": "cost_price",
                    "source_date": str(row.get("buy_date") or ""),
                    "is_stale": False,
                }
        return result

    def _revalue_positions(self, positions: list[dict], price_map: dict[str, dict], latest_report_date: str) -> list[dict]:
        result = []
        for row in positions:
            code = str(row.get("code") or row.get("stock_code") or "").zfill(6)
            shares = self._number(row.get("shares"))
            cost_price = self._first_number(row, ["cost_price", "buy_price"])
            price_item = price_map.get(code, {})
            latest_price = self._number(price_item.get("price")) or cost_price
            market_value = latest_price * shares
            pnl = (latest_price - cost_price) * shares
            pnl_pct = ((latest_price / cost_price - 1) * 100) if cost_price else 0.0
            result.append(
                {
                    **row,
                    "date": latest_report_date or row.get("date", ""),
                    "stock_code": code,
                    "code": code,
                    "cost_price": self._format_number(cost_price),
                    "buy_price": self._format_number(cost_price),
                    "latest_price": self._format_number(latest_price),
                    "current_price": self._format_number(latest_price),
                    "market_value": self._format_number(market_value),
                    "floating_pnl": self._format_number(pnl),
                    "pnl": self._format_number(pnl),
                    "pnl_pct": self._format_number(pnl_pct),
                    "price_source": price_item.get("source", "cost_price"),
                    "price_source_date": price_item.get("source_date", ""),
                    "price_is_fallback": price_item.get("source") in {"portfolio_positions_old_latest_price", "cost_price"},
                }
            )
        return result

    def _resolve_cash(self, equity_curve: list[dict], account: dict) -> float:
        if equity_curve:
            cash = self._number(equity_curve[-1].get("cash"))
            if cash:
                return cash
        return self._number(account.get("cash"))

    def _resolve_initial_assets(self, equity_curve: list[dict]) -> float:
        if equity_curve:
            first_total = self._number(equity_curve[0].get("total_assets"))
            if first_total:
                return first_total
        return 100000.0

    def _replace_latest_equity_row(
        self,
        rows: list[dict],
        latest_report_date: str,
        cash: float,
        holding_value: float,
        total_assets: float,
        cumulative_return: float,
        holding_count: int,
    ) -> list[dict]:
        rows = [dict(row) for row in rows]
        previous_total = 0.0
        for row in reversed(rows):
            if str(row.get("date", "")) != latest_report_date:
                previous_total = self._number(row.get("total_assets"))
                if previous_total:
                    break
        if not previous_total and rows:
            previous_total = self._number(rows[-1].get("total_assets"))
        daily_pnl = total_assets - previous_total if previous_total else 0.0
        daily_return = (daily_pnl / previous_total * 100) if previous_total else 0.0
        latest_row = {
            "date": latest_report_date,
            "total_assets": self._format_number(total_assets),
            "cash": self._format_number(cash),
            "holding_value": self._format_number(holding_value),
            "market_value": self._format_number(holding_value),
            "daily_pnl": self._format_number(daily_pnl),
            "daily_return": self._format_number(daily_return),
            "cumulative_return": self._format_number(cumulative_return),
            "holding_count": str(holding_count),
        }
        replaced = False
        for index, row in enumerate(rows):
            if str(row.get("date", "")) == latest_report_date:
                rows[index] = {**row, **latest_row}
                replaced = True
        if not replaced:
            rows.append(latest_row)
        return self._normalize_equity_curve(rows)

    def _normalize_equity_curve(self, rows: list[dict]) -> list[dict]:
        result: list[dict] = []
        peak = 0.0
        max_drawdown = 0.0
        for index, row in enumerate(rows, start=1):
            total_assets = self._number(row.get("total_assets"))
            cash = self._number(row.get("cash"))
            holding_value = self._number(row.get("holding_value") or row.get("market_value"))
            cumulative_return = self._number(row.get("cumulative_return"))
            daily_return = self._number(row.get("daily_return"))
            peak = max(peak, total_assets)
            drawdown = ((total_assets - peak) / peak * 100) if peak else 0.0
            raw_max_drawdown = row.get("max_drawdown")
            if raw_max_drawdown in (None, ""):
                max_drawdown = min(max_drawdown, drawdown)
            else:
                max_drawdown = min(max_drawdown, self._number(raw_max_drawdown))
            date = str(row.get("date") or row.get("trade_date") or row.get("day") or "").strip()
            if not date:
                date = f"row_{index}"
            result.append(
                {
                    **row,
                    "date": date,
                    "total_assets": self._format_number(total_assets),
                    "cash": self._format_number(cash),
                    "holding_value": self._format_number(holding_value),
                    "market_value": self._format_number(holding_value),
                    "daily_return": self._format_number(daily_return),
                    "cumulative_return": self._format_number(cumulative_return),
                    "drawdown": self._format_number(drawdown),
                    "max_drawdown": self._format_number(max_drawdown),
                }
            )
        return result

    def _normalize_positions(self, rows: list[dict]) -> list[dict]:
        result = []
        for row in rows:
            code = str(row.get("stock_code") or row.get("code") or "").zfill(6)
            cost_price = row.get("cost_price") or row.get("buy_price") or ""
            floating_pnl = row.get("floating_pnl") or row.get("pnl") or ""
            result.append(
                {
                    **row,
                    "stock_code": code,
                    "code": code,
                    "cost_price": cost_price,
                    "buy_price": row.get("buy_price") or cost_price,
                    "latest_price": row.get("latest_price") or row.get("current_price") or "",
                    "floating_pnl": floating_pnl,
                    "pnl": row.get("pnl") or floating_pnl,
                    "holding_days": row.get("holding_days", ""),
                    "status": row.get("status", ""),
                }
            )
        return result

    def _normalize_trades(self, rows: list[dict]) -> list[dict]:
        result = []
        for row in rows:
            code = str(row.get("stock_code") or row.get("code") or "").zfill(6)
            result.append(
                {
                    **row,
                    "stock_code": code,
                    "code": code,
                    "date": row.get("date") or row.get("trade_date") or "",
                    "action": row.get("action") or row.get("side") or "",
                    "price": row.get("price") or row.get("trade_price") or "",
                    "shares": row.get("shares") or row.get("qty") or "",
                    "amount": row.get("amount", ""),
                    "pnl": row.get("pnl", ""),
                    "pnl_pct": row.get("pnl_pct", ""),
                }
            )
        return result

    def _number(self, value) -> float:
        try:
            if value in (None, ""):
                return 0.0
            return float(value)
        except Exception:
            return 0.0

    def _first_number(self, row: dict, keys: list[str]) -> float:
        for key in keys:
            value = row.get(key)
            number = self._number(value)
            if number > 0:
                return number
        return 0.0

    def _format_number(self, value: float) -> str:
        return str(round(value, 4)).rstrip("0").rstrip(".") if value else "0"

    def _read_csv(self, path: Path | None, read_errors: list[dict]) -> list[dict]:
        if not path or not path.exists() or path.stat().st_size == 0:
            return []
        failures: list[str] = []
        for encoding in CSV_ENCODINGS:
            try:
                with path.open("r", encoding=encoding, newline="") as file:
                    return [self._clean_row(row) for row in csv.DictReader(file)]
            except UnicodeDecodeError as exc:
                failures.append(f"{encoding}: {exc}")
        read_errors.append({"path": self._path_text(path), "type": "csv", "errors": failures})
        return []

    def _clean_row(self, row: dict) -> dict:
        return {str(key).lstrip("\ufeff").strip(): value for key, value in row.items()}

    def _read_json(self, path: Path | None, read_errors: list[dict]) -> dict:
        if not path or not path.exists() or path.stat().st_size == 0:
            return {}
        for encoding in CSV_ENCODINGS:
            try:
                return json.loads(path.read_text(encoding=encoding))
            except UnicodeDecodeError:
                continue
            except Exception as exc:
                read_errors.append({"path": self._path_text(path), "type": "json", "error": str(exc)})
                return {}
        read_errors.append({"path": self._path_text(path), "type": "json", "error": "encoding fallback failed"})
        return {}

    def _read_text(self, path: Path | None, read_errors: list[dict]) -> str:
        if not path or not path.exists() or path.stat().st_size == 0:
            return ""
        for encoding in CSV_ENCODINGS:
            try:
                return path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue
            except Exception as exc:
                read_errors.append({"path": self._path_text(path), "type": "text", "error": str(exc)})
                return ""
        read_errors.append({"path": self._path_text(path), "type": "text", "error": "encoding fallback failed"})
        return ""

    def _existing(self, relative: str) -> Path | None:
        path = self.project_root / relative
        return path if path.exists() else None

    def _latest_by_name(self, pattern: str) -> Path | None:
        paths = sorted(self.project_root.glob(pattern))
        return paths[-1] if paths else None

    def _latest_by_mtime(self, relatives: list[str]) -> Path | None:
        paths = [self.project_root / item for item in relatives]
        paths = [path for path in paths if path.exists()]
        return max(paths, key=lambda path: path.stat().st_mtime) if paths else None

    def _data_updated_at(self, selected: dict[str, Path | None]) -> str:
        paths = [path for path in selected.values() if path and path.exists()]
        if not paths:
            return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        latest = max(path.stat().st_mtime for path in paths)
        return datetime.fromtimestamp(latest).strftime("%Y-%m-%d %H:%M:%S")

    def _latest_report_date(self, selected: dict[str, Path | None], paper: dict, frozen_payload: Any) -> str:
        candidates = [
            self._date_from_path(selected.get("daily_report")),
            self._date_from_path(selected.get("trend_core_pool")),
            str(frozen_payload.get("date", "")) if isinstance(frozen_payload, dict) else "",
            str(paper.get("account", {}).get("date", "")),
        ]
        for item in candidates:
            digits = "".join(ch for ch in item if ch.isdigit())
            if len(digits) >= 8:
                return digits[-8:]
        return ""

    def _date_from_path(self, path: Path | None) -> str:
        if not path:
            return ""
        digits = "".join(ch for ch in path.stem if ch.isdigit())
        return digits[-8:] if len(digits) >= 8 else ""

    def _path_text(self, path: Path | None) -> str:
        if not path:
            return ""
        try:
            return str(path.relative_to(self.project_root))
        except ValueError:
            return str(path)


data_center = DataCenter()

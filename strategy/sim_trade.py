from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd

from strategy.trend_core import _fetch_stock_history


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
TRADE_COLUMNS = [
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
BUY_LOG_COLUMNS = [
    "date",
    "code",
    "name",
    "price",
    "shares",
    "required_amount",
    "cash_before",
    "success",
    "fail_reason",
]
STRATEGY_REPORT_COLUMNS = [
    "date",
    "buy_count",
    "sell_count",
    "hold_count",
    "win_count",
    "loss_count",
    "win_rate",
    "avg_pnl_pct",
    "best_trade_pct",
    "worst_trade_pct",
    "total_assets",
    "cumulative_return",
    "max_drawdown",
]
REPORT_EQUITY_COLUMNS = ["date", "cash", "market_value", "total_assets", "daily_return", "cumulative_return"]


def _read_csv(path: Path, columns: list[str]) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame(columns=columns)
    return pd.read_csv(path, dtype={"code": str})


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _days_between(start: str, end: str) -> int:
    try:
        return max(0, (datetime.strptime(end, "%Y%m%d") - datetime.strptime(start, "%Y%m%d")).days)
    except Exception:
        return 0


def _normalize_positions(positions: pd.DataFrame, target_date: str) -> pd.DataFrame:
    """兼容第一阶段旧持仓字段，统一成第二阶段字段。"""
    if positions.empty:
        return pd.DataFrame(columns=POSITION_COLUMNS)

    rows = []
    for pos in positions.to_dict("records"):
        code = str(pos.get("code", "")).zfill(6)
        shares = int(_safe_float(pos.get("shares", pos.get("qty", 0))))
        buy_price = _safe_float(pos.get("buy_price"))
        latest_price = _safe_float(pos.get("latest_price", pos.get("current_price", buy_price)))
        buy_date = str(pos.get("buy_date", target_date))
        market_value = shares * latest_price
        pnl = (latest_price - buy_price) * shares
        pnl_pct = ((latest_price / buy_price - 1) * 100) if buy_price else 0.0
        rows.append(
            {
                "date": target_date,
                "code": code,
                "name": pos.get("name", ""),
                "buy_date": buy_date,
                "buy_price": round(buy_price, 2),
                "shares": shares,
                "latest_price": round(latest_price, 2),
                "market_value": round(market_value, 2),
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 2),
                "holding_days": _days_between(buy_date, target_date),
                "miss_days": int(_safe_float(pos.get("miss_days", 0))),
                "status": str(pos.get("status", "holding")).lower(),
            }
        )
    return pd.DataFrame(rows, columns=POSITION_COLUMNS)


def _lookup_latest_price(code: str, target_date: str, pool: pd.DataFrame, quotes: pd.DataFrame, fallback_price: float) -> float:
    """获取持仓最新收盘价，优先用趋势池和行情快照，缺失时单独拉取日线。"""
    pool_match = pool[pool["code"] == code] if not pool.empty and "code" in pool.columns else pd.DataFrame()
    if not pool_match.empty and "close" in pool_match.columns:
        return _safe_float(pool_match.iloc[0]["close"], fallback_price)

    quote_match = quotes[quotes["code"] == code] if not quotes.empty and "code" in quotes.columns else pd.DataFrame()
    if not quote_match.empty and "close" in quote_match.columns:
        return _safe_float(quote_match.iloc[0]["close"], fallback_price)

    hist = _fetch_stock_history(code, target_date)
    if not hist.empty and "close" in hist.columns:
        return _safe_float(hist.iloc[-1]["close"], fallback_price)
    print(f"持仓价格更新失败：{code} 缺少最新收盘价，沿用上一价格。")
    return fallback_price


def _analyze_positions(positions: pd.DataFrame) -> dict:
    """分析当前持仓盈亏分布。"""
    if positions.empty:
        return {
            "profit_count": 0,
            "loss_count": 0,
            "position_win_rate": 0.0,
            "avg_position_pnl_pct": 0.0,
            "max_profit_pct": 0.0,
            "max_loss_pct": 0.0,
        }

    pnl_pct = pd.to_numeric(positions["pnl_pct"], errors="coerce").fillna(0)
    profit_count = int((pnl_pct > 0).sum())
    loss_count = int((pnl_pct < 0).sum())
    finished = profit_count + loss_count
    return {
        "profit_count": profit_count,
        "loss_count": loss_count,
        "position_win_rate": round(profit_count / finished * 100, 2) if finished else 0.0,
        "avg_position_pnl_pct": round(float(pnl_pct.mean()), 2),
        "max_profit_pct": round(float(pnl_pct.max()), 2),
        "max_loss_pct": round(float(pnl_pct.min()), 2),
    }


def _latest_cash_and_asset(equity: pd.DataFrame, initial_cash: float) -> tuple[float, float]:
    """兼容旧 equity_curve 字段，读取上一日现金和总资产。"""
    if equity.empty:
        return initial_cash, initial_cash
    latest = equity.iloc[-1]
    cash = _safe_float(latest.get("cash"), initial_cash)
    total_assets = _safe_float(latest.get("total_assets", latest.get("total_asset")), initial_cash)
    return cash, total_assets


def _calc_max_drawdown(equity: pd.DataFrame) -> float:
    if equity.empty or "total_assets" not in equity.columns:
        return 0.0
    assets = pd.to_numeric(equity["total_assets"], errors="coerce").dropna()
    if assets.empty:
        return 0.0
    running_max = assets.cummax()
    drawdown = assets / running_max - 1
    return round(float(drawdown.min() * 100), 2)


def _build_strategy_report(
    target_date: str,
    trades: pd.DataFrame,
    equity: pd.DataFrame,
    buy_count: int,
    sell_count: int,
    hold_count: int,
    total_assets: float,
    cumulative_return: float,
    max_drawdown: float,
) -> dict:
    sold = trades[trades["side"] == "SELL"].copy() if not trades.empty and "side" in trades.columns else pd.DataFrame()
    if not sold.empty and "pnl_pct" in sold.columns:
        sold["pnl_pct"] = pd.to_numeric(sold["pnl_pct"], errors="coerce")
        finished = sold.dropna(subset=["pnl_pct"])
    else:
        finished = pd.DataFrame()

    win_count = int((finished["pnl_pct"] > 0).sum()) if not finished.empty else 0
    loss_count = int((finished["pnl_pct"] <= 0).sum()) if not finished.empty else 0
    total_finished = win_count + loss_count
    win_rate = win_count / total_finished * 100 if total_finished else 0.0

    return {
        "date": target_date,
        "buy_count": buy_count,
        "sell_count": sell_count,
        "hold_count": hold_count,
        "win_count": win_count,
        "loss_count": loss_count,
        "win_rate": round(win_rate, 2),
        "avg_pnl_pct": round(float(finished["pnl_pct"].mean()), 2) if not finished.empty else 0.0,
        "best_trade_pct": round(float(finished["pnl_pct"].max()), 2) if not finished.empty else 0.0,
        "worst_trade_pct": round(float(finished["pnl_pct"].min()), 2) if not finished.empty else 0.0,
        "total_assets": round(total_assets, 2),
        "cumulative_return": round(cumulative_return, 2),
        "max_drawdown": max_drawdown,
    }


def run_sim_trade(target_date: str, pool_path: Path, config: Dict, project_root: Path) -> Dict:
    """根据趋势池执行模拟买卖，并更新持仓、交易流水、权益曲线和策略统计。"""
    portfolio_dir = project_root / str(config.get("portfolio_dir", "portfolio"))
    portfolio_dir.mkdir(parents=True, exist_ok=True)

    positions_path = portfolio_dir / "positions.csv"
    trades_path = portfolio_dir / "trades.csv"
    equity_path = portfolio_dir / "equity_curve.csv"
    strategy_report_path = portfolio_dir / "strategy_report.csv"
    report_equity_path = project_root / "reports" / "equity_curve.csv"
    quotes_path = project_root / "data" / "raw" / f"daily_quotes_{target_date}.csv"

    initial_cash = float(config.get("initial_cash", 100000))
    buy_top_n = int(config.get("buy_top_n", 5))
    buy_lot = int(config.get("buy_lot", 100))

    pool = _read_csv(pool_path, [])
    if not pool.empty:
        pool["code"] = pool["code"].astype(str).str.zfill(6)
    pool_codes = set(pool["code"].tolist()) if "code" in pool.columns else set()

    positions = _normalize_positions(_read_csv(positions_path, POSITION_COLUMNS), target_date)
    trades = _read_csv(trades_path, TRADE_COLUMNS)
    equity = _read_csv(equity_path, EQUITY_COLUMNS)
    quotes = _read_csv(quotes_path, [])
    if not quotes.empty:
        quotes["code"] = quotes["code"].astype(str).str.zfill(6)

    cash, yesterday_assets = _latest_cash_and_asset(equity, initial_cash)
    previous_assets = yesterday_assets
    today_trades = []
    buy_logs = []

    # 每日先更新历史持仓最新价格和浮动盈亏，再决定是否卖出。
    kept_positions = []
    for pos in positions.to_dict("records"):
        code = str(pos.get("code", "")).zfill(6)
        status = str(pos.get("status", "holding")).lower()
        shares = int(_safe_float(pos.get("shares")))
        buy_price = _safe_float(pos.get("buy_price"))
        latest_price = _lookup_latest_price(code, target_date, pool, quotes, _safe_float(pos.get("latest_price", buy_price)))
        pnl = (latest_price - buy_price) * shares
        pnl_pct = (latest_price / buy_price - 1) * 100 if buy_price else 0.0
        updated_pos = {
            "date": target_date,
            "code": code,
            "name": pos.get("name", ""),
            "buy_date": pos.get("buy_date", target_date),
            "buy_price": round(buy_price, 2),
            "shares": shares,
            "latest_price": round(latest_price, 2),
            "market_value": round(latest_price * shares, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "holding_days": _days_between(str(pos.get("buy_date", target_date)), target_date),
            "miss_days": 0 if code in pool_codes else int(_safe_float(pos.get("miss_days", 0))) + 1,
            "status": "holding",
        }

        if status not in {"holding", "hold"}:
            kept_positions.append(updated_pos)
            continue

        if code not in pool_codes and updated_pos["miss_days"] < 2:
            kept_positions.append(updated_pos)
            print(
                f"持仓观察 | {code} {updated_pos['name']} 连续不满足趋势条件:"
                f"{updated_pos['miss_days']}/2，暂不卖出"
            )
            continue

        if code not in pool_codes:
            amount = latest_price * shares
            cash += amount
            trade = {
                "date": target_date,
                "code": code,
                "name": pos.get("name", ""),
                "side": "SELL",
                "price": round(latest_price, 2),
                "shares": shares,
                "amount": round(amount, 2),
                "cash_after": round(cash, 2),
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 2),
                "reason": "连续2天不满足趋势条件，模拟卖出",
            }
            today_trades.append(trade)
            print(
                f"卖出日志 | {code} {trade['name']} 价格:{trade['price']} "
                f"数量:{shares} 金额:{trade['amount']} 现金:{trade['cash_after']} 原因:{trade['reason']}"
            )
            continue

        kept_positions.append(updated_pos)

    positions = pd.DataFrame(kept_positions, columns=POSITION_COLUMNS)

    # 买入趋势池 trend_score 前 N；每个候选都输出成败原因。
    holding_codes = set(positions["code"].astype(str).str.zfill(6).tolist()) if not positions.empty else set()
    score_col = "trend_score" if "trend_score" in pool.columns else "score"
    buy_candidates = pool.sort_values(score_col, ascending=False).head(buy_top_n) if not pool.empty and score_col in pool.columns else pd.DataFrame()

    for item in buy_candidates.to_dict("records"):
        code = str(item.get("code", "")).zfill(6)
        name = item.get("name", "")
        price = _safe_float(item.get("close"), np.nan)
        required_amount = price * buy_lot if not pd.isna(price) else 0.0
        cash_before = cash
        success = False
        fail_reason = ""

        try:
            if len(code) != 6 or not code.isdigit():
                fail_reason = "股票代码异常"
            elif not item or "close" not in item:
                fail_reason = "数据缺失"
            elif pd.isna(price) or price <= 0:
                fail_reason = "价格为空"
            elif code in holding_codes:
                fail_reason = "已经持仓"
            elif cash < required_amount:
                fail_reason = "现金不足"
            else:
                cash -= required_amount
                success = True
                positions.loc[len(positions)] = {
                    "date": target_date,
                    "code": code,
                    "name": name,
                    "buy_date": target_date,
                    "buy_price": round(price, 2),
                    "shares": buy_lot,
                    "latest_price": round(price, 2),
                    "market_value": round(required_amount, 2),
                    "pnl": 0.0,
                    "pnl_pct": 0.0,
                    "holding_days": 0,
                    "miss_days": 0,
                    "status": "holding",
                }
                holding_codes.add(code)
                today_trades.append(
                    {
                        "date": target_date,
                        "code": code,
                        "name": name,
                        "side": "BUY",
                        "price": round(price, 2),
                        "shares": buy_lot,
                        "amount": round(required_amount, 2),
                        "cash_after": round(cash, 2),
                        "pnl": 0.0,
                        "pnl_pct": 0.0,
                        "reason": "趋势核心池排名靠前，模拟买入",
                    }
                )
        except Exception as exc:
            fail_reason = f"其他异常：{exc}"

        buy_log = {
            "date": target_date,
            "code": code,
            "name": name,
            "price": round(price, 2) if not pd.isna(price) else "",
            "shares": buy_lot,
            "required_amount": round(required_amount, 2),
            "cash_before": round(cash_before, 2),
            "success": success,
            "fail_reason": "" if success else fail_reason,
        }
        buy_logs.append(buy_log)
        print(
            f"买入候选 | {code} {name} 价格:{buy_log['price']} 数量:{buy_lot} "
            f"所需金额:{buy_log['required_amount']} 现金余额:{buy_log['cash_before']} "
            f"是否买入成功:{'是' if success else '否'} 失败原因:{buy_log['fail_reason'] or '-'}"
        )

    market_value = float(positions["market_value"].sum()) if not positions.empty else 0.0
    total_assets = cash + market_value
    daily_pnl = total_assets - yesterday_assets
    daily_return = daily_pnl / yesterday_assets * 100 if yesterday_assets else 0.0
    cumulative_return = (total_assets / initial_cash - 1) * 100 if initial_cash else 0.0

    equity_row = {
        "date": target_date,
        "total_assets": round(total_assets, 2),
        "cash": round(cash, 2),
        "market_value": round(market_value, 2),
        "daily_pnl": round(daily_pnl, 2),
        "daily_return": round(daily_return, 2),
        "cumulative_return": round(cumulative_return, 2),
        "max_drawdown": 0.0,
        "holding_count": int(len(positions)),
    }

    today_trades_df = pd.DataFrame(today_trades, columns=TRADE_COLUMNS)
    trades = trades[trades["date"].astype(str) != target_date] if not trades.empty and "date" in trades.columns else trades
    trades = pd.concat([trades, today_trades_df], ignore_index=True)

    equity = equity[[col for col in EQUITY_COLUMNS if col in equity.columns]] if not equity.empty else pd.DataFrame(columns=EQUITY_COLUMNS)
    equity = equity[equity["date"].astype(str) != target_date] if not equity.empty and "date" in equity.columns else equity
    equity = pd.concat([equity, pd.DataFrame([equity_row])], ignore_index=True)
    max_drawdown = _calc_max_drawdown(equity)
    equity.loc[equity.index[-1], "max_drawdown"] = max_drawdown
    equity_row["max_drawdown"] = max_drawdown

    buy_count = int((today_trades_df["side"] == "BUY").sum()) if not today_trades_df.empty else 0
    sell_count = int((today_trades_df["side"] == "SELL").sum()) if not today_trades_df.empty else 0
    strategy_row = _build_strategy_report(
        target_date,
        trades,
        equity,
        buy_count,
        sell_count,
        int(len(positions)),
        total_assets,
        cumulative_return,
        max_drawdown,
    )
    strategy_report = _read_csv(strategy_report_path, STRATEGY_REPORT_COLUMNS)
    strategy_report = strategy_report[strategy_report["date"].astype(str) != target_date] if not strategy_report.empty else strategy_report
    strategy_report = pd.concat([strategy_report, pd.DataFrame([strategy_row])], ignore_index=True)
    position_analysis = _analyze_positions(positions)

    report_equity = _read_csv(report_equity_path, REPORT_EQUITY_COLUMNS)
    report_equity = report_equity[report_equity["date"].astype(str) != target_date] if not report_equity.empty else report_equity
    report_equity = pd.concat(
        [
            report_equity,
            pd.DataFrame(
                [
                    {
                        "date": target_date,
                        "cash": round(cash, 2),
                        "market_value": round(market_value, 2),
                        "total_assets": round(total_assets, 2),
                        "daily_return": round(daily_return, 2),
                        "cumulative_return": round(cumulative_return, 2),
                    }
                ]
            ),
        ],
        ignore_index=True,
    )

    positions.to_csv(positions_path, index=False, encoding="utf-8-sig")
    trades.to_csv(trades_path, index=False, encoding="utf-8-sig")
    equity.to_csv(equity_path, index=False, encoding="utf-8-sig")
    strategy_report.to_csv(strategy_report_path, index=False, encoding="utf-8-sig")
    report_equity_path.parent.mkdir(parents=True, exist_ok=True)
    report_equity.to_csv(report_equity_path, index=False, encoding="utf-8-sig")

    return {
        "positions": positions,
        "today_trades": today_trades_df,
        "buy_logs": pd.DataFrame(buy_logs, columns=BUY_LOG_COLUMNS),
        "equity_row": equity_row,
        "strategy_row": strategy_row,
        "position_analysis": position_analysis,
        "previous_assets": round(previous_assets, 2),
        "buy_count": buy_count,
        "sell_count": sell_count,
    }

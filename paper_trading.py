from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from strategy.trend_core import _fetch_stock_history


INITIAL_CASH = 100000.0
ACCOUNT_COLUMNS = ["date", "initial_cash", "cash", "market_value", "total_assets", "cumulative_return"]
POSITION_COLUMNS = [
    "date",
    "stock_code",
    "name",
    "buy_date",
    "cost_price",
    "shares",
    "latest_price",
    "market_value",
    "floating_pnl",
    "floating_pnl_pct",
    "holding_days",
    "status",
]
TRADE_COLUMNS = [
    "date",
    "stock_code",
    "name",
    "action",
    "price",
    "shares",
    "amount",
    "pnl",
    "pnl_pct",
    "reason",
]
EQUITY_COLUMNS = [
    "date",
    "cash",
    "market_value",
    "total_assets",
    "daily_return",
    "cumulative_return",
    "max_drawdown",
    "win_rate",
    "profit_factor",
    "sharpe_ratio",
]


def _read_csv(path: Path, columns: list[str], dtype: dict | None = None) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame(columns=columns)
    data = pd.read_csv(path, dtype=dtype or {})
    for column in columns:
        if column not in data.columns:
            data[column] = ""
    return data[columns]


def _read_frozen_orders(project_root: Path, date: str) -> pd.DataFrame:
    frozen_dir = project_root / "frozen_decisions"
    json_path = frozen_dir / f"orders_{date}.json"
    csv_path = frozen_dir / f"orders_{date}.csv"
    if json_path.exists() and json_path.stat().st_size > 0:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        records = payload.get("orders", payload if isinstance(payload, list) else [])
        orders = pd.DataFrame(records)
    elif csv_path.exists() and csv_path.stat().st_size > 0:
        orders = pd.read_csv(csv_path, dtype={"stock_code": str})
    else:
        return pd.DataFrame()
    if not orders.empty and "stock_code" in orders.columns:
        orders["stock_code"] = orders["stock_code"].astype(str).str.zfill(6)
    return orders


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value, default: int = 0) -> int:
    try:
        if pd.isna(value):
            return default
        return int(float(value))
    except Exception:
        return default


def _close_price(code: str, target_date: str) -> float | None:
    hist = _fetch_stock_history(str(code).zfill(6), target_date)
    if hist.empty or "close" not in hist.columns:
        return None
    close = pd.to_numeric(hist.iloc[-1]["close"], errors="coerce")
    if pd.isna(close):
        return None
    return float(close)


def _holding_days(buy_date: str, target_date: str) -> int:
    try:
        start = pd.to_datetime(str(buy_date), format="%Y%m%d")
        end = pd.to_datetime(str(target_date), format="%Y%m%d")
        return max(0, int((end - start).days))
    except Exception:
        return 0


def _regime_cap(market_regime: str) -> float:
    text = str(market_regime)
    if "空仓" in text or "防守" in text:
        return 0.0
    if "观望" in text:
        return 0.20
    if "参与" in text or "中性" in text:
        return 0.50
    if "进攻" in text or "重仓" in text:
        return 1.00
    return 0.0


def _calc_stats(trades: pd.DataFrame, equity: pd.DataFrame) -> dict:
    closed = trades[(trades["action"] == "SELL") & (pd.to_numeric(trades["pnl"], errors="coerce").notna())].copy()
    if closed.empty:
        win_rate = 0.0
        profit_factor = 0.0
    else:
        pnl = pd.to_numeric(closed["pnl"], errors="coerce").fillna(0)
        wins = pnl[pnl > 0]
        losses = pnl[pnl < 0]
        win_rate = round(float((pnl > 0).mean() * 100), 2)
        profit_factor = round(float(wins.sum() / abs(losses.sum())), 2) if abs(losses.sum()) > 0 else (round(float(wins.sum()), 2) if wins.sum() > 0 else 0.0)

    if equity.empty or len(equity) < 2:
        sharpe = 0.0
    else:
        daily = pd.to_numeric(equity["daily_return"], errors="coerce").dropna() / 100
        sharpe = round(float(daily.mean() / daily.std() * np.sqrt(252)), 2) if len(daily) > 1 and daily.std() != 0 else 0.0
    return {"win_rate": win_rate, "profit_factor": profit_factor, "sharpe_ratio": sharpe}


def _format_table(df: pd.DataFrame, columns: list[str], limit: int = 20) -> str:
    if df.empty:
        return "暂无数据"
    view = df[[column for column in columns if column in df.columns]].tail(limit).fillna("")
    if view.empty:
        return "暂无数据"
    rows = [[str(value) for value in row] for row in view.to_numpy().tolist()]
    headers = list(view.columns)
    widths = [max(len(headers[i]), *(len(row[i]) for row in rows)) for i in range(len(headers))]
    lines = [
        "| " + " | ".join(headers[i].ljust(widths[i]) for i in range(len(headers))) + " |",
        "| " + " | ".join("-" * widths[i] for i in range(len(headers))) + " |",
    ]
    lines.extend("| " + " | ".join(row[i].ljust(widths[i]) for i in range(len(headers))) + " |" for row in rows)
    return "\n".join(lines)


def _write_report(path: Path, account: pd.DataFrame, positions: pd.DataFrame, trades: pd.DataFrame, equity: pd.DataFrame) -> None:
    latest = account.iloc[-1].to_dict() if not account.empty else {
        "total_assets": INITIAL_CASH,
        "cumulative_return": 0.0,
        "cash": INITIAL_CASH,
        "market_value": 0.0,
    }
    stats = _calc_stats(trades, equity)
    max_drawdown = round(float(pd.to_numeric(equity.get("max_drawdown", pd.Series(dtype=float)), errors="coerce").min()), 2) if not equity.empty else 0.0
    current_positions = positions[positions["status"] == "holding"].copy() if not positions.empty else pd.DataFrame()
    today = str(latest.get("date", ""))
    today_trades = trades[trades["date"].astype(str) == today].copy() if not trades.empty and today else pd.DataFrame()

    content = f"""# Paper Trading 虚拟账户报告

> 只验证完全按系统信号执行后的虚拟账户表现，不代表实盘结果。

## 账户概览

- 总资产：{round(_safe_float(latest.get('total_assets'), INITIAL_CASH), 2)}
- 现金：{round(_safe_float(latest.get('cash'), INITIAL_CASH), 2)}
- 持仓市值：{round(_safe_float(latest.get('market_value')), 2)}
- 累计收益：{round(_safe_float(latest.get('cumulative_return')), 2)}%
- 最大回撤：{max_drawdown}%
- 胜率：{stats['win_rate']}%
- 盈亏比：{stats['profit_factor']}
- 夏普比率：{stats['sharpe_ratio']}

--------------------------------

## 当前持仓

{_format_table(current_positions, ['stock_code', 'name', 'cost_price', 'latest_price', 'floating_pnl', 'floating_pnl_pct', 'holding_days'], 20)}

--------------------------------

## 今日操作

{_format_table(today_trades, ['date', 'stock_code', 'name', 'action', 'price', 'shares', 'amount', 'pnl', 'reason'], 50)}

--------------------------------

## 资金曲线

{_format_table(equity, ['date', 'total_assets', 'daily_return', 'cumulative_return', 'max_drawdown'], 20)}
"""
    path.write_text(content, encoding="utf-8")


def _load_name_map(project_root: Path, date: str) -> dict:
    pool_path = project_root / "data" / "processed" / f"trend_core_pool_{date}.csv"
    if not pool_path.exists():
        return {}
    pool = pd.read_csv(pool_path, dtype={"code": str})
    if "code" not in pool.columns or "name" not in pool.columns:
        return {}
    pool["code"] = pool["code"].astype(str).str.zfill(6)
    return dict(zip(pool["code"], pool["name"]))


def run_paper_trading(project_root: Path, max_days: int = 10) -> dict:
    validation_path = project_root / "forward_validation.csv"
    if not validation_path.exists():
        raise FileNotFoundError("缺少 forward_validation.csv，请先运行 forward_test.py 生成 Phase 7 验证记录。")

    validation = pd.read_csv(validation_path, dtype={"date": str}).sort_values("date").tail(max_days)
    account_path = project_root / "paper_account.csv"
    positions_path = project_root / "paper_positions.csv"
    trades_path = project_root / "paper_trades.csv"
    equity_path = project_root / "paper_equity_curve.csv"
    report_path = project_root / "paper_report.md"

    cash = INITIAL_CASH
    positions = pd.DataFrame(columns=POSITION_COLUMNS)
    trades = pd.DataFrame(columns=TRADE_COLUMNS)
    account_rows = []
    equity_rows = []
    peak_assets = INITIAL_CASH
    previous_assets = INITIAL_CASH
    missing_frozen_dates = []

    for _, vrow in validation.iterrows():
        date = str(vrow["date"])
        name_map = _load_name_map(project_root, date)
        frozen_json_path = project_root / "frozen_decisions" / f"orders_{date}.json"
        frozen_csv_path = project_root / "frozen_decisions" / f"orders_{date}.csv"
        if not frozen_json_path.exists() and not frozen_csv_path.exists():
            missing_frozen_dates.append(date)
            print(f"提示：{date} 缺少冻结订单，Paper Trading 跳过该日。请先运行 decision_freeze.py --date {date}")
            continue
        orders = _read_frozen_orders(project_root, date)

        market_regime = str(vrow.get("market_regime_final", ""))
        allow_trade = str(vrow.get("allow_trade", "NO")) == "YES"
        cap = _regime_cap(market_regime)

        # 每日先刷新持仓市值。
        if not positions.empty:
            for idx, pos in positions[positions["status"] == "holding"].iterrows():
                latest = _close_price(pos["stock_code"], date)
                if latest is None:
                    latest = _safe_float(pos.get("latest_price"), _safe_float(pos.get("cost_price")))
                shares = _safe_int(pos.get("shares"))
                cost = _safe_float(pos.get("cost_price"))
                market_value = latest * shares
                pnl = (latest - cost) * shares
                pnl_pct = (latest / cost - 1) * 100 if cost else 0.0
                positions.at[idx, "date"] = date
                positions.at[idx, "latest_price"] = round(latest, 4)
                positions.at[idx, "market_value"] = round(market_value, 2)
                positions.at[idx, "floating_pnl"] = round(pnl, 2)
                positions.at[idx, "floating_pnl_pct"] = round(pnl_pct, 2)
                positions.at[idx, "holding_days"] = _holding_days(str(pos.get("buy_date")), date)

        current_market_value = float(pd.to_numeric(positions.loc[positions["status"] == "holding", "market_value"], errors="coerce").fillna(0).sum()) if not positions.empty else 0.0
        total_assets_before_trade = cash + current_market_value

        if not orders.empty:
            # 先处理卖出。
            for _, order in orders[orders["action"] == "SELL"].iterrows():
                code = str(order["stock_code"]).zfill(6)
                held = positions[(positions["stock_code"] == code) & (positions["status"] == "holding")]
                if held.empty:
                    continue
                price = _close_price(code, date)
                if price is None:
                    price = _safe_float(held.iloc[-1].get("latest_price"), _safe_float(held.iloc[-1].get("cost_price")))
                for pos_idx, pos in held.iterrows():
                    shares = _safe_int(pos.get("shares"))
                    amount = price * shares
                    cost_amount = _safe_float(pos.get("cost_price")) * shares
                    pnl = amount - cost_amount
                    pnl_pct = pnl / cost_amount * 100 if cost_amount else 0.0
                    cash += amount
                    positions.at[pos_idx, "status"] = "closed"
                    trades = pd.concat([trades, pd.DataFrame([{
                        "date": date,
                        "stock_code": code,
                        "name": pos.get("name", name_map.get(code, "")),
                        "action": "SELL",
                        "price": round(price, 4),
                        "shares": shares,
                        "amount": round(amount, 2),
                        "pnl": round(pnl, 2),
                        "pnl_pct": round(pnl_pct, 2),
                        "reason": order.get("reason", ""),
                    }])], ignore_index=True)

            # 再处理买入，严格服从允许交易和市场仓位上限。
            if allow_trade and cap > 0:
                current_market_value = float(pd.to_numeric(positions.loc[positions["status"] == "holding", "market_value"], errors="coerce").fillna(0).sum()) if not positions.empty else 0.0
                max_position_value = total_assets_before_trade * cap
                available_position_value = max(0.0, max_position_value - current_market_value)
                for _, order in orders[orders["action"] == "BUY"].sort_values("score", ascending=False).iterrows():
                    if available_position_value <= 0 or cash <= 0:
                        break
                    code = str(order["stock_code"]).zfill(6)
                    if not positions[(positions["stock_code"] == code) & (positions["status"] == "holding")].empty:
                        continue
                    price = _close_price(code, date)
                    if price is None or price <= 0:
                        continue
                    target_value = min(total_assets_before_trade * _safe_float(order.get("position_ratio")), available_position_value, cash)
                    shares = int(target_value // (price * 100)) * 100
                    if shares <= 0:
                        continue
                    amount = shares * price
                    cash -= amount
                    available_position_value -= amount
                    name = name_map.get(code, "")
                    positions = pd.concat([positions, pd.DataFrame([{
                        "date": date,
                        "stock_code": code,
                        "name": name,
                        "buy_date": date,
                        "cost_price": round(price, 4),
                        "shares": shares,
                        "latest_price": round(price, 4),
                        "market_value": round(amount, 2),
                        "floating_pnl": 0.0,
                        "floating_pnl_pct": 0.0,
                        "holding_days": 0,
                        "status": "holding",
                    }])], ignore_index=True)
                    trades = pd.concat([trades, pd.DataFrame([{
                        "date": date,
                        "stock_code": code,
                        "name": name,
                        "action": "BUY",
                        "price": round(price, 4),
                        "shares": shares,
                        "amount": round(amount, 2),
                        "pnl": 0.0,
                        "pnl_pct": 0.0,
                        "reason": order.get("reason", ""),
                    }])], ignore_index=True)

        # 交易后再次刷新当日权益。
        market_value = float(pd.to_numeric(positions.loc[positions["status"] == "holding", "market_value"], errors="coerce").fillna(0).sum()) if not positions.empty else 0.0
        total_assets = cash + market_value
        peak_assets = max(peak_assets, total_assets)
        daily_return = (total_assets / previous_assets - 1) * 100 if previous_assets else 0.0
        cumulative_return = (total_assets / INITIAL_CASH - 1) * 100
        max_drawdown = (total_assets / peak_assets - 1) * 100 if peak_assets else 0.0
        stats = _calc_stats(trades, pd.DataFrame(equity_rows, columns=EQUITY_COLUMNS))
        account_rows.append({
            "date": date,
            "initial_cash": INITIAL_CASH,
            "cash": round(cash, 2),
            "market_value": round(market_value, 2),
            "total_assets": round(total_assets, 2),
            "cumulative_return": round(cumulative_return, 2),
        })
        equity_rows.append({
            "date": date,
            "cash": round(cash, 2),
            "market_value": round(market_value, 2),
            "total_assets": round(total_assets, 2),
            "daily_return": round(daily_return, 2),
            "cumulative_return": round(cumulative_return, 2),
            "max_drawdown": round(max_drawdown, 2),
            "win_rate": stats["win_rate"],
            "profit_factor": stats["profit_factor"],
            "sharpe_ratio": stats["sharpe_ratio"],
        })
        previous_assets = total_assets

    if not account_rows:
        missing_text = "、".join(missing_frozen_dates) if missing_frozen_dates else "未知日期"
        raise FileNotFoundError(f"缺少冻结订单：{missing_text}。请先执行 decision_freeze.py 生成冻结订单后再运行 paper_trading.py。")

    account = pd.DataFrame(account_rows, columns=ACCOUNT_COLUMNS)
    equity = pd.DataFrame(equity_rows, columns=EQUITY_COLUMNS)
    stats = _calc_stats(trades, equity)
    if not equity.empty:
        equity.loc[equity.index[-1], "win_rate"] = stats["win_rate"]
        equity.loc[equity.index[-1], "profit_factor"] = stats["profit_factor"]
        equity.loc[equity.index[-1], "sharpe_ratio"] = stats["sharpe_ratio"]

    account.to_csv(account_path, index=False, encoding="utf-8-sig")
    positions.to_csv(positions_path, index=False, encoding="utf-8-sig")
    trades.to_csv(trades_path, index=False, encoding="utf-8-sig")
    equity.to_csv(equity_path, index=False, encoding="utf-8-sig")
    _write_report(report_path, account, positions, trades, equity)

    latest_total = _safe_float(account.iloc[-1]["total_assets"], INITIAL_CASH) if not account.empty else INITIAL_CASH
    latest_return = _safe_float(account.iloc[-1]["cumulative_return"]) if not account.empty else 0.0
    latest_drawdown = round(float(pd.to_numeric(equity.get("max_drawdown", pd.Series(dtype=float)), errors="coerce").min()), 2) if not equity.empty else 0.0
    return {
        "account_path": account_path,
        "positions_path": positions_path,
        "trades_path": trades_path,
        "equity_path": equity_path,
        "report_path": report_path,
        "total_assets": round(latest_total, 2),
        "cumulative_return": round(latest_return, 2),
        "max_drawdown": latest_drawdown,
        "win_rate": stats["win_rate"],
        "profit_factor": stats["profit_factor"],
        "sharpe_ratio": stats["sharpe_ratio"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 8 Paper Trading 虚拟账户")
    parser.add_argument("--max-days", type=int, default=10, help="最多处理最近N个验证日，默认10")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    project_root = Path(__file__).resolve().parent
    result = run_paper_trading(project_root, max_days=args.max_days)
    print("Paper Trading 虚拟账户已更新")
    print(f"账户文件：{result['account_path']}")
    print(f"持仓文件：{result['positions_path']}")
    print(f"交易文件：{result['trades_path']}")
    print(f"资金曲线：{result['equity_path']}")
    print(f"报告文件：{result['report_path']}")
    print(f"总资产：{result['total_assets']}")
    print(f"累计收益率：{result['cumulative_return']}%")
    print(f"最大回撤：{result['max_drawdown']}%")
    print(f"胜率：{result['win_rate']}%")
    print(f"盈亏比：{result['profit_factor']}")
    print(f"夏普比率：{result['sharpe_ratio']}")


if __name__ == "__main__":
    main()

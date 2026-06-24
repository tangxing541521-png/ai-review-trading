from __future__ import annotations

import argparse
import math
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

import akshare as ak
import numpy as np
import pandas as pd

from strategy.trend_core import _akshare_daily_symbol, _is_abnormal_name, _is_beijing_stock, _normalize_code


PROJECT_ROOT = Path(__file__).resolve().parent
REPORT_COLUMNS = ["date", "total_assets", "daily_return", "cumulative_return", "drawdown"]
TRADE_COLUMNS = [
    "buy_date",
    "sell_date",
    "code",
    "name",
    "buy_price",
    "sell_price",
    "shares",
    "pnl",
    "pnl_pct",
    "holding_days",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI复盘交易历史回测")
    parser.add_argument("--start", default="2026-04-01", help="开始日期，格式 YYYY-MM-DD 或 YYYYMMDD")
    parser.add_argument("--end", default="2026-06-22", help="结束日期，格式 YYYY-MM-DD 或 YYYYMMDD")
    parser.add_argument("--days", type=int, default=60, help="输出最近 N 个交易日统计，默认 60")
    parser.add_argument(
        "--universe",
        choices=["cache", "all", "historical"],
        default="cache",
        help="股票池来源：cache 使用本地缓存，all 使用当前全市场代码列表，historical 使用历史股票池缓存",
    )
    parser.add_argument("--max-workers", type=int, default=6, help="并发进程数量")
    return parser.parse_args()


def parse_date(value: str) -> str:
    text = value.replace("-", "")
    datetime.strptime(text, "%Y%m%d")
    return text


def load_config() -> Dict:
    config_path = PROJECT_ROOT / "config" / "config.yaml"
    config: Dict[str, object] = {}
    for line in config_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip()
        if value.replace(".", "", 1).isdigit():
            config[key.strip()] = float(value) if "." in value else int(value)
        else:
            config[key.strip()] = value
    return config


def safe_float(value, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def load_universe(source: str) -> pd.DataFrame:
    """加载股票池；默认用本地缓存，避免每次回测都重新拉全市场列表。"""
    if source == "cache":
        cached_files = sorted((PROJECT_ROOT / "data" / "raw").glob("daily_quotes_*.csv"), reverse=True)
        if cached_files:
            df = pd.read_csv(cached_files[0], dtype={"code": str})
            df = df[["code", "name"]].drop_duplicates("code")
            df["code"] = df["code"].map(_normalize_code)
            df["name"] = df["name"].astype(str)
            return df[(~df["code"].map(_is_beijing_stock)) & (~df["name"].map(_is_abnormal_name))]

    records = []
    try:
        sh_df = ak.stock_info_sh_name_code().rename(columns={"证券代码": "code", "证券简称": "name"})
        records.append(sh_df[["code", "name"]])
    except Exception as exc:
        print(f"获取沪市股票列表失败：{exc}")

    try:
        sz_df = ak.stock_info_sz_name_code().rename(columns={"A股代码": "code", "A股简称": "name"})
        records.append(sz_df[["code", "name"]])
    except Exception as exc:
        print(f"获取深市股票列表失败：{exc}")

    if not records:
        raise RuntimeError("股票列表获取失败，无法回测。")

    universe = pd.concat(records, ignore_index=True).drop_duplicates("code")
    universe["code"] = universe["code"].map(_normalize_code)
    universe["name"] = universe["name"].astype(str)
    return universe[(~universe["code"].map(_is_beijing_stock)) & (~universe["name"].map(_is_abnormal_name))]


def fetch_history_worker(item: tuple[str, str], start_date: str, end_date: str) -> list[dict]:
    """子进程拉取单只股票历史日线，返回普通 dict，避免 Windows 序列化问题。"""
    code, name = item
    try:
        hist = ak.stock_zh_a_daily(
            symbol=_akshare_daily_symbol(code),
            start_date=start_date,
            end_date=end_date,
            adjust="",
        )
    except Exception:
        try:
            hist = ak.stock_zh_a_hist(symbol=code, period="daily", start_date=start_date, end_date=end_date, adjust="")
        except Exception:
            return []

    if hist is None or hist.empty:
        return []

    hist = hist.rename(columns={"日期": "date", "收盘": "close", "涨跌幅": "pct_chg", "成交额": "amount", "换手率": "turnover"})
    for col in ["date", "open", "close", "pct_chg", "amount", "turnover"]:
        if col not in hist.columns:
            hist[col] = np.nan

    hist["date"] = pd.to_datetime(hist["date"], errors="coerce")
    hist = hist.dropna(subset=["date"]).sort_values("date")
    hist["code"] = code
    hist["name"] = name
    return hist[["date", "code", "name", "open", "close", "pct_chg", "amount", "turnover"]].to_dict("records")


def load_histories(universe: pd.DataFrame, start_date: str, end_date: str, max_workers: int) -> pd.DataFrame:
    """并发加载历史日线。"""
    fetch_start = (datetime.strptime(start_date, "%Y%m%d") - timedelta(days=450)).strftime("%Y%m%d")
    items = [(str(row["code"]), str(row["name"])) for _, row in universe.iterrows()]
    records: List[dict] = []
    print(f"开始加载历史日线，股票数量：{len(items)}")

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(fetch_history_worker, item, fetch_start, end_date) for item in items]
        for idx, future in enumerate(as_completed(futures), start=1):
            try:
                records.extend(future.result())
            except Exception as exc:
                print(f"历史日线加载异常：{exc}")
            if idx % 100 == 0:
                print(f"历史日线加载进度：{idx}/{len(items)}")

    if not records:
        raise RuntimeError("历史日线为空，无法回测。")

    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for col in ["open", "close", "pct_chg", "amount", "turnover"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["date", "code", "close"]).sort_values(["code", "date"])


def load_historical_market_histories(start_date: str, end_date: str) -> pd.DataFrame:
    """读取 market_universe_builder.py 构建的历史股票池行情缓存。"""
    path = PROJECT_ROOT / "data" / "processed" / f"market_histories_{start_date}_{end_date}.csv"
    if not path.exists():
        raise RuntimeError(
            "历史股票池缓存不存在，请先运行："
            f"python market_universe_builder.py --start {start_date} --end {end_date}"
        )

    df = pd.read_csv(path, dtype={"code": str})
    if df.empty:
        raise RuntimeError(f"历史股票池缓存为空：{path}")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for col in ["open", "close", "pct_chg", "amount", "turnover"]:
        if col not in df.columns:
            df[col] = np.nan
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["code"] = df["code"].astype(str).str.zfill(6)
    return df.dropna(subset=["date", "code", "close"]).sort_values(["code", "date"])


def add_indicators(histories: pd.DataFrame) -> pd.DataFrame:
    """计算趋势核心池需要的历史指标。"""
    frames = []
    for _, group in histories.groupby("code", sort=False):
        g = group.sort_values("date").copy()
        g["pct_chg"] = g["pct_chg"].fillna(g["close"].pct_change() * 100)
        g["ma5"] = g["close"].rolling(5).mean()
        g["ma10"] = g["close"].rolling(10).mean()
        g["ma20"] = g["close"].rolling(20).mean()
        g["pct_5d"] = (g["close"] / g["close"].shift(5) - 1) * 100
        g["pct_10d"] = (g["close"] / g["close"].shift(10) - 1) * 100
        g["pct_20d"] = (g["close"] / g["close"].shift(20) - 1) * 100
        high_20d = g["close"].rolling(20).max()
        g["distance_to_20d_high"] = (high_20d / g["close"] - 1) * 100
        high_52w = g["close"].rolling(252, min_periods=20).max()
        g["distance_to_52w_high"] = (high_52w / g["close"] - 1) * 100
        g["volatility_20d"] = g["close"].pct_change().rolling(20).std() * 100
        amount_mean_20d = g["amount"].rolling(20).mean()
        g["amount_cv_20d"] = g["amount"].rolling(20).std() / amount_mean_20d
        trend_flags = (g["close"] > g["ma5"]) & (g["ma5"] > g["ma10"]) & (g["ma10"] > g["ma20"])
        trend_days = []
        count = 0
        for flag in trend_flags.fillna(False):
            count = count + 1 if flag else 0
            trend_days.append(count)
        g["trend_days"] = trend_days
        frames.append(g)
    return pd.concat(frames, ignore_index=True)


def rank_score(series: pd.Series, min_score: float, max_score: float, higher_better: bool = True) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    valid_count = values.notna().sum()
    if valid_count <= 1:
        return pd.Series(max_score, index=series.index)
    ranked = values.rank(method="average", ascending=True if higher_better else False)
    percentile = ((ranked - 1) / (valid_count - 1)).fillna(0)
    return min_score + percentile * (max_score - min_score)


def amount_rank_score(amount: pd.Series) -> pd.Series:
    values = pd.to_numeric(amount, errors="coerce")
    valid_count = values.notna().sum()
    if valid_count <= 1:
        return pd.Series(20.0, index=amount.index)
    ranked = values.rank(method="average", ascending=True)
    percentile = ((ranked - 1) / (valid_count - 1)).fillna(0)
    return pd.Series(
        np.select(
            [percentile >= 0.90, percentile >= 0.70, percentile >= 0.50],
            [20.0, 15.0, 10.0],
            default=5.0,
        ),
        index=amount.index,
    )


def blend_score(*parts: tuple[pd.Series, float]) -> pd.Series:
    total = None
    for score, weight in parts:
        weighted = pd.to_numeric(score, errors="coerce").fillna(30) * weight
        total = weighted if total is None else total + weighted
    return total.clip(30, 100).round(2)


def score_rows(df: pd.DataFrame) -> pd.DataFrame:
    """按单日市场样本计算双模型 weighted rank score。"""
    result = df.copy()
    result["amount_rank_component"] = rank_score(result["amount"], 30.0, 100.0, higher_better=True)
    result["acceleration_5_10"] = result["pct_5d"] - result["pct_10d"] / 2
    result["acceleration_component"] = rank_score(result["acceleration_5_10"], 30.0, 100.0, higher_better=True)
    result["near_high_component"] = rank_score(-result["distance_to_52w_high"], 30.0, 100.0, higher_better=True)
    result["volatility_component"] = rank_score(result["volatility_20d"], 30.0, 100.0, higher_better=True)
    result["turnover_component"] = rank_score(result["turnover"], 30.0, 100.0, higher_better=True)
    result["vol_turn_component"] = ((result["volatility_component"] + result["turnover_component"]) / 2).round(2)
    result["trend_strength"] = result["pct_5d"] * 0.30 + result["pct_10d"] * 0.30 + result["pct_20d"] * 0.40
    result["ma_strength"] = (
        (result["close"] / result["ma5"] - 1) * 100
        + (result["ma5"] / result["ma10"] - 1) * 100
        + (result["ma10"] / result["ma20"] - 1) * 100
    )
    result["ma_component"] = rank_score(result["ma_strength"], 30.0, 100.0, higher_better=True)
    result["drawdown_component"] = rank_score(-result["distance_to_52w_high"], 30.0, 100.0, higher_better=True)
    result["trend_days_component"] = rank_score(result["trend_days"], 30.0, 100.0, higher_better=True)
    result["amount_stability_component"] = rank_score(-result["amount_cv_20d"], 30.0, 100.0, higher_better=True)
    result["momentum_score"] = blend_score(
        (result["amount_rank_component"], 0.30),
        (result["acceleration_component"], 0.30),
        (result["near_high_component"], 0.20),
        (result["vol_turn_component"], 0.20),
    )
    result["trend_score"] = blend_score(
        (result["ma_component"], 0.30),
        (result["drawdown_component"], 0.30),
        (result["trend_days_component"], 0.20),
        (result["amount_stability_component"], 0.20),
    )
    result["combined_score"] = (
        np.maximum(result["momentum_score"], result["trend_score"]) * 0.60
        + np.minimum(result["momentum_score"], result["trend_score"]) * 0.40
    ).round(2)
    return result


def build_daily_pools(indicators: pd.DataFrame, min_amount: float) -> dict[str, pd.DataFrame]:
    """按信号日生成趋势核心池。"""
    df = indicators.copy()
    big_bear = (df["open"] > 0) & (df["close"] < df["open"] * 0.97) & (df["pct_chg"] < -3)
    mask = (
        (df["amount"] > min_amount)
        & (df["pct_5d"] > 5)
        & (df["pct_10d"] > 10)
        & (df["pct_20d"] > 15)
        & (df["close"] > df["ma5"])
        & (df["ma5"] > df["ma10"])
        & (df["ma10"] > df["ma20"])
        & (df["distance_to_20d_high"] <= 10)
        & (df["pct_5d"] <= 35)
        & (~big_bear)
    )
    filtered = df[mask].copy()
    pools: dict[str, pd.DataFrame] = {}
    for date, group in filtered.groupby(filtered["date"].dt.strftime("%Y%m%d")):
        day_base = df[df["date"].dt.strftime("%Y%m%d") == date]
        day_scores = score_rows(day_base)
        score_cols = ["code", "momentum_score", "trend_score", "combined_score"]
        pool = group.drop(columns=[col for col in score_cols if col in group.columns], errors="ignore").merge(day_scores[score_cols], on="code", how="left")
        pool = pool.sort_values(["combined_score", "amount"], ascending=False).head(100).reset_index(drop=True)
        pools[date] = pool
    return pools


def get_price(price_map: dict[tuple[str, str], float], date: str, code: str) -> float | None:
    price = price_map.get((date, code))
    if price is None or pd.isna(price) or price <= 0:
        return None
    return float(price)


def run_backtest(start_date: str, end_date: str, universe_source: str, max_workers: int) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    config = load_config()
    initial_cash = float(config.get("initial_cash", 100000))
    buy_top_n = int(config.get("buy_top_n", 5))
    buy_lot = int(config.get("buy_lot", 100))
    min_amount = float(config.get("min_amount", 1_000_000_000))

    if universe_source == "historical":
        raw_histories = load_historical_market_histories(start_date, end_date)
    else:
        universe = load_universe(universe_source)
        raw_histories = load_histories(universe, start_date, end_date, max_workers)
    histories = add_indicators(raw_histories)
    pools = build_daily_pools(histories, min_amount)
    price_map = {
        (row["date"].strftime("%Y%m%d"), row["code"]): safe_float(row["close"])
        for _, row in histories.iterrows()
    }

    trading_dates = sorted(histories[(histories["date"].dt.strftime("%Y%m%d") >= start_date) & (histories["date"].dt.strftime("%Y%m%d") <= end_date)]["date"].dt.strftime("%Y%m%d").unique())
    cash = initial_cash
    positions: dict[str, dict] = {}
    equity_rows: list[dict] = []
    trades: list[dict] = []

    for idx in range(len(trading_dates) - 1):
        signal_date = trading_dates[idx]
        exec_date = trading_dates[idx + 1]
        pool = pools.get(signal_date, pd.DataFrame())
        pool_codes = set(pool["code"].tolist()) if not pool.empty else set()

        for code in list(positions.keys()):
            pos = positions[code]
            if code in pool_codes:
                pos["miss_count"] = 0
                continue

            pos["miss_count"] = int(pos.get("miss_count", 0)) + 1
            if pos["miss_count"] < 2:
                continue

            pos = positions.pop(code)
            sell_price = get_price(price_map, exec_date, code)
            if sell_price is None:
                positions[code] = pos
                continue
            amount = sell_price * pos["shares"]
            pnl = (sell_price - pos["buy_price"]) * pos["shares"]
            pnl_pct = (sell_price / pos["buy_price"] - 1) * 100 if pos["buy_price"] else 0.0
            cash += amount
            trades.append(
                {
                    "buy_date": pos["buy_date"],
                    "sell_date": exec_date,
                    "code": code,
                    "name": pos["name"],
                    "buy_price": round(pos["buy_price"], 2),
                    "sell_price": round(sell_price, 2),
                    "shares": pos["shares"],
                    "pnl": round(pnl, 2),
                    "pnl_pct": round(pnl_pct, 2),
                    "holding_days": max(1, trading_dates.index(exec_date) - trading_dates.index(pos["buy_date"])),
                }
            )

        if not pool.empty:
            for _, item in pool.head(buy_top_n).iterrows():
                code = str(item["code"])
                if code in positions:
                    continue
                buy_price = get_price(price_map, exec_date, code)
                if buy_price is None:
                    continue
                amount = buy_price * buy_lot
                if cash < amount:
                    continue
                cash -= amount
                positions[code] = {
                    "name": item["name"],
                    "buy_date": exec_date,
                    "buy_price": buy_price,
                    "shares": buy_lot,
                    "miss_count": 0,
                }

        market_value = 0.0
        for code, pos in positions.items():
            latest_price = get_price(price_map, exec_date, code)
            if latest_price is None:
                latest_price = pos["buy_price"]
            market_value += latest_price * pos["shares"]

        total_assets = cash + market_value
        previous_assets = equity_rows[-1]["total_assets"] if equity_rows else initial_cash
        daily_return = (total_assets / previous_assets - 1) * 100 if previous_assets else 0.0
        cumulative_return = (total_assets / initial_cash - 1) * 100 if initial_cash else 0.0
        equity_rows.append(
            {
                "date": exec_date,
                "total_assets": round(total_assets, 2),
                "daily_return": round(daily_return, 4),
                "cumulative_return": round(cumulative_return, 4),
                "holding_count": len(positions),
            }
        )

    equity = pd.DataFrame(equity_rows)
    if not equity.empty:
        running_max = equity["total_assets"].cummax()
        equity["drawdown"] = ((equity["total_assets"] / running_max - 1) * 100).round(4)
    else:
        equity = pd.DataFrame(columns=[*REPORT_COLUMNS, "holding_count"])

    trade_df = pd.DataFrame(trades, columns=TRADE_COLUMNS)
    metrics = calculate_metrics(equity, trade_df, initial_cash)
    return equity, trade_df, metrics


def calculate_metrics(equity: pd.DataFrame, trades: pd.DataFrame, initial_cash: float) -> dict:
    if equity.empty:
        return {}

    total_return = (equity.iloc[-1]["total_assets"] / initial_cash - 1) * 100
    periods = max(1, len(equity))
    annual_return = ((equity.iloc[-1]["total_assets"] / initial_cash) ** (252 / periods) - 1) * 100
    max_drawdown = float(equity["drawdown"].min())
    daily_returns = pd.to_numeric(equity["daily_return"], errors="coerce").fillna(0) / 100
    sharpe = math.sqrt(252) * daily_returns.mean() / daily_returns.std() if daily_returns.std() else 0.0

    if trades.empty:
        win_rate = avg_return = best = worst = avg_hold = profit_factor = 0.0
    else:
        pnl = pd.to_numeric(trades["pnl"], errors="coerce").fillna(0)
        pnl_pct = pd.to_numeric(trades["pnl_pct"], errors="coerce").fillna(0)
        wins = pnl[pnl > 0]
        losses = pnl[pnl <= 0]
        win_rate = len(wins) / len(pnl) * 100 if len(pnl) else 0.0
        avg_return = float(pnl_pct.mean()) if len(pnl_pct) else 0.0
        best = float(pnl_pct.max()) if len(pnl_pct) else 0.0
        worst = float(pnl_pct.min()) if len(pnl_pct) else 0.0
        avg_hold = float(pd.to_numeric(trades["holding_days"], errors="coerce").fillna(0).mean())
        profit_factor = float(wins.sum() / abs(losses.sum())) if abs(losses.sum()) > 0 else (float("inf") if wins.sum() > 0 else 0.0)

    return {
        "total_return": round(float(total_return), 2),
        "annual_return": round(float(annual_return), 2),
        "max_drawdown": round(max_drawdown, 2),
        "win_rate": round(win_rate, 2),
        "avg_return": round(avg_return, 2),
        "best_trade": round(best, 2),
        "worst_trade": round(worst, 2),
        "avg_holding_days": round(avg_hold, 2),
        "avg_holding_count": round(float(equity["holding_count"].mean()), 2) if "holding_count" in equity.columns else 0.0,
        "profit_factor": round(profit_factor, 2) if math.isfinite(profit_factor) else "inf",
        "sharpe": round(float(sharpe), 2),
        "trade_count": int(len(trades)),
    }


def write_reports(equity: pd.DataFrame, trades: pd.DataFrame, metrics: dict, start_date: str, end_date: str) -> None:
    csv_path = PROJECT_ROOT / "backtest_report.csv"
    md_path = PROJECT_ROOT / "backtest_report.md"
    trades_path = PROJECT_ROOT / "backtest_trades.csv"

    equity[REPORT_COLUMNS].to_csv(csv_path, index=False, encoding="utf-8-sig")
    trades.to_csv(trades_path, index=False, encoding="utf-8-sig")

    content = f"""# 历史回测报告

回测区间：{start_date} 至 {end_date}

## 核心指标
- 总收益率：{metrics.get('total_return', 0)}%
- 年化收益率：{metrics.get('annual_return', 0)}%
- 最大回撤：{metrics.get('max_drawdown', 0)}%
- 胜率：{metrics.get('win_rate', 0)}%
- 平均收益率：{metrics.get('avg_return', 0)}%
- 最大盈利：{metrics.get('best_trade', 0)}%
- 最大亏损：{metrics.get('worst_trade', 0)}%
- 平均持仓天数：{metrics.get('avg_holding_days', 0)}
- 平均持仓数量：{metrics.get('avg_holding_count', 0)}
- 盈利因子：{metrics.get('profit_factor', 0)}
- 夏普比率：{metrics.get('sharpe', 0)}
- 完成交易数：{metrics.get('trade_count', 0)}

## 回测规则
- 信号日只使用当日及以前日线数据。
- 买入和卖出都使用下一交易日收盘价。
- 当前为模拟盘回测，不含手续费、滑点、涨跌停无法成交等真实约束。
"""
    md_path.write_text(content, encoding="utf-8")
    print(f"回测资金曲线：{csv_path}")
    print(f"回测交易明细：{trades_path}")
    print(f"回测报告：{md_path}")


def main() -> None:
    args = parse_args()
    start_date = parse_date(args.start)
    end_date = parse_date(args.end)
    equity, trades, metrics = run_backtest(start_date, end_date, args.universe, args.max_workers)

    if args.days and not equity.empty:
        equity = equity.tail(args.days).reset_index(drop=True)
        metrics = calculate_metrics(equity, trades[trades["sell_date"].isin(set(equity["date"]))] if not trades.empty else trades, float(load_config().get("initial_cash", 100000)))

    write_reports(equity, trades, metrics, start_date, end_date)
    print(f"总收益率：{metrics.get('total_return', 0)}%")
    print(f"最大回撤：{metrics.get('max_drawdown', 0)}%")
    print(f"胜率：{metrics.get('win_rate', 0)}%")
    print(f"盈利因子：{metrics.get('profit_factor', 0)}")
    print(f"夏普比率：{metrics.get('sharpe', 0)}")


if __name__ == "__main__":
    main()

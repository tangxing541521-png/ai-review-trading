from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from backtest import add_indicators, calculate_metrics, get_price, load_config, load_histories, load_universe, parse_date, score_rows


PROJECT_ROOT = Path(__file__).resolve().parent
REPORT_PATH = PROJECT_ROOT / "stability_experiment.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="趋势池稳定性实验")
    parser.add_argument("--start", default="2026-04-01", help="开始日期，格式 YYYY-MM-DD 或 YYYYMMDD")
    parser.add_argument("--end", default="2026-06-22", help="结束日期，格式 YYYY-MM-DD 或 YYYYMMDD")
    parser.add_argument("--days", type=int, default=60, help="分析最近 N 个交易日，默认 60")
    parser.add_argument("--universe", choices=["cache", "all"], default="cache", help="股票池来源")
    parser.add_argument("--max-workers", type=int, default=6, help="并发进程数量")
    return parser.parse_args()


def pct(value: float) -> str:
    return f"{value:.2f}%"


def markdown_table(df: pd.DataFrame, columns: list[str]) -> str:
    if df.empty:
        return "暂无数据"
    view = df[columns].copy().fillna("")
    rows = [[str(value) for value in row] for row in view.to_numpy().tolist()]
    widths = [max(len(str(col)), *(len(row[i]) for row in rows)) for i, col in enumerate(columns)]
    header = "| " + " | ".join(str(col).ljust(widths[i]) for i, col in enumerate(columns)) + " |"
    separator = "| " + " | ".join("-" * widths[i] for i in range(len(columns))) + " |"
    body = ["| " + " | ".join(row[i].ljust(widths[i]) for i in range(len(columns))) + " |" for row in rows]
    return "\n".join([header, separator, *body])


def base_condition(df: pd.DataFrame, min_amount: float, require_today_positive: bool) -> pd.Series:
    """生成基础条件，B 实验会取消今日涨幅必须大于 0。"""
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
    if require_today_positive:
        mask = mask & (df["pct_chg"] > 0)
    return mask


def build_raw_pools(indicators: pd.DataFrame, min_amount: float, require_today_positive: bool, top_n: int) -> dict[str, pd.DataFrame]:
    scored = score_rows(indicators)
    filtered = scored[base_condition(scored, min_amount, require_today_positive)].copy()
    pools = {}
    for date, group in filtered.groupby(filtered["date"].dt.strftime("%Y%m%d")):
        pool = group.sort_values(["trend_score", "amount"], ascending=False).head(top_n).reset_index(drop=True)
        pool["rank"] = pool.index + 1
        pools[date] = pool
    return pools


def apply_consecutive_entry(raw_pools: dict[str, pd.DataFrame], dates: list[str]) -> dict[str, pd.DataFrame]:
    """连续2天满足条件才允许进入趋势池。"""
    result = {}
    previous_codes: set[str] = set()
    for date in dates:
        pool = raw_pools.get(date, pd.DataFrame())
        if pool.empty:
            result[date] = pool
            previous_codes = set()
            continue
        codes = set(pool["code"].astype(str).tolist())
        allowed = codes & previous_codes
        result[date] = pool[pool["code"].astype(str).isin(allowed)].reset_index(drop=True)
        if not result[date].empty:
            result[date]["rank"] = result[date].index + 1
        previous_codes = codes
    return result


def apply_consecutive_exit(raw_pools: dict[str, pd.DataFrame], dates: list[str]) -> dict[str, pd.DataFrame]:
    """连续2天不满足条件才移出趋势池。"""
    result = {}
    stable_codes: set[str] = set()
    miss_count: dict[str, int] = {}
    last_rows: dict[str, pd.Series] = {}

    for date in dates:
        raw_pool = raw_pools.get(date, pd.DataFrame())
        raw_codes = set(raw_pool["code"].astype(str).tolist()) if not raw_pool.empty else set()
        for _, row in raw_pool.iterrows():
            code = str(row["code"])
            stable_codes.add(code)
            miss_count[code] = 0
            last_rows[code] = row

        for code in list(stable_codes):
            if code not in raw_codes:
                miss_count[code] = miss_count.get(code, 0) + 1
                if miss_count[code] >= 2:
                    stable_codes.remove(code)
                    last_rows.pop(code, None)
                    miss_count.pop(code, None)

        rows = [last_rows[code] for code in stable_codes if code in last_rows]
        if rows:
            pool = pd.DataFrame(rows).sort_values(["trend_score", "amount"], ascending=False).head(100).reset_index(drop=True)
            pool["rank"] = pool.index + 1
            result[date] = pool
        else:
            result[date] = pd.DataFrame()
    return result


def avg_in_pool_days(pools: dict[str, pd.DataFrame], dates: list[str]) -> float:
    """计算每个连续入池段的平均天数。"""
    presence: dict[str, list[int]] = {}
    for idx, date in enumerate(dates):
        pool = pools.get(date, pd.DataFrame())
        if pool.empty:
            continue
        for code in pool["code"].astype(str).tolist():
            presence.setdefault(code, []).append(idx)

    streaks = []
    for indexes in presence.values():
        if not indexes:
            continue
        length = 1
        for prev, current in zip(indexes, indexes[1:]):
            if current == prev + 1:
                length += 1
            else:
                streaks.append(length)
                length = 1
        streaks.append(length)
    return round(float(np.mean(streaks)), 2) if streaks else 0.0


def run_pool_backtest(
    pools: dict[str, pd.DataFrame],
    histories: pd.DataFrame,
    dates: list[str],
    initial_cash: float,
    buy_top_n: int,
    buy_lot: int,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    price_map = {
        (row["date"].strftime("%Y%m%d"), row["code"]): float(row["close"])
        for _, row in histories.iterrows()
        if not pd.isna(row["close"])
    }
    cash = initial_cash
    positions: dict[str, dict] = {}
    equity_rows = []
    trades = []

    for idx in range(len(dates) - 1):
        signal_date = dates[idx]
        exec_date = dates[idx + 1]
        pool = pools.get(signal_date, pd.DataFrame())
        pool_codes = set(pool["code"].astype(str).tolist()) if not pool.empty else set()

        for code in list(positions.keys()):
            if code not in pool_codes:
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
                        "holding_days": max(1, dates.index(exec_date) - dates.index(pos["buy_date"])),
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
                }

        market_value = 0.0
        for code, pos in positions.items():
            latest_price = get_price(price_map, exec_date, code) or pos["buy_price"]
            market_value += latest_price * pos["shares"]
        total_assets = cash + market_value
        previous_assets = equity_rows[-1]["total_assets"] if equity_rows else initial_cash
        daily_return = (total_assets / previous_assets - 1) * 100 if previous_assets else 0.0
        equity_rows.append(
            {
                "date": exec_date,
                "total_assets": round(total_assets, 2),
                "daily_return": round(daily_return, 4),
                "cumulative_return": round((total_assets / initial_cash - 1) * 100, 4),
                "holding_count": len(positions),
            }
        )

    equity = pd.DataFrame(equity_rows)
    if equity.empty:
        equity = pd.DataFrame(columns=["date", "total_assets", "daily_return", "cumulative_return", "holding_count", "drawdown"])
    else:
        equity["drawdown"] = ((equity["total_assets"] / equity["total_assets"].cummax() - 1) * 100).round(4)
    trades_df = pd.DataFrame(trades)
    metrics = calculate_metrics(equity, trades_df, initial_cash)
    return equity, trades_df, metrics


def recommend(results: pd.DataFrame) -> str:
    if results.empty:
        return "数据不足，无法给出推荐。"
    ranked = results.copy()
    ranked["收益回撤比数值"] = ranked["收益回撤比"].replace("inf", np.inf).astype(float)
    best = ranked.sort_values(["收益回撤比数值", "总收益"], ascending=False).iloc[0]
    stability_best = ranked.sort_values(["平均在池天数", "收益回撤比数值"], ascending=False).iloc[0]
    lines = [
        f"推荐优先验证：{best['实验名称']}。它在本次实验中的收益回撤比最高，为 {best['收益回撤比']}。",
        f"如果首要目标是降低趋势池敏感度，则重点看 {stability_best['实验名称']}，其平均在池天数为 {stability_best['平均在池天数']} 天。",
        "正式改策略前，应继续用全市场股票池、手续费滑点、涨跌停不可成交约束复验。当前实验只回答稳定性方向，不等于最终实盘规则。",
    ]
    return "\n\n".join(lines)


def main() -> None:
    args = parse_args()
    start_date = parse_date(args.start)
    end_date = parse_date(args.end)
    config = load_config()
    initial_cash = float(config.get("initial_cash", 100000))
    buy_top_n = int(config.get("buy_top_n", 5))
    buy_lot = int(config.get("buy_lot", 100))
    min_amount = float(config.get("min_amount", 1_000_000_000))

    universe = load_universe(args.universe)
    histories = load_histories(universe, start_date, end_date, args.max_workers)
    indicators = add_indicators(histories)
    all_dates = sorted(
        indicators[
            (indicators["date"].dt.strftime("%Y%m%d") >= start_date)
            & (indicators["date"].dt.strftime("%Y%m%d") <= end_date)
        ]["date"].dt.strftime("%Y%m%d").unique()
    )
    dates = all_dates[-args.days :] if args.days else all_dates

    raw_a = build_raw_pools(indicators, min_amount, require_today_positive=True, top_n=100)
    raw_b = build_raw_pools(indicators, min_amount, require_today_positive=False, top_n=100)

    experiments = {
        "A 当前版本": raw_a,
        "B 取消今日涨幅>0": raw_b,
        "C 连续2天入池": apply_consecutive_entry(raw_a, dates),
        "D 连续2天出池": apply_consecutive_exit(raw_a, dates),
        "E Top50": build_raw_pools(indicators, min_amount, require_today_positive=True, top_n=50),
    }

    rows = []
    for name, pools in experiments.items():
        print(f"开始实验：{name}")
        equity, trades, metrics = run_pool_backtest(pools, histories, dates, initial_cash, buy_top_n, buy_lot)
        total_return = float(metrics.get("total_return", 0))
        max_drawdown = float(metrics.get("max_drawdown", 0))
        ratio = total_return / abs(max_drawdown) if max_drawdown else 0.0
        rows.append(
            {
                "实验名称": name,
                "总收益": round(total_return, 2),
                "最大回撤": round(max_drawdown, 2),
                "胜率": round(float(metrics.get("win_rate", 0)), 2),
                "平均持仓天数": round(float(metrics.get("avg_holding_days", 0)), 2),
                "平均在池天数": avg_in_pool_days(pools, dates),
                "收益回撤比": round(ratio, 2),
            }
        )

    result = pd.DataFrame(rows)
    content = f"""# 趋势池稳定性实验

实验区间：{dates[0]} 至 {dates[-1]}

## 实验说明

- A 当前版本：今日涨幅 > 0
- B：取消今日涨幅 > 0，保留近5日涨幅 > 5%
- C：连续2天满足条件才允许进入趋势池
- D：连续2天不满足条件才移出趋势池
- E：趋势池 Top100 改 Top50

## 实验结果

{markdown_table(result, ['实验名称', '总收益', '最大回撤', '胜率', '平均持仓天数', '平均在池天数', '收益回撤比'])}

## 推荐方案

{recommend(result)}
"""
    REPORT_PATH.write_text(content, encoding="utf-8")
    print(f"趋势池稳定性实验报告已生成：{REPORT_PATH}")
    print(result.to_string(index=False))


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from backtest import add_indicators, build_daily_pools, load_config, load_histories, load_universe, parse_date


PROJECT_ROOT = Path(__file__).resolve().parent
REPORT_PATH = PROJECT_ROOT / "reports" / "pool_analysis.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="趋势池稳定性分析")
    parser.add_argument("--start", default="2026-04-01", help="开始日期，格式 YYYY-MM-DD 或 YYYYMMDD")
    parser.add_argument("--end", default="2026-06-22", help="结束日期，格式 YYYY-MM-DD 或 YYYYMMDD")
    parser.add_argument("--days", type=int, default=60, help="分析最近 N 个交易日，默认 60")
    parser.add_argument("--universe", choices=["cache", "all"], default="cache", help="股票池来源")
    parser.add_argument("--max-workers", type=int, default=6, help="并发进程数量")
    return parser.parse_args()


def pct(value: float) -> str:
    return f"{value:.2f}%"


def markdown_table(df: pd.DataFrame, columns: list[str], max_rows: int | None = None) -> str:
    if df.empty:
        return "暂无数据"
    view = df[columns].copy()
    if max_rows:
        view = view.head(max_rows)
    view = view.fillna("")
    rows = [[str(value) for value in row] for row in view.to_numpy().tolist()]
    widths = [max(len(str(col)), *(len(row[i]) for row in rows)) for i, col in enumerate(columns)]
    header = "| " + " | ".join(str(col).ljust(widths[i]) for i, col in enumerate(columns)) + " |"
    separator = "| " + " | ".join("-" * widths[i] for i in range(len(columns))) + " |"
    body = ["| " + " | ".join(row[i].ljust(widths[i]) for i in range(len(columns))) + " |" for row in rows]
    return "\n".join([header, separator, *body])


def build_presence(pools: dict[str, pd.DataFrame], dates: list[str]) -> pd.DataFrame:
    rows = []
    for date in dates:
        pool = pools.get(date, pd.DataFrame())
        if pool.empty:
            continue
        for _, item in pool.iterrows():
            rows.append(
                {
                    "date": date,
                    "code": str(item["code"]).zfill(6),
                    "name": item["name"],
                    "rank": int(item.get("rank", 0)) if "rank" in item else 0,
                    "trend_score": round(float(item.get("trend_score", 0)), 2),
                }
            )
    return pd.DataFrame(rows)


def streaks_for_stock(stock_rows: pd.DataFrame, date_index: dict[str, int]) -> list[dict]:
    sorted_rows = stock_rows.sort_values("date")
    dates = sorted_rows["date"].tolist()
    if not dates:
        return []

    streaks = []
    start = dates[0]
    end = dates[0]
    length = 1
    previous_idx = date_index[start]

    for date in dates[1:]:
        idx = date_index[date]
        if idx == previous_idx + 1:
            end = date
            length += 1
        else:
            streaks.append({"start_date": start, "end_date": end, "days": length})
            start = date
            end = date
            length = 1
        previous_idx = idx

    streaks.append({"start_date": start, "end_date": end, "days": length})
    return streaks


def analyze_stability(presence: pd.DataFrame, dates: list[str]) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    date_index = {date: idx for idx, date in enumerate(dates)}
    rows = []
    all_streak_rows = []

    for (code, name), group in presence.groupby(["code", "name"], sort=False):
        streaks = streaks_for_stock(group, date_index)
        entry_count = len(streaks)
        in_pool_days = len(group)
        streak_lengths = [item["days"] for item in streaks]
        removed_next_day = sum(1 for item in streaks if item["days"] == 1 and item["end_date"] != dates[-1])
        removed_within_3 = sum(1 for item in streaks if item["days"] <= 3 and item["end_date"] != dates[-1])
        rows.append(
            {
                "code": code,
                "name": name,
                "入池次数": entry_count,
                "在池总天数": in_pool_days,
                "平均在池天数": round(float(np.mean(streak_lengths)), 2) if streak_lengths else 0,
                "最长在池天数": max(streak_lengths) if streak_lengths else 0,
                "最短在池天数": min(streak_lengths) if streak_lengths else 0,
                "次日剔除次数": removed_next_day,
                "3日内剔除次数": removed_within_3,
            }
        )
        for item in streaks:
            all_streak_rows.append({"code": code, "name": name, **item})

    stock_stats = pd.DataFrame(rows)
    streak_df = pd.DataFrame(all_streak_rows)
    total_entries = int(stock_stats["入池次数"].sum()) if not stock_stats.empty else 0
    next_day_removed = int(stock_stats["次日剔除次数"].sum()) if not stock_stats.empty else 0
    three_day_removed = int(stock_stats["3日内剔除次数"].sum()) if not stock_stats.empty else 0
    summary = {
        "stock_count": int(stock_stats["code"].nunique()) if not stock_stats.empty else 0,
        "total_entries": total_entries,
        "avg_pool_size": round(len(presence) / len(dates), 2) if dates else 0,
        "avg_stay_days": round(float(streak_df["days"].mean()), 2) if not streak_df.empty else 0,
        "max_stay_days": int(streak_df["days"].max()) if not streak_df.empty else 0,
        "min_stay_days": int(streak_df["days"].min()) if not streak_df.empty else 0,
        "next_day_removed_ratio": next_day_removed / total_entries * 100 if total_entries else 0,
        "three_day_removed_ratio": three_day_removed / total_entries * 100 if total_entries else 0,
    }
    return stock_stats, streak_df, summary


def failed_filters(row: pd.Series, min_amount: float) -> list[str]:
    reasons = []
    if pd.isna(row.get("close")):
        return ["无行情数据"]
    if row.get("amount", 0) <= min_amount:
        reasons.append("成交额不足")
    if row.get("pct_chg", 0) <= 0:
        reasons.append("今日涨幅不大于0")
    if row.get("pct_5d", 0) <= 5:
        reasons.append("5日涨幅不足")
    if row.get("pct_10d", 0) <= 10:
        reasons.append("10日涨幅不足")
    if row.get("pct_20d", 0) <= 15:
        reasons.append("20日涨幅不足")
    if not (row.get("close", 0) > row.get("ma5", 0)):
        reasons.append("跌破5日线")
    if not (row.get("ma5", 0) > row.get("ma10", 0)):
        reasons.append("5日线未高于10日线")
    if not (row.get("ma10", 0) > row.get("ma20", 0)):
        reasons.append("10日线未高于20日线")
    if row.get("distance_to_20d_high", 100) > 10:
        reasons.append("距离20日高点过远")
    if row.get("pct_5d", 0) > 35:
        reasons.append("5日涨幅过大")
    open_price = row.get("open", 0)
    close = row.get("close", 0)
    pct_chg = row.get("pct_chg", 0)
    if open_price > 0 and close < open_price * 0.97 and pct_chg < -3:
        reasons.append("放量大阴线")
    return reasons or ["Top100排名外"]


def analyze_exit_reasons(indicators: pd.DataFrame, pools: dict[str, pd.DataFrame], dates: list[str], min_amount: float) -> pd.DataFrame:
    indicator_map = {
        (row["date"].strftime("%Y%m%d"), str(row["code"]).zfill(6)): row
        for _, row in indicators.iterrows()
    }
    reason_counts: dict[str, int] = {}

    for idx in range(len(dates) - 1):
        today = dates[idx]
        tomorrow = dates[idx + 1]
        today_pool = pools.get(today, pd.DataFrame())
        tomorrow_pool = pools.get(tomorrow, pd.DataFrame())
        today_codes = set(today_pool["code"].astype(str).str.zfill(6).tolist()) if not today_pool.empty else set()
        tomorrow_codes = set(tomorrow_pool["code"].astype(str).str.zfill(6).tolist()) if not tomorrow_pool.empty else set()
        removed_codes = today_codes - tomorrow_codes
        for code in removed_codes:
            row = indicator_map.get((tomorrow, code))
            reasons = ["无行情数据"] if row is None else failed_filters(row, min_amount)
            for reason in reasons:
                reason_counts[reason] = reason_counts.get(reason, 0) + 1

    result = pd.DataFrame(
        [{"过滤条件": key, "触发次数": value} for key, value in reason_counts.items()]
    )
    if result.empty:
        return pd.DataFrame(columns=["过滤条件", "触发次数", "占比"])
    total = result["触发次数"].sum()
    result["占比"] = result["触发次数"].map(lambda value: pct(value / total * 100 if total else 0))
    return result.sort_values("触发次数", ascending=False)


def make_conclusion(summary: dict, repeated: pd.DataFrame, long_stay: pd.DataFrame, exit_reasons: pd.DataFrame) -> str:
    sensitive = summary["avg_stay_days"] < 3 or summary["next_day_removed_ratio"] > 35 or summary["three_day_removed_ratio"] > 60
    top_reason = exit_reasons.iloc[0]["过滤条件"] if not exit_reasons.empty else "暂无"
    repeated_count = len(repeated)
    long_stay_count = len(long_stay)

    lines = [
        f"1. 当前趋势池是否过于敏感？{'是' if sensitive else '暂时不算过于敏感'}。平均在池天数为 {summary['avg_stay_days']} 天，次日剔除比例为 {pct(summary['next_day_removed_ratio'])}，3日内剔除比例为 {pct(summary['three_day_removed_ratio'])}。",
        "2. 是否应该增加连续入池机制？建议增加观察，但先作为回测参数验证。例如连续2天满足条件才允许买入，可以过滤一日脉冲票。",
        "3. 是否应该增加连续出池机制？建议验证。例如连续2天不满足条件才卖出，可以减少趋势票被单日波动洗出。",
        f"4. 是否应该缩减Top100到Top50？建议验证缩减。当前反复进入超过3次的股票有 {repeated_count} 只，连续留在池中超过10天的股票有 {long_stay_count} 只，说明核心票和噪声票差异明显。",
        f"5. 哪些过滤条件最容易导致频繁进出池？当前最主要触发项是：{top_reason}。需要重点观察它是否过度惩罚正常趋势震荡。",
    ]
    return "\n\n".join(lines)


def main() -> None:
    args = parse_args()
    start_date = parse_date(args.start)
    end_date = parse_date(args.end)
    config = load_config()
    min_amount = float(config.get("min_amount", 1_000_000_000))

    universe = load_universe(args.universe)
    histories = load_histories(universe, start_date, end_date, args.max_workers)
    indicators = add_indicators(histories)
    pools = build_daily_pools(indicators, min_amount)

    all_dates = sorted(
        indicators[
            (indicators["date"].dt.strftime("%Y%m%d") >= start_date)
            & (indicators["date"].dt.strftime("%Y%m%d") <= end_date)
        ]["date"].dt.strftime("%Y%m%d").unique()
    )
    dates = all_dates[-args.days :] if args.days else all_dates
    pools = {date: pools.get(date, pd.DataFrame()) for date in dates}

    presence = build_presence(pools, dates)
    stock_stats, streak_df, summary = analyze_stability(presence, dates)
    exit_reasons = analyze_exit_reasons(indicators, pools, dates, min_amount)

    repeated = stock_stats[stock_stats["入池次数"] > 3].sort_values(["入池次数", "在池总天数"], ascending=False) if not stock_stats.empty else pd.DataFrame()
    long_stay = streak_df[streak_df["days"] > 10].sort_values("days", ascending=False) if not streak_df.empty else pd.DataFrame()
    top_entries = stock_stats.sort_values(["入池次数", "在池总天数"], ascending=False).head(30) if not stock_stats.empty else pd.DataFrame()
    top_stay = stock_stats.sort_values(["最长在池天数", "在池总天数"], ascending=False).head(30) if not stock_stats.empty else pd.DataFrame()
    conclusion = make_conclusion(summary, repeated, long_stay, exit_reasons)

    content = f"""# 趋势池稳定性分析

分析区间：{dates[0] if dates else start_date} 至 {dates[-1] if dates else end_date}

## 一、总体稳定性

- 分析交易日数量：{len(dates)}
- 进入过趋势池的股票数：{summary['stock_count']}
- 总入池段数：{summary['total_entries']}
- 平均每日趋势池数量：{summary['avg_pool_size']}
- 平均在池天数：{summary['avg_stay_days']}
- 最长在池天数：{summary['max_stay_days']}
- 最短在池天数：{summary['min_stay_days']}
- 进入池后第二天被剔除比例：{pct(summary['next_day_removed_ratio'])}
- 进入池后3天内被剔除比例：{pct(summary['three_day_removed_ratio'])}

## 二、入池次数最多的股票

{markdown_table(top_entries, ['code', 'name', '入池次数', '在池总天数', '平均在池天数', '最长在池天数', '最短在池天数'], 30)}

## 三、连续留池能力最强的股票

{markdown_table(top_stay, ['code', 'name', '入池次数', '在池总天数', '平均在池天数', '最长在池天数'], 30)}

## 四、反复进入超过3次的股票

{markdown_table(repeated, ['code', 'name', '入池次数', '在池总天数', '平均在池天数', '最长在池天数'], 50)}

## 五、连续留在池中超过10天的股票

{markdown_table(long_stay, ['code', 'name', 'start_date', 'end_date', 'days'], 50)}

## 六、出池触发条件统计

{markdown_table(exit_reasons, ['过滤条件', '触发次数', '占比'])}

## 七、最终回答

{conclusion}
"""
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(content, encoding="utf-8")
    print(f"趋势池稳定性分析报告已生成：{REPORT_PATH}")


if __name__ == "__main__":
    main()

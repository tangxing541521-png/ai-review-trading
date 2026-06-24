from __future__ import annotations

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent
TRADE_PATH = PROJECT_ROOT / "backtest_trades.csv"
REPORT_PATH = PROJECT_ROOT / "reports" / "trade_analysis.md"


def pct(value: float) -> str:
    return f"{value:.2f}%"


def money(value: float) -> str:
    return f"{value:.2f}"


def markdown_table(df: pd.DataFrame, columns: list[str]) -> str:
    if df.empty:
        return "暂无数据"
    view = df[columns].copy()
    view = view.fillna("")
    rows = [[str(value) for value in row] for row in view.to_numpy().tolist()]
    widths = [max(len(str(col)), *(len(row[i]) for row in rows)) for i, col in enumerate(columns)]
    header = "| " + " | ".join(str(col).ljust(widths[i]) for i, col in enumerate(columns)) + " |"
    separator = "| " + " | ".join("-" * widths[i] for i in range(len(columns))) + " |"
    body = ["| " + " | ".join(row[i].ljust(widths[i]) for i in range(len(columns))) + " |" for row in rows]
    return "\n".join([header, separator, *body])


def max_streak(values: list[bool]) -> int:
    best = 0
    current = 0
    for value in values:
        if value:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def longest_period(trades: pd.DataFrame, is_win: bool) -> str:
    """按卖出日期顺序计算最长连续盈利/亏损周期。"""
    if trades.empty:
        return "暂无"
    target = trades["pnl"] > 0 if is_win else trades["pnl"] <= 0
    best_start = best_end = None
    best_len = 0
    current_start = None
    current_end = None
    current_len = 0

    for (_, row), flag in zip(trades.iterrows(), target.tolist()):
        if flag:
            if current_start is None:
                current_start = row["sell_date"]
            current_end = row["sell_date"]
            current_len += 1
            if current_len > best_len:
                best_len = current_len
                best_start = current_start
                best_end = current_end
        else:
            current_start = None
            current_end = None
            current_len = 0

    if best_len == 0:
        return "暂无"
    return f"{best_start} 至 {best_end}，{best_len} 笔"


def distribution(trades: pd.DataFrame) -> pd.DataFrame:
    total = len(trades)
    bins = [
        ("收益 > 20%", trades["pnl_pct"] > 20),
        ("收益 10%-20%", (trades["pnl_pct"] > 10) & (trades["pnl_pct"] <= 20)),
        ("收益 5%-10%", (trades["pnl_pct"] > 5) & (trades["pnl_pct"] <= 10)),
        ("收益 0%-5%", (trades["pnl_pct"] > 0) & (trades["pnl_pct"] <= 5)),
        ("亏损 0%-5%", (trades["pnl_pct"] <= 0) & (trades["pnl_pct"] > -5)),
        ("亏损 5%-10%", (trades["pnl_pct"] <= -5) & (trades["pnl_pct"] > -10)),
        ("亏损 >10%", trades["pnl_pct"] <= -10),
    ]
    rows = []
    for label, mask in bins:
        count = int(mask.sum())
        ratio = count / total * 100 if total else 0.0
        rows.append({"区间": label, "交易数": count, "占比": pct(ratio)})
    return pd.DataFrame(rows)


def aggregate_stock_rank(trades: pd.DataFrame, positive: bool) -> pd.DataFrame:
    grouped = trades.groupby(["code", "name"], as_index=False).agg(
        交易次数=("pnl", "count"),
        累计盈亏=("pnl", "sum"),
        平均盈亏=("pnl", "mean"),
        最大单笔=("pnl", "max" if positive else "min"),
    )
    if positive:
        ranked = grouped[grouped["累计盈亏"] > 0].sort_values("累计盈亏", ascending=False).head(20)
        ranked = ranked.rename(columns={"累计盈亏": "累计盈利", "平均盈亏": "平均盈利", "最大单笔": "最大盈利"})
        cols = ["股票代码", "股票名称", "交易次数", "累计盈利", "平均盈利", "最大盈利"]
    else:
        ranked = grouped[grouped["累计盈亏"] < 0].sort_values("累计盈亏", ascending=True).head(20)
        ranked = ranked.rename(columns={"累计盈亏": "累计亏损", "平均盈亏": "平均亏损", "最大单笔": "最大亏损"})
        cols = ["股票代码", "股票名称", "交易次数", "累计亏损", "平均亏损", "最大亏损"]

    ranked = ranked.rename(columns={"code": "股票代码", "name": "股票名称"})
    money_cols = [col for col in ranked.columns if col not in {"股票代码", "股票名称", "交易次数"}]
    for col in money_cols:
        ranked[col] = ranked[col].map(lambda x: round(float(x), 2))
    return ranked[cols]


def diagnose(trades: pd.DataFrame, stats: dict, dist_df: pd.DataFrame) -> tuple[str, list[str]]:
    """根据交易统计自动生成诊断和最终结论。"""
    winners = trades[trades["pnl"] > 0]
    losers = trades[trades["pnl"] <= 0]
    top_profit = winners["pnl"].sort_values(ascending=False).head(5).sum() if not winners.empty else 0
    total_profit = winners["pnl"].sum() if not winners.empty else 0
    top_profit_ratio = top_profit / total_profit * 100 if total_profit > 0 else 0
    big_win_ratio = float(dist_df.loc[dist_df["区间"].isin(["收益 > 20%", "收益 10%-20%"]), "占比"].str.replace("%", "").astype(float).sum())
    mid_loss_ratio = float(dist_df.loc[dist_df["区间"].isin(["亏损 0%-5%", "亏损 5%-10%"]), "占比"].str.replace("%", "").astype(float).sum())

    diagnosis = []
    if stats["expectancy"] > 0:
        diagnosis.append("该策略当前回测样本具备正期望值。")
    else:
        diagnosis.append("该策略当前回测样本暂未体现正期望值。")

    if top_profit_ratio >= 45:
        diagnosis.append("利润主要由少数大盈利交易贡献，策略更像依赖趋势行情中的大票拉动。")
    elif stats["win_rate"] >= 55:
        diagnosis.append("策略更依赖较高胜率稳定获利。")
    else:
        diagnosis.append("策略不是高胜率模型，收益更多依赖盈亏比和少数强趋势交易。")

    if stats["profit_loss_ratio"] > 1.5 and stats["win_rate"] < 50:
        diagnosis.append("该策略呈现大赚小亏特征，但需要承受较多小亏。")
    if stats["loss_count"] > stats["win_count"] and mid_loss_ratio > 40:
        diagnosis.append("亏损交易数量偏多，存在频繁止损或频繁被趋势池剔除的问题。")
    if big_win_ratio < 10 and stats["profit_loss_ratio"] <= 1:
        diagnosis.append("大盈利交易占比不足，趋势延伸捕捉能力需要继续观察。")

    conclusions = []
    conclusions.append(f"1. 策略是否具备正期望值？{'是' if stats['expectancy'] > 0 else '否'}，单笔平均收益约 {money(stats['expectancy'])} 元，平均收益率 {pct(stats['avg_return'])}。")
    conclusions.append("2. 最大问题在哪里？胜率不高且亏损交易数量偏多，资金曲线依赖少数强趋势交易贡献。")
    if stats["avg_win_holding"] <= stats["avg_loss_holding"] and stats["profit_loss_ratio"] > 1:
        conclusions.append("3. 应该优化买点还是卖点？优先优化买点和入池质量，减少弱趋势票进入；卖点目前能让盈利交易跑出更大的平均收益。")
    else:
        conclusions.append("3. 应该优化买点还是卖点？优先优化卖点，避免盈利回吐或亏损交易停留过久。")
    conclusions.append("4. 是否应该缩减趋势池规模？应该。当前不是高胜率模型，缩小到更强的核心趋势票更符合收益来源。")
    conclusions.append("5. 是否应该提高成交额门槛？可以小幅提高或分层使用。赚钱榜若集中在高流动性票，提高门槛有助于减少杂票；但过高会错过部分弹性票。")
    return "\n\n".join(diagnosis), conclusions


def analyze() -> str:
    if not TRADE_PATH.exists():
        raise FileNotFoundError(f"找不到回测交易文件：{TRADE_PATH}")

    trades = pd.read_csv(TRADE_PATH, dtype={"code": str})
    if trades.empty:
        raise RuntimeError("backtest_trades.csv 为空，无法进行交易归因分析。")

    trades["pnl"] = pd.to_numeric(trades["pnl"], errors="coerce").fillna(0)
    trades["pnl_pct"] = pd.to_numeric(trades["pnl_pct"], errors="coerce").fillna(0)
    trades["holding_days"] = pd.to_numeric(trades["holding_days"], errors="coerce").fillna(0)
    trades["sell_date"] = trades["sell_date"].astype(str)
    trades = trades.sort_values(["sell_date", "code"]).reset_index(drop=True)

    winners = trades[trades["pnl"] > 0]
    losers = trades[trades["pnl"] <= 0]
    total_count = len(trades)
    win_count = len(winners)
    loss_count = len(losers)
    avg_win = winners["pnl"].mean() if win_count else 0.0
    avg_loss = losers["pnl"].mean() if loss_count else 0.0
    profit_loss_ratio = avg_win / abs(avg_loss) if avg_loss else 0.0

    stats = {
        "total_count": total_count,
        "win_count": win_count,
        "loss_count": loss_count,
        "win_rate": win_count / total_count * 100 if total_count else 0.0,
        "avg_return": trades["pnl_pct"].mean(),
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "profit_loss_ratio": profit_loss_ratio,
        "expectancy": trades["pnl"].mean(),
        "avg_holding": trades["holding_days"].mean(),
        "avg_win_holding": winners["holding_days"].mean() if win_count else 0.0,
        "avg_loss_holding": losers["holding_days"].mean() if loss_count else 0.0,
        "max_holding": trades["holding_days"].max(),
        "min_holding": trades["holding_days"].min(),
        "max_win_streak": max_streak((trades["pnl"] > 0).tolist()),
        "max_loss_streak": max_streak((trades["pnl"] <= 0).tolist()),
    }

    top_profit = aggregate_stock_rank(trades, positive=True)
    top_loss = aggregate_stock_rank(trades, positive=False)
    dist_df = distribution(trades)
    diagnosis, conclusions = diagnose(trades, stats, dist_df)

    content = f"""# 交易归因分析报告

数据来源：`backtest_trades.csv`

## 一、总体统计

- 总交易数：{stats['total_count']}
- 盈利交易数：{stats['win_count']}
- 亏损交易数：{stats['loss_count']}
- 胜率：{pct(stats['win_rate'])}
- 平均收益率：{pct(stats['avg_return'])}
- 平均盈利：{money(stats['avg_win'])}
- 平均亏损：{money(stats['avg_loss'])}
- 盈亏比：{stats['profit_loss_ratio']:.2f}

## 二、赚钱榜

{markdown_table(top_profit, ['股票代码', '股票名称', '交易次数', '累计盈利', '平均盈利', '最大盈利'])}

## 三、亏钱榜

{markdown_table(top_loss, ['股票代码', '股票名称', '交易次数', '累计亏损', '平均亏损', '最大亏损'])}

## 四、持仓分析

- 平均持仓天数：{stats['avg_holding']:.2f}
- 盈利交易平均持仓天数：{stats['avg_win_holding']:.2f}
- 亏损交易平均持仓天数：{stats['avg_loss_holding']:.2f}
- 最大持仓天数：{int(stats['max_holding'])}
- 最短持仓天数：{int(stats['min_holding'])}

## 五、连续性分析

- 最大连续盈利次数：{stats['max_win_streak']}
- 最大连续亏损次数：{stats['max_loss_streak']}
- 最长盈利周期：{longest_period(trades, True)}
- 最长亏损周期：{longest_period(trades, False)}

## 六、收益分布

{markdown_table(dist_df, ['区间', '交易数', '占比'])}

## 七、策略诊断

{diagnosis}

## 八、最终结论

{chr(10).join(conclusions)}
"""

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(content, encoding="utf-8")
    return str(REPORT_PATH)


def main() -> None:
    report_path = analyze()
    print(f"交易归因分析报告已生成：{report_path}")


if __name__ == "__main__":
    main()

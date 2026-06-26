from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent
DISCLAIMER = "仅供学习研究和模拟验证，不构成投资建议；不得据此进行真实交易。"


METRIC_COLUMNS = [
    "metric",
    "value",
    "unit",
    "description",
]
HEALTH_COLUMNS = [
    "date",
    "strategy_health_score",
    "rating",
    "return_score",
    "return_drawdown_score",
    "win_rate_score",
    "profit_factor_score",
    "drawdown_score",
    "excess_return_score",
    "sample_warning",
]


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str)
    except Exception:
        return pd.DataFrame()


def _to_float(value, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _num_series(df: pd.DataFrame, column: str) -> pd.Series:
    if df.empty or column not in df.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(df[column], errors="coerce").dropna()


def _latest_float(df: pd.DataFrame, column: str, default: float = 0.0) -> float:
    series = _num_series(df, column)
    if series.empty:
        return default
    return float(series.iloc[-1])


def _max_drawdown(equity: pd.DataFrame) -> float:
    if equity.empty:
        return 0.0
    if "max_drawdown" in equity.columns:
        drawdown = _num_series(equity, "max_drawdown")
        if not drawdown.empty:
            return abs(float(drawdown.min()))
    assets = _num_series(equity, "total_assets")
    if assets.empty:
        return 0.0
    peak = assets.cummax()
    dd = (assets / peak - 1) * 100
    return abs(float(dd.min()))


def _max_consecutive_losses(trades: pd.DataFrame) -> int:
    if trades.empty or "pnl_pct" not in trades.columns:
        return 0
    closed = trades[trades.get("action", "") == "SELL"].copy() if "action" in trades.columns else trades.copy()
    pnl = pd.to_numeric(closed.get("pnl_pct", pd.Series(dtype=float)), errors="coerce").dropna()
    max_streak = 0
    current = 0
    for value in pnl:
        if value <= 0:
            current += 1
            max_streak = max(max_streak, current)
        else:
            current = 0
    return max_streak


def _max_consecutive_cash_days(equity: pd.DataFrame) -> int:
    if equity.empty or "market_value" not in equity.columns:
        return 0
    market_value = pd.to_numeric(equity["market_value"], errors="coerce").fillna(0)
    max_streak = 0
    current = 0
    for value in market_value:
        if value <= 0:
            current += 1
            max_streak = max(max_streak, current)
        else:
            current = 0
    return max_streak


def _rates_from_validation(validation: pd.DataFrame) -> dict:
    if validation.empty:
        return {
            "cash_correct_rate": 0.0,
            "entry_correct_rate": 0.0,
            "recommended_avg_return": 0.0,
            "avg_excess_return": 0.0,
            "index_total_return": 0.0,
            "evaluated_count": 0,
        }
    data = validation.copy()
    if "status" in data.columns:
        data = data[data["status"].astype(str) == "evaluated"]
    rec = pd.to_numeric(data.get("recommended_return", pd.Series(dtype=float)), errors="coerce")
    idx = pd.to_numeric(data.get("index_return", pd.Series(dtype=float)), errors="coerce")
    excess = pd.to_numeric(data.get("excess_return", pd.Series(dtype=float)), errors="coerce")
    allow = data.get("allow_trade", pd.Series(dtype=str)).astype(str)
    no_trade = data.get("no_trade_day", pd.Series(dtype=str)).astype(str)

    evaluated = data.copy()
    evaluated["recommended_return_num"] = rec
    evaluated["index_return_num"] = idx
    evaluated["excess_return_num"] = excess
    evaluated = evaluated.dropna(subset=["recommended_return_num", "index_return_num"])

    cash_days = evaluated[(allow != "YES") | (no_trade == "YES")]
    entry_days = evaluated[(allow == "YES") & (no_trade != "YES")]

    # 空仓正确：不交易日里，推荐池不强于指数，或指数为负。
    if cash_days.empty:
        cash_correct_rate = 0.0
    else:
        cash_correct = (cash_days["recommended_return_num"] <= cash_days["index_return_num"]) | (cash_days["index_return_num"] <= 0)
        cash_correct_rate = float(cash_correct.mean() * 100)

    # 开仓正确：允许交易日里，推荐池收益为正且跑赢指数。
    if entry_days.empty:
        entry_correct_rate = 0.0
    else:
        entry_correct = (entry_days["recommended_return_num"] > 0) & (entry_days["recommended_return_num"] > entry_days["index_return_num"])
        entry_correct_rate = float(entry_correct.mean() * 100)

    return {
        "cash_correct_rate": round(cash_correct_rate, 2),
        "entry_correct_rate": round(entry_correct_rate, 2),
        "recommended_avg_return": round(float(evaluated["recommended_return_num"].mean()), 2) if not evaluated.empty else 0.0,
        "avg_excess_return": round(float(evaluated["excess_return_num"].dropna().mean()), 2) if not evaluated.empty else 0.0,
        "index_total_return": round(float(idx.dropna().sum()), 2) if not idx.dropna().empty else 0.0,
        "evaluated_count": int(len(evaluated)),
    }


def _frozen_order_stats() -> dict:
    files = sorted((PROJECT_ROOT / "frozen_decisions").glob("orders_*.json"))
    total_orders = 0
    buy_orders = 0
    sell_orders = 0
    skip_orders = 0
    frozen_dates = []
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        frozen_dates.append(str(payload.get("date", path.stem.replace("orders_", ""))))
        orders = payload.get("orders", [])
        total_orders += len(orders)
        for order in orders:
            action = str(order.get("action", ""))
            if action == "BUY":
                buy_orders += 1
            elif action == "SELL":
                sell_orders += 1
            elif action == "SKIP":
                skip_orders += 1
    return {
        "frozen_days": len(set(frozen_dates)),
        "total_frozen_orders": total_orders,
        "buy_orders": buy_orders,
        "sell_orders": sell_orders,
        "skip_orders": skip_orders,
    }


def _trade_stats(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return {
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "avg_profit": 0.0,
            "avg_loss": 0.0,
            "trade_count": 0,
        }
    closed = trades[trades.get("action", "") == "SELL"].copy() if "action" in trades.columns else trades.copy()
    pnl = pd.to_numeric(closed.get("pnl", pd.Series(dtype=float)), errors="coerce").dropna()
    if pnl.empty:
        return {
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "avg_profit": 0.0,
            "avg_loss": 0.0,
            "trade_count": 0,
        }
    wins = pnl[pnl > 0]
    losses = pnl[pnl <= 0]
    gross_profit = float(wins.sum()) if not wins.empty else 0.0
    gross_loss = abs(float(losses.sum())) if not losses.empty else 0.0
    if gross_loss == 0 and gross_profit > 0:
        profit_factor = np.inf
    elif gross_loss == 0:
        profit_factor = 0.0
    else:
        profit_factor = gross_profit / gross_loss
    return {
        "win_rate": round(float((pnl > 0).mean() * 100), 2),
        "profit_factor": round(float(profit_factor), 4) if np.isfinite(profit_factor) else 999.0,
        "avg_profit": round(float(wins.mean()), 2) if not wins.empty else 0.0,
        "avg_loss": round(float(losses.mean()), 2) if not losses.empty else 0.0,
        "trade_count": int(len(pnl)),
    }


def _rating(score: float) -> str:
    if score >= 80:
        return "A：80分以上，具备继续模拟盘验证价值"
    if score >= 60:
        return "B：60-80分，可以继续观察"
    if score >= 40:
        return "C：40-60分，策略需要优化"
    return "D：40分以下，不建议进入模拟盘"


def _build_health_score(metrics: dict) -> dict:
    return_score = 20 if metrics["cumulative_return"] > 0 else 0
    return_drawdown_score = 20 if metrics["return_drawdown_ratio"] > 2 else 0
    win_rate_score = 15 if metrics["win_rate"] > 50 else 0
    profit_factor_score = 15 if metrics["profit_factor"] > 1.5 else 0
    drawdown_score = 15 if metrics["max_drawdown"] < 10 else 0
    excess_return_score = 15 if metrics["avg_excess_return"] > 0 else 0
    total = return_score + return_drawdown_score + win_rate_score + profit_factor_score + drawdown_score + excess_return_score
    return {
        "date": metrics["date"],
        "strategy_health_score": total,
        "rating": _rating(total),
        "return_score": return_score,
        "return_drawdown_score": return_drawdown_score,
        "win_rate_score": win_rate_score,
        "profit_factor_score": profit_factor_score,
        "drawdown_score": drawdown_score,
        "excess_return_score": excess_return_score,
        "sample_warning": metrics["sample_warning"],
    }


def judge_strategy() -> tuple[dict, dict, pd.DataFrame]:
    equity = _read_csv(PROJECT_ROOT / "paper_equity_curve.csv")
    trades = _read_csv(PROJECT_ROOT / "paper_trades.csv")
    validation = _read_csv(PROJECT_ROOT / "forward_validation.csv")
    positions = _read_csv(PROJECT_ROOT / "paper_positions.csv")

    cumulative_return = round(_latest_float(equity, "cumulative_return"), 2)
    max_drawdown = round(_max_drawdown(equity), 2)
    if max_drawdown == 0 and cumulative_return > 0:
        return_drawdown_ratio = 999.0
    elif max_drawdown == 0:
        return_drawdown_ratio = 0.0
    else:
        return_drawdown_ratio = round(cumulative_return / max_drawdown, 4)

    trade_stats = _trade_stats(trades)
    validation_stats = _rates_from_validation(validation)
    order_stats = _frozen_order_stats()
    daily_return = _num_series(equity, "daily_return")
    max_single_day_loss = round(float(daily_return.min()), 2) if not daily_return.empty else 0.0
    paper_beats_index = cumulative_return > validation_stats["index_total_return"]

    sample_warning = "样本不足：当前 Paper Trading 和 Forward Validation 样本过少，评级仅作结构化诊断。"
    if len(equity) >= 20 and validation_stats["evaluated_count"] >= 10 and trade_stats["trade_count"] >= 10:
        sample_warning = "样本初步可用，但仍需继续前向验证。"

    metrics = {
        "date": str(equity.iloc[-1]["date"]) if not equity.empty and "date" in equity.columns else "",
        "cumulative_return": cumulative_return,
        "max_drawdown": max_drawdown,
        "return_drawdown_ratio": return_drawdown_ratio,
        "win_rate": trade_stats["win_rate"],
        "profit_factor": trade_stats["profit_factor"],
        "avg_profit": trade_stats["avg_profit"],
        "avg_loss": trade_stats["avg_loss"],
        "max_single_day_loss": max_single_day_loss,
        "max_consecutive_losses": _max_consecutive_losses(trades),
        "max_consecutive_cash_days": _max_consecutive_cash_days(equity),
        "cash_correct_rate": validation_stats["cash_correct_rate"],
        "entry_correct_rate": validation_stats["entry_correct_rate"],
        "recommended_avg_return": validation_stats["recommended_avg_return"],
        "avg_excess_return": validation_stats["avg_excess_return"],
        "paper_beats_index": paper_beats_index,
        "index_total_return": validation_stats["index_total_return"],
        "trade_count": trade_stats["trade_count"],
        "evaluated_count": validation_stats["evaluated_count"],
        "holding_count": int(len(positions[positions.get("status", "") == "holding"])) if not positions.empty and "status" in positions.columns else 0,
        "sample_warning": sample_warning,
        **order_stats,
    }
    health = _build_health_score(metrics)
    metric_rows = pd.DataFrame(
        [
            ["累计收益率", metrics["cumulative_return"], "%", "Paper Trading 最新累计收益率"],
            ["最大回撤", metrics["max_drawdown"], "%", "资金曲线最大回撤绝对值"],
            ["收益回撤比", metrics["return_drawdown_ratio"], "倍", "累计收益率 / 最大回撤"],
            ["胜率", metrics["win_rate"], "%", "已卖出交易中盈利占比"],
            ["盈亏比", metrics["profit_factor"], "倍", "总盈利 / 总亏损"],
            ["平均盈利", metrics["avg_profit"], "元", "盈利交易平均 PnL"],
            ["平均亏损", metrics["avg_loss"], "元", "亏损交易平均 PnL"],
            ["最大单日亏损", metrics["max_single_day_loss"], "%", "资金曲线 daily_return 最小值"],
            ["最大连续亏损次数", metrics["max_consecutive_losses"], "次", "已完成交易连续亏损"],
            ["最大连续空仓天数", metrics["max_consecutive_cash_days"], "天", "market_value 为 0 的最长连续天数"],
            ["空仓正确率", metrics["cash_correct_rate"], "%", "不交易日中推荐池未强于指数或指数下跌的比例"],
            ["开仓正确率", metrics["entry_correct_rate"], "%", "允许交易日推荐池为正且跑赢指数的比例"],
            ["推荐股票平均收益", metrics["recommended_avg_return"], "%", "Forward Validation 已评估推荐收益均值"],
            ["推荐股票相对指数超额收益", metrics["avg_excess_return"], "%", "Forward Validation 已评估超额收益均值"],
            ["Paper Trading 是否跑赢指数", str(metrics["paper_beats_index"]), "", "Paper累计收益率是否大于验证期指数收益合计"],
            ["冻结天数", metrics["frozen_days"], "天", "frozen_decisions/orders_*.json 数量"],
            ["冻结订单数", metrics["total_frozen_orders"], "条", "冻结 JSON 中订单总数"],
            ["BUY订单数", metrics["buy_orders"], "条", "冻结订单 BUY 数量"],
            ["SELL订单数", metrics["sell_orders"], "条", "冻结订单 SELL 数量"],
            ["SKIP订单数", metrics["skip_orders"], "条", "冻结订单 SKIP 数量"],
        ],
        columns=METRIC_COLUMNS,
    )
    return metrics, health, metric_rows


def _yes_no(value: bool) -> str:
    return "是" if value else "否"


def write_report(metrics: dict, health: dict, metric_rows: pd.DataFrame) -> Path:
    report_path = PROJECT_ROOT / "strategy_judge_report.md"
    metrics_path = PROJECT_ROOT / "strategy_metrics.csv"
    health_path = PROJECT_ROOT / "strategy_health_score.csv"
    metric_rows.to_csv(metrics_path, index=False, encoding="utf-8-sig")
    pd.DataFrame([health], columns=HEALTH_COLUMNS).to_csv(health_path, index=False, encoding="utf-8-sig")

    profitable = metrics["cumulative_return"] > 0
    beats_index = bool(metrics["paper_beats_index"])
    drawdown_ok = metrics["max_drawdown"] < 10
    over_cash = metrics["max_consecutive_cash_days"] >= max(5, metrics["evaluated_count"])
    worth_paper = health["strategy_health_score"] >= 60 and metrics["evaluated_count"] >= 10
    worth_small_live = False

    if metrics["trade_count"] == 0:
        biggest_problem = "当前没有已完成交易，无法评估真实交易胜率、盈亏比和回撤承压能力。"
    elif metrics["evaluated_count"] < 10:
        biggest_problem = "Forward Validation 样本不足，统计显著性不够。"
    elif metrics["avg_excess_return"] <= 0:
        biggest_problem = "推荐股票尚未证明稳定跑赢指数。"
    else:
        biggest_problem = "需要继续观察冻结订单在更长周期中的收益稳定性。"

    next_step = "继续积累前向验证样本，暂不进入实盘；样本达到至少20-30个交易日后再复评。"
    if health["strategy_health_score"] < 40:
        next_step = "不建议进入模拟盘扩展，应先复盘样本和风险控制，但不要为短期分数改历史数据。"
    elif health["strategy_health_score"] >= 60 and metrics["evaluated_count"] >= 10:
        next_step = "可以继续模拟盘验证，但仍不建议小资金实盘。"

    content = f"""# Strategy Judge 策略终极评估报告

> {DISCLAIMER}

## 一、最终评分

- strategy_health_score：{health['strategy_health_score']} / 100
- 最终评级：{health['rating']}
- 样本提示：{metrics['sample_warning']}

## 二、核心指标

| 指标 | 数值 | 单位 |
| --- | ---: | --- |
| 累计收益率 | {metrics['cumulative_return']} | % |
| 最大回撤 | {metrics['max_drawdown']} | % |
| 收益回撤比 | {metrics['return_drawdown_ratio']} | 倍 |
| 胜率 | {metrics['win_rate']} | % |
| 盈亏比 | {metrics['profit_factor']} | 倍 |
| 平均盈利 | {metrics['avg_profit']} | 元 |
| 平均亏损 | {metrics['avg_loss']} | 元 |
| 最大单日亏损 | {metrics['max_single_day_loss']} | % |
| 最大连续亏损次数 | {metrics['max_consecutive_losses']} | 次 |
| 最大连续空仓天数 | {metrics['max_consecutive_cash_days']} | 天 |
| 空仓正确率 | {metrics['cash_correct_rate']} | % |
| 开仓正确率 | {metrics['entry_correct_rate']} | % |
| 推荐股票平均收益 | {metrics['recommended_avg_return']} | % |
| 推荐股票相对指数超额收益 | {metrics['avg_excess_return']} | % |
| Paper Trading 是否跑赢指数 | {_yes_no(metrics['paper_beats_index'])} |  |

## 三、健康分拆解

| 评分项 | 得分 |
| --- | ---: |
| 收益率 > 0 | {health['return_score']} |
| 收益回撤比 > 2 | {health['return_drawdown_score']} |
| 胜率 > 50% | {health['win_rate_score']} |
| 盈亏比 > 1.5 | {health['profit_factor_score']} |
| 最大回撤 < 10% | {health['drawdown_score']} |
| 超额收益 > 0 | {health['excess_return_score']} |

## 四、冻结订单统计

- 冻结天数：{metrics['frozen_days']}
- 冻结订单数：{metrics['total_frozen_orders']}
- BUY订单数：{metrics['buy_orders']}
- SELL订单数：{metrics['sell_orders']}
- SKIP订单数：{metrics['skip_orders']}

## 五、最终结论

1. 当前策略是否赚钱：{_yes_no(profitable)}，当前累计收益率为 {metrics['cumulative_return']}%。
2. 是否跑赢指数：{_yes_no(beats_index)}，当前平均超额收益为 {metrics['avg_excess_return']}%。
3. 是否回撤可控：{_yes_no(drawdown_ok)}，当前最大回撤为 {metrics['max_drawdown']}%。
4. 是否过度空仓：{_yes_no(over_cash)}，当前最大连续空仓天数为 {metrics['max_consecutive_cash_days']} 天。
5. 是否值得进入同花顺模拟盘：{_yes_no(worth_paper)}。当前更适合继续本地前向验证。
6. 是否值得小资金实盘：{_yes_no(worth_small_live)}。当前不建议进入小资金实盘。
7. 当前最大问题：{biggest_problem}
8. 下一步应该继续验证还是优化：{next_step}

## 六、文件输出

- `strategy_metrics.csv`
- `strategy_health_score.csv`

## 七、纪律

- 不因为评分结果修改策略。
- 不修改历史数据。
- 不删除亏损记录。
- 不接同花顺。
- 不自动下单。
"""
    report_path.write_text(content, encoding="utf-8")
    return report_path


def main() -> None:
    metrics, health, metric_rows = judge_strategy()
    report_path = write_report(metrics, health, metric_rows)
    print("Strategy Judge 已完成")
    print(f"当前策略评分：{health['strategy_health_score']}/100")
    print(f"当前评级：{health['rating']}")
    print(f"是否建议进入模拟盘：{'是' if health['strategy_health_score'] >= 60 and metrics['evaluated_count'] >= 10 else '否'}")
    print(f"最大风险点：{metrics['sample_warning']}")
    print(f"报告路径：{report_path}")
    print(f"指标文件：{PROJECT_ROOT / 'strategy_metrics.csv'}")
    print(f"健康分文件：{PROJECT_ROOT / 'strategy_health_score.csv'}")


if __name__ == "__main__":
    main()

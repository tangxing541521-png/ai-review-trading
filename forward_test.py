from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd

from execution_alignment_layer import build_execution_alignment
from execution_layer import build_execution_layer
from forward_validation import update_forward_validation
from main import PROJECT_ROOT, load_config
from market_cycle import update_market_cycle
from strategy.trend_core import build_trend_core_pool
from decision_freeze import freeze_order_files, is_frozen
from system_clock import assert_generation_allowed
from trade_decision_engine import build_trade_decision


FORWARD_COLUMNS = [
    "date",
    "code",
    "name",
    "momentum_score",
    "trend_score",
    "combined_score",
    "action",
    "buy_price",
    "close_price",
    "day1_return",
    "day3_return",
    "day5_return",
    "max_return",
    "max_drawdown",
    "status",
]
SUMMARY_COLUMNS = [
    "date",
    "total_observed",
    "day1_win_rate",
    "day3_win_rate",
    "day5_win_rate",
    "avg_day1_return",
    "avg_day3_return",
    "avg_day5_return",
    "max_profit",
    "max_loss",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="V3 策略前向验证，仅生成模拟建议和观察报告")
    parser.add_argument("--date", help="前向验证日期，格式 YYYYMMDD")
    return parser.parse_args()


def _read_csv(path: Path, columns: list[str] | None = None) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame(columns=columns or [])
    return pd.read_csv(path, dtype={"code": str})


def _safe_float(value, default: float = np.nan) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _return_pct(price: float, base: float) -> float:
    if not base or pd.isna(base) or pd.isna(price):
        return np.nan
    return round((price / base - 1) * 100, 2)


def _days_between(start: str, end: str, calendar_dates: list[str]) -> int:
    """优先按已有前向验证日期计算观察天数，缺失时退化为自然日。"""
    if start in calendar_dates and end in calendar_dates:
        return max(0, calendar_dates.index(end) - calendar_dates.index(start))
    try:
        return max(0, (datetime.strptime(end, "%Y%m%d") - datetime.strptime(start, "%Y%m%d")).days)
    except Exception:
        return 0


def _format_table(df: pd.DataFrame, columns: list[str]) -> str:
    if df.empty:
        return "暂无数据"
    view = df[[col for col in columns if col in df.columns]].fillna("")
    if view.empty:
        return "暂无数据"
    rows = [[str(value) for value in row] for row in view.to_numpy().tolist()]
    headers = list(view.columns)
    widths = [max(len(headers[i]), *(len(row[i]) for row in rows)) for i in range(len(headers))]
    header = "| " + " | ".join(headers[i].ljust(widths[i]) for i in range(len(headers))) + " |"
    separator = "| " + " | ".join("-" * widths[i] for i in range(len(headers))) + " |"
    body = ["| " + " | ".join(row[i].ljust(widths[i]) for i in range(len(headers))) + " |" for row in rows]
    return "\n".join([header, separator, *body])


def _load_latest_pool(target_date: str, config: Dict) -> tuple[Path, pd.DataFrame]:
    """复用冻结后的趋势核心池生成逻辑，不在 forward test 中改选股规则。"""
    pool_path = build_trend_core_pool(target_date, config, PROJECT_ROOT)
    pool = _read_csv(pool_path)
    if not pool.empty:
        pool["code"] = pool["code"].astype(str).str.zfill(6)
        if "momentum_score" in pool.columns:
            pool["momentum_score"] = pd.to_numeric(pool["momentum_score"], errors="coerce")
        pool["trend_score"] = pd.to_numeric(pool["trend_score"], errors="coerce")
        if "combined_score" in pool.columns:
            pool["combined_score"] = pd.to_numeric(pool["combined_score"], errors="coerce")
        pool["close"] = pd.to_numeric(pool["close"], errors="coerce")
    return pool_path, pool


def _update_existing_records(records: pd.DataFrame, pool: pd.DataFrame, target_date: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """更新历史观察记录，并生成今日卖出、持有、风险观察列表。"""
    if records.empty:
        return records, pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    records = records.copy()
    records["code"] = records["code"].astype(str).str.zfill(6)
    pool_map = pool.set_index("code").to_dict("index") if not pool.empty else {}
    calendar_dates = sorted(set(records["date"].astype(str).tolist() + [target_date]))

    sell_rows = []
    hold_rows = []
    risk_rows = []

    for idx, row in records.iterrows():
        code = str(row["code"]).zfill(6)
        if str(row.get("status", "")).startswith("【模拟】已卖出"):
            continue

        buy_date = str(row["date"])
        buy_price = _safe_float(row.get("buy_price"))
        latest = pool_map.get(code)
        old_close = _safe_float(row.get("close_price"), buy_price)
        close_price = _safe_float(latest.get("close")) if latest else old_close
        current_return = _return_pct(close_price, buy_price)
        observed_days = _days_between(buy_date, target_date, calendar_dates)

        records.at[idx, "close_price"] = round(close_price, 2) if not pd.isna(close_price) else ""
        if observed_days >= 1 and pd.isna(_safe_float(row.get("day1_return"))):
            records.at[idx, "day1_return"] = current_return
        if observed_days >= 3 and pd.isna(_safe_float(row.get("day3_return"))):
            records.at[idx, "day3_return"] = current_return
        if observed_days >= 5 and pd.isna(_safe_float(row.get("day5_return"))):
            records.at[idx, "day5_return"] = current_return

        old_max = _safe_float(row.get("max_return"))
        old_dd = _safe_float(row.get("max_drawdown"))
        records.at[idx, "max_return"] = round(np.nanmax([old_max, current_return]), 2)
        records.at[idx, "max_drawdown"] = round(np.nanmin([old_dd, current_return]), 2)

        status = str(row.get("status", "【模拟】持有"))
        in_pool = latest is not None
        if in_pool:
            records.at[idx, "action"] = "【模拟】继续持有"
            records.at[idx, "status"] = "【模拟】持有"
            hold_rows.append(
                {
                    "代码": code,
                    "名称": row.get("name", ""),
                    "持仓天数": observed_days,
                    "当前收益率": current_return,
                }
            )
            continue

        if "观察1天" in status:
            records.at[idx, "action"] = "【模拟】卖出"
            records.at[idx, "status"] = "【模拟】已卖出"
            sell_rows.append({"代码": code, "名称": row.get("name", ""), "卖出原因": "连续2天不在趋势池"})
        else:
            records.at[idx, "action"] = "【模拟】风险观察"
            records.at[idx, "status"] = "【模拟】风险观察1天"
            risk_rows.append({"代码": code, "名称": row.get("name", ""), "风险原因": "第1天不在趋势池，等待连续2天确认"})

    return records, pd.DataFrame(sell_rows), pd.DataFrame(hold_rows), pd.DataFrame(risk_rows)


def _append_today_top5(records: pd.DataFrame, pool: pd.DataFrame, target_date: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """把今日 Top5 作为【模拟】买入建议写入观察表，已观察过的同日同股不重复追加。"""
    if pool.empty:
        return records, pd.DataFrame()

    top5 = pool.sort_values("trend_score", ascending=False).head(5).copy()
    existing_keys = set()
    if not records.empty:
        existing_keys = set(zip(records["date"].astype(str), records["code"].astype(str).str.zfill(6)))

    new_rows = []
    report_rows = []
    for _, item in top5.iterrows():
        code = str(item["code"]).zfill(6)
        report_rows.append(
            {
                "代码": code,
                "名称": item.get("name", ""),
                "momentum_score": round(_safe_float(item.get("momentum_score")), 2),
                "trend_score": round(_safe_float(item.get("trend_score")), 2),
                "combined_score": round(_safe_float(item.get("combined_score")), 2),
                "推荐理由": item.get("reason", ""),
            }
        )
        if (target_date, code) in existing_keys:
            continue
        close_price = _safe_float(item.get("close"))
        new_rows.append(
            {
                "date": target_date,
                "code": code,
                "name": item.get("name", ""),
                "momentum_score": round(_safe_float(item.get("momentum_score")), 2),
                "trend_score": round(_safe_float(item.get("trend_score")), 2),
                "combined_score": round(_safe_float(item.get("combined_score")), 2),
                "action": "【模拟】买入建议",
                "buy_price": round(close_price, 2) if not pd.isna(close_price) else "",
                "close_price": round(close_price, 2) if not pd.isna(close_price) else "",
                "day1_return": np.nan,
                "day3_return": np.nan,
                "day5_return": np.nan,
                "max_return": 0.0,
                "max_drawdown": 0.0,
                "status": "【模拟】持有",
            }
        )

    if new_rows:
        records = pd.concat([records, pd.DataFrame(new_rows)], ignore_index=True)
    return records, pd.DataFrame(report_rows)


def _build_summary(records: pd.DataFrame, target_date: str) -> dict:
    def _series(col: str) -> pd.Series:
        if records.empty or col not in records.columns:
            return pd.Series(dtype=float)
        return pd.to_numeric(records[col], errors="coerce").dropna()

    day1 = _series("day1_return")
    day3 = _series("day3_return")
    day5 = _series("day5_return")
    max_return = _series("max_return")
    max_drawdown = _series("max_drawdown")
    return {
        "date": target_date,
        "total_observed": int(len(records)),
        "day1_win_rate": round(float((day1 > 0).mean() * 100), 2) if not day1.empty else 0.0,
        "day3_win_rate": round(float((day3 > 0).mean() * 100), 2) if not day3.empty else 0.0,
        "day5_win_rate": round(float((day5 > 0).mean() * 100), 2) if not day5.empty else 0.0,
        "avg_day1_return": round(float(day1.mean()), 2) if not day1.empty else 0.0,
        "avg_day3_return": round(float(day3.mean()), 2) if not day3.empty else 0.0,
        "avg_day5_return": round(float(day5.mean()), 2) if not day5.empty else 0.0,
        "max_profit": round(float(max_return.max()), 2) if not max_return.empty else 0.0,
        "max_loss": round(float(max_drawdown.min()), 2) if not max_drawdown.empty else 0.0,
    }


def _write_daily_report(
    target_date: str,
    report_dir: Path,
    top5: pd.DataFrame,
    sells: pd.DataFrame,
    holds: pd.DataFrame,
    risks: pd.DataFrame,
    cycle: dict,
    decision: dict,
    execution: dict,
    alignment: dict,
) -> Path:
    report_path = report_dir / f"forward_report_{target_date}.md"
    decision_cycle = decision["cycle"]
    position = decision["position"]
    leaders = decision["leaders"]
    final = decision["final"]
    final_signal = final["signal"]
    risk_gate = final["risk_gate"]
    final_stocks = final["stocks"]
    execution_records = execution["records"]
    orders = execution.get("orders", pd.DataFrame())
    signal_quality = alignment.get("quality", pd.DataFrame())
    leader_pool = leaders[leaders["pool_type"] == "A类：龙头进攻池"].copy() if not leaders.empty else pd.DataFrame()
    trend_pool = leaders[leaders["pool_type"] == "B类：趋势持仓池"].copy() if not leaders.empty else pd.DataFrame()
    risk_pool = leaders[leaders["pool_type"] == "D类：风险剔除池"].copy() if not leaders.empty else pd.DataFrame()
    final_attack = final_stocks[final_stocks["final_decision"] == "核心进攻标的"].sort_values("master_score", ascending=False) if not final_stocks.empty else pd.DataFrame()
    executable = execution_records[execution_records["action"] == "BUY"].sort_values("master_score", ascending=False) if not execution_records.empty else pd.DataFrame()
    blocked = execution_records[execution_records["action"].isin(["SKIP", "SELL"])].sort_values(["action", "master_score"], ascending=[True, False]).head(20) if not execution_records.empty else pd.DataFrame()
    executable_orders = orders[orders["action"].isin(["BUY", "SELL"])].sort_values("score", ascending=False) if not orders.empty else pd.DataFrame()
    aligned_executable = signal_quality[signal_quality["aligned_action"].isin(["BUY", "SELL"])].sort_values("signal_quality_score", ascending=False) if not signal_quality.empty else pd.DataFrame()
    content = f"""# Forward Test 前向验证日报 {target_date}

> 本报告全部为【模拟】建议，只用于验证 V3 策略真实市场表现，不自动交易、不下单、不连接券商、不控制任何交易软件。

## 今日市场一句话总结

{final_signal.get("one_sentence_summary", "数据不足，空仓观望")}

## 唯一核心裁决

- 今天是否值得参与市场：{final_signal.get("market_regime_final", "空仓（防守）")}
- 风控闸门：{risk_gate.get("risk_gate_action", "禁止开仓")}
- 风控原因：{risk_gate.get("risk_gate_reason", "数据不足")}
- master_score均值：{final_signal.get("master_score_mean", 0)}
- 最高master_score：{final_signal.get("top_master_score", 0)}

## 交易执行闭环

- 今日是否可以交易：{execution.get("can_trade_today", "NO")}
- 今日是否 NO TRADE DAY：{execution.get("no_trade_day", "YES")}
- 今日交易强度：{execution.get("trade_intensity", 0)}
- 可执行订单数量：{execution.get("order_count", 0)}
- 最大仓位：{execution.get("max_position_ratio", 0)}%
- 风险等级：{execution.get("risk_level", 0)}
- 仓位总原则：{execution.get("market_regime_final", "空仓（防守）")}
- 执行风控原因：{execution.get("risk_gate_reason", "数据不足")}

## 实盘对齐验证

- 今日信号是否真实可交易：{alignment.get("real_tradable_today", "NO")}
- 信号质量评分：{alignment.get("signal_quality_score", 0)}
- 是否存在滑点风险：{alignment.get("has_slippage_risk", "NO")}
- 是否建议放弃交易：{alignment.get("should_abandon_trade", "YES")}
- 对齐原因：{alignment.get("alignment_reason", "数据不足")}

### 实盘过滤后可执行信号

{_format_table(aligned_executable, ["stock_code", "name", "aligned_action", "signal_filled_probability", "signal_quality_score", "entry_price_slippage", "adjusted_entry_price"])}

### 可执行订单包

{_format_table(executable_orders, ["stock_code", "action", "position_ratio", "score", "cycle", "reason"])}

### 可执行标的列表

{_format_table(executable, ["stock_code", "name", "action", "position_size", "master_score", "hold_action", "trigger_reason"])}

### 禁止交易标的列表

{_format_table(blocked, ["stock_code", "name", "action", "position_size", "master_score", "hold_action", "trigger_reason"])}

### 仓位建议

- full：主升/加速 + 龙头，组合仓位80~100%
- medium：启动 + 趋势，组合仓位50~80%
- small：震荡或非龙头，组合仓位10~50%
- zero：退潮或风控闸门关闭，组合仓位0

## 市场周期

- 当前市场周期（强化版）：{decision_cycle.get("market_cycle", cycle.get("market_cycle", "未知"))}
- 当前市场情绪阶段：{decision_cycle.get("market_cycle", "未知")}
- 当前交易建议模式：{cycle.get("trade_mode", "混合")}
- 当前交易模式：{position.get("trading_mode", "稳健（机构）")}
- 推荐仓位比例：{position.get("recommended_position_ratio", 0)}%
- 动量强度：{cycle.get("market_strength_momentum", 0)}
- 趋势强度：{cycle.get("market_strength_trend", 0)}
- 周期置信度：{cycle.get("market_regime_confidence", 0)}%
- 强化周期强度：{decision_cycle.get("cycle_strength", 0)}
- 强化周期置信度：{decision_cycle.get("cycle_stage_confidence", 0)}%
- 风险等级：{position.get("risk_level", 0)}
- 风险动作：{position.get("risk_action", "维持")}

## 最终核心进攻标的

{_format_table(final_attack, ["code", "name", "master_score", "leader_tier", "leader_strength_score", "money_continuation_score"])}

## 龙头股列表

{_format_table(leader_pool, ["code", "name", "momentum_score", "trend_score", "combined_score", "leader_rank", "leader_strength_score"])}

## 趋势股列表

{_format_table(trend_pool.sort_values("trend_score", ascending=False) if not trend_pool.empty else trend_pool, ["code", "name", "trend_score", "combined_score", "continuation_score", "risk_level"])}

## 风险提示

{_format_table(risk_pool.sort_values("risk_level", ascending=False).head(10) if not risk_pool.empty else risk_pool, ["code", "name", "combined_score", "risk_level", "risk_reason"])}

## Top5模拟买入池

{_format_table(top5, ["代码", "名称", "momentum_score", "trend_score", "combined_score", "推荐理由"])}

## 模拟卖出池

{_format_table(sells, ["代码", "名称", "卖出原因"])}

## 继续持有池

{_format_table(holds, ["代码", "名称", "持仓天数", "当前收益率"])}

## 风险观察池

{_format_table(risks, ["代码", "名称", "风险原因"])}
"""
    report_path.write_text(content, encoding="utf-8")
    return report_path


def _write_monthly_report(records: pd.DataFrame, summary: dict, report_dir: Path, target_date: str) -> Path:
    month = target_date[:6]
    month_records = records[records["date"].astype(str).str.startswith(month)].copy() if not records.empty else records
    day5 = pd.to_numeric(month_records.get("day5_return", pd.Series(dtype=float)), errors="coerce").dropna()
    max_dd = pd.to_numeric(month_records.get("max_drawdown", pd.Series(dtype=float)), errors="coerce").dropna()
    backtest_day5 = 0.0
    real_day5 = round(float(day5.mean()), 2) if not day5.empty else 0.0
    deviation = 0.0 if backtest_day5 == 0 else round((real_day5 / backtest_day5 - 1) * 100, 2)
    content = f"""# 月度 Forward Test 统计 {month}

> 全部数据均为【模拟】前向验证，不代表真实交易收益。

- 本月推荐次数：{len(month_records)}
- 本月胜率：{summary['day5_win_rate']}%
- 本月平均收益：{real_day5}%
- 本月最大回撤：{round(float(max_dd.min()), 2) if not max_dd.empty else 0.0}%

## 与 V3 回测对比

- 回测Day5收益：{backtest_day5}%
- 真实Day5收益：{real_day5}%
- 偏差率：{deviation}%

说明：当前 V3 回测报告没有单独输出 Day5 平均收益，因此回测Day5收益暂记为 0，待前向样本积累后只比较真实 Day5 表现。
"""
    path = report_dir / "monthly_forward_report.md"
    path.write_text(content, encoding="utf-8")
    return path


def run_forward_test(target_date: str | None = None) -> Dict:
    target_date = target_date or datetime.now().strftime("%Y%m%d")
    if is_frozen(target_date):
        raise RuntimeError(f"{target_date} 已存在冻结订单，禁止二次生成策略。请读取 frozen_decisions 中的冻结文件。")
    assert_generation_allowed(target_date)

    config = load_config()
    report_dir = PROJECT_ROOT / "reports" / "forward_test"
    report_dir.mkdir(parents=True, exist_ok=True)

    pool_path, pool = _load_latest_pool(target_date, config)
    cycle = update_market_cycle(target_date, pool, PROJECT_ROOT)
    decision = build_trade_decision(target_date, pool, cycle, PROJECT_ROOT)
    execution = build_execution_layer(target_date, decision, PROJECT_ROOT)
    alignment = build_execution_alignment(target_date, pool, decision, execution, PROJECT_ROOT)
    forward_path = report_dir / "forward_test.csv"
    summary_path = report_dir / "forward_summary.csv"
    records = _read_csv(forward_path, FORWARD_COLUMNS)

    records, sells, holds, risks = _update_existing_records(records, pool, target_date)
    records, top5 = _append_today_top5(records, pool, target_date)
    records = records[FORWARD_COLUMNS]
    records.to_csv(forward_path, index=False, encoding="utf-8-sig")

    summary_row = _build_summary(records, target_date)
    summary = _read_csv(summary_path, SUMMARY_COLUMNS)
    summary = summary[summary["date"].astype(str) != target_date] if not summary.empty else summary
    summary = pd.concat([summary, pd.DataFrame([summary_row])], ignore_index=True)
    summary.to_csv(summary_path, index=False, encoding="utf-8-sig")

    report_path = _write_daily_report(target_date, report_dir, top5, sells, holds, risks, cycle, decision, execution, alignment)
    monthly_path = _write_monthly_report(records, summary_row, report_dir, target_date)
    validation = update_forward_validation(target_date, pool, decision, execution, top5, PROJECT_ROOT)
    orders_csv = Path(execution["paths"]["orders_csv"])
    orders_json = Path(execution["paths"]["orders_json"])
    frozen = freeze_order_files(
        target_date,
        orders_csv,
        orders_json if orders_json.exists() else None,
        note="forward_test 在收盘冻结窗口生成当天唯一策略后写入，后续禁止覆盖。",
    )

    return {
        "pool_path": pool_path,
        "forward_path": forward_path,
        "summary_path": summary_path,
        "report_path": report_path,
        "monthly_path": monthly_path,
        "cycle_path": cycle["cycle_path"],
        "cycle_report_path": cycle["cycle_report_path"],
        "market_cycle": cycle["market_cycle"],
        "trade_mode": cycle["trade_mode"],
        "enhanced_market_cycle": decision["cycle"]["market_cycle"],
        "recommended_position_ratio": decision["position"]["recommended_position_ratio"],
        "risk_level": decision["position"]["risk_level"],
        "risk_action": decision["position"]["risk_action"],
        "market_regime_final": decision["final"]["signal"]["market_regime_final"],
        "one_sentence_summary": decision["final"]["signal"]["one_sentence_summary"],
        "risk_gate_action": decision["final"]["risk_gate"]["risk_gate_action"],
        "risk_gate_reason": decision["final"]["risk_gate"]["risk_gate_reason"],
        "can_trade_today": execution["can_trade_today"],
        "no_trade_day": execution["no_trade_day"],
        "trade_intensity": execution["trade_intensity"],
        "order_count": execution["order_count"],
        "max_position_ratio": execution["max_position_ratio"],
        "execution_risk_level": execution["risk_level"],
        "execution_paths": execution["paths"],
        "alignment": {
            "real_tradable_today": alignment["real_tradable_today"],
            "signal_quality_score": alignment["signal_quality_score"],
            "has_slippage_risk": alignment["has_slippage_risk"],
            "should_abandon_trade": alignment["should_abandon_trade"],
            "paths": alignment["paths"],
        },
        "validation": validation,
        "decision_paths": decision["paths"],
        "decision_counts": decision["counts"],
        "top5_count": int(len(top5)),
        "sell_count": int(len(sells)),
        "hold_count": int(len(holds)),
        "risk_count": int(len(risks)),
        "total_observed": summary_row["total_observed"],
        "frozen": frozen,
    }


def main() -> None:
    args = parse_args()
    result = run_forward_test(args.date)
    print("【模拟】Forward Test 已完成")
    print(f"趋势池路径：{result['pool_path']}")
    print(f"前向记录：{result['forward_path']}")
    print(f"汇总统计：{result['summary_path']}")
    print(f"日报路径：{result['report_path']}")
    print(f"月报路径：{result['monthly_path']}")
    print(f"市场周期：{result['market_cycle']}")
    print(f"强化市场周期：{result['enhanced_market_cycle']}")
    print(f"交易建议模式：{result['trade_mode']}")
    print(f"推荐仓位比例：{result['recommended_position_ratio']}%")
    print(f"风险等级：{result['risk_level']}")
    print(f"风险动作：{result['risk_action']}")
    print(f"今日市场一句话总结：{result['one_sentence_summary']}")
    print(f"最终市场裁决：{result['market_regime_final']}")
    print(f"风控闸门：{result['risk_gate_action']}")
    print(f"风控原因：{result['risk_gate_reason']}")
    print(f"今日是否可以交易：{result['can_trade_today']}")
    print(f"今日是否 NO TRADE DAY：{result['no_trade_day']}")
    print(f"今日交易强度：{result['trade_intensity']}")
    print(f"可执行订单数量：{result['order_count']}")
    print(f"最大仓位：{result['max_position_ratio']}%")
    print(f"执行层风险等级：{result['execution_risk_level']}")
    print(f"今日信号是否真实可交易：{result['alignment']['real_tradable_today']}")
    print(f"信号质量评分：{result['alignment']['signal_quality_score']}")
    print(f"是否存在滑点风险：{result['alignment']['has_slippage_risk']}")
    print(f"是否建议放弃交易：{result['alignment']['should_abandon_trade']}")
    print(f"周期日报：{result['cycle_report_path']}")
    print(f"五合一决策报告：{result['decision_paths']['trade_decision_report']}")
    print(f"最终裁决报告：{result['decision_paths']['final_decision_report']}")
    print(f"交易日志：{result['execution_paths']['trade_log']}")
    print(f"执行报告：{result['execution_paths']['execution_report']}")
    print(f"订单CSV：{result['execution_paths']['orders_csv']}")
    print(f"订单JSON：{result['execution_paths']['orders_json']}")
    print(f"冻结订单CSV：{result['frozen']['orders_csv']}")
    print(f"冻结订单JSON：{result['frozen']['orders_json']}")
    print(f"冻结元数据：{result['frozen']['meta_path']}")
    print(f"仓位计划：{result['execution_paths']['position_plan']}")
    print(f"风险检查：{result['execution_paths']['risk_check_report']}")
    print(f"实盘对齐报告：{result['alignment']['paths']['execution_feasibility_report']}")
    print(f"信号质量报告：{result['alignment']['paths']['signal_quality_report']}")
    print(f"Forward Validation：{result['validation']['validation_path']}")
    print(f"Validation 报告：{result['validation']['validation_report']}")
    print(f"验证记录数：{result['validation']['rows']}")
    print(f"已评估记录数：{result['validation']['evaluated_rows']}")
    print(f"【模拟】Top5买入建议数量：{result['top5_count']}")
    print(f"【模拟】卖出建议数量：{result['sell_count']}")
    print(f"【模拟】继续持有数量：{result['hold_count']}")
    print(f"【模拟】风险观察数量：{result['risk_count']}")
    print(f"累计观察股票数：{result['total_observed']}")


if __name__ == "__main__":
    main()

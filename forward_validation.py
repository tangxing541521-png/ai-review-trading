from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

import akshare as ak
import pandas as pd

from strategy.trend_core import _fetch_stock_history


VALIDATION_COLUMNS = [
    "date",
    "eval_date",
    "validation_day",
    "market_regime_final",
    "master_score",
    "master_score_mean",
    "allow_trade",
    "no_trade_day",
    "recommended_codes",
    "recommended_names",
    "recommended_base_prices",
    "leader_codes",
    "leader_names",
    "position_advice",
    "recommended_return",
    "index_return",
    "win_rate",
    "excess_return",
    "status",
]


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _json_dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def _json_loads(text: str, default):
    try:
        if not text or pd.isna(text):
            return default
        return json.loads(text)
    except Exception:
        return default


def _read_validation(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame(columns=VALIDATION_COLUMNS)
    data = pd.read_csv(path, dtype={"date": str, "eval_date": str})
    for column in VALIDATION_COLUMNS:
        if column not in data.columns:
            data[column] = ""
    return data[VALIDATION_COLUMNS]


def _stock_close(code: str, target_date: str) -> float | None:
    hist = _fetch_stock_history(str(code).zfill(6), target_date)
    if hist.empty or "close" not in hist.columns:
        return None
    close = pd.to_numeric(hist.iloc[-1]["close"], errors="coerce")
    if pd.isna(close):
        return None
    return float(close)


def _index_close(target_date: str, symbol: str = "000001") -> float | None:
    start_date = "20200101"
    try:
        data = ak.index_zh_a_hist(symbol=symbol, period="daily", start_date=start_date, end_date=target_date)
    except Exception:
        try:
            data = ak.stock_zh_index_daily(symbol=f"sh{symbol}")
        except Exception as exc:
            print(f"指数数据获取失败：{exc}")
            return None
    if data is None or data.empty:
        return None
    data = data.rename(columns={"日期": "date", "收盘": "close"})
    if "date" not in data.columns or "close" not in data.columns:
        return None
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data = data.dropna(subset=["date"]).sort_values("date")
    data = data[data["date"].dt.strftime("%Y%m%d") <= target_date]
    if data.empty:
        return None
    close = pd.to_numeric(data.iloc[-1]["close"], errors="coerce")
    if pd.isna(close):
        return None
    return float(close)


def _calc_recommendation_result(row: pd.Series, eval_date: str) -> dict | None:
    base_prices = _json_loads(str(row.get("recommended_base_prices", "")), {})
    if not base_prices:
        return None
    returns = []
    for code, base_price in base_prices.items():
        base = _safe_float(base_price)
        latest = _stock_close(code, eval_date)
        if base > 0 and latest is not None:
            returns.append((latest / base - 1) * 100)
    if not returns:
        return None

    signal_index = _index_close(str(row.get("date", "")))
    eval_index = _index_close(eval_date)
    index_return = 0.0
    if signal_index and eval_index:
        index_return = (eval_index / signal_index - 1) * 100

    avg_return = sum(returns) / len(returns)
    win_rate = sum(1 for item in returns if item > 0) / len(returns) * 100
    return {
        "eval_date": eval_date,
        "recommended_return": round(avg_return, 2),
        "index_return": round(index_return, 2),
        "win_rate": round(win_rate, 2),
        "excess_return": round(avg_return - index_return, 2),
        "status": "evaluated",
    }


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


def _write_report(path: Path, validation: pd.DataFrame) -> None:
    evaluated = validation[validation["status"] == "evaluated"].copy()
    if evaluated.empty:
        summary = {
            "days": 0,
            "avg_return": 0.0,
            "avg_index": 0.0,
            "avg_excess": 0.0,
            "avg_win_rate": 0.0,
        }
    else:
        summary = {
            "days": int(len(evaluated)),
            "avg_return": round(float(pd.to_numeric(evaluated["recommended_return"], errors="coerce").mean()), 2),
            "avg_index": round(float(pd.to_numeric(evaluated["index_return"], errors="coerce").mean()), 2),
            "avg_excess": round(float(pd.to_numeric(evaluated["excess_return"], errors="coerce").mean()), 2),
            "avg_win_rate": round(float(pd.to_numeric(evaluated["win_rate"], errors="coerce").mean()), 2),
        }

    content = f"""# Forward Validation 验证报告

> Phase 7 冻结策略，只记录、统计、分析，不优化。

## 验证摘要

- 已评估交易日：{summary['days']}
- 推荐股票平均涨跌幅：{summary['avg_return']}%
- 指数平均涨跌幅：{summary['avg_index']}%
- 平均超额收益：{summary['avg_excess']}%
- 平均胜率：{summary['avg_win_rate']}%

## 最近记录

{_format_table(validation, ['date', 'eval_date', 'market_regime_final', 'master_score', 'allow_trade', 'recommended_return', 'index_return', 'win_rate', 'excess_return', 'status'], 10)}
"""
    path.write_text(content, encoding="utf-8")


def update_forward_validation(
    target_date: str,
    pool: pd.DataFrame,
    decision: Dict,
    execution: Dict,
    top5: pd.DataFrame,
    project_root: Path,
    max_days: int = 10,
) -> Dict:
    """Phase 7 前向验证：只记录和回填表现，不新增策略逻辑。"""
    validation_path = project_root / "forward_validation.csv"
    report_path = project_root / "validation_report.md"
    validation = _read_validation(validation_path)

    if not validation.empty:
        for idx, row in validation.iterrows():
            if str(row.get("status", "")) == "evaluated":
                continue
            if str(row.get("date", "")) >= target_date:
                continue
            result = _calc_recommendation_result(row, target_date)
            if result:
                for key, value in result.items():
                    validation.at[idx, key] = value

    final_signal = decision["final"]["signal"]
    final_stocks = decision["final"]["stocks"].copy()
    leaders = decision.get("leaders", pd.DataFrame()).copy()

    recommended = top5.copy()
    recommended_codes = []
    recommended_names = []
    base_prices = {}
    if not recommended.empty:
        pool_map = pool.copy()
        pool_map["code"] = pool_map["code"].astype(str).str.zfill(6)
        pool_map = pool_map.set_index("code").to_dict("index")
        for _, item in recommended.iterrows():
            code = str(item.get("代码", item.get("code", ""))).zfill(6)
            if not code or code == "000000":
                continue
            recommended_codes.append(code)
            recommended_names.append(str(item.get("名称", item.get("name", ""))))
            close_price = _safe_float(pool_map.get(code, {}).get("close"))
            if close_price > 0:
                base_prices[code] = round(close_price, 4)

    leader_codes = []
    leader_names = []
    if not leaders.empty and "is_leader" in leaders.columns:
        leader_view = leaders[leaders["is_leader"].astype(bool)].head(10)
        for _, item in leader_view.iterrows():
            leader_codes.append(str(item.get("code", "")).zfill(6))
            leader_names.append(str(item.get("name", "")))

    validation_day = 1
    if not validation.empty:
        existing_dates = sorted(set(validation["date"].astype(str).tolist()))
        if target_date not in existing_dates:
            validation_day = min(len(existing_dates) + 1, max_days)
        else:
            current = validation[validation["date"].astype(str) == target_date]
            validation_day = int(_safe_float(current.iloc[-1].get("validation_day"), 1)) if not current.empty else 1

    today_row = {
        "date": target_date,
        "eval_date": "",
        "validation_day": validation_day,
        "market_regime_final": final_signal.get("market_regime_final", ""),
        "master_score": final_signal.get("top_master_score", 0),
        "master_score_mean": final_signal.get("master_score_mean", 0),
        "allow_trade": execution.get("can_trade_today", "NO"),
        "no_trade_day": execution.get("no_trade_day", "YES"),
        "recommended_codes": _json_dumps(recommended_codes),
        "recommended_names": _json_dumps(recommended_names),
        "recommended_base_prices": _json_dumps(base_prices),
        "leader_codes": _json_dumps(leader_codes),
        "leader_names": _json_dumps(leader_names),
        "position_advice": f"{execution.get('market_regime_final', '')}; max_position={execution.get('max_position_ratio', 0)}%",
        "recommended_return": "",
        "index_return": "",
        "win_rate": "",
        "excess_return": "",
        "status": "pending",
    }

    validation = validation[validation["date"].astype(str) != target_date] if not validation.empty else validation
    validation = pd.concat([validation, pd.DataFrame([today_row])], ignore_index=True)
    validation = validation.sort_values("date").tail(max_days).reset_index(drop=True)
    validation.to_csv(validation_path, index=False, encoding="utf-8-sig")
    _write_report(report_path, validation)

    return {
        "validation_path": validation_path,
        "validation_report": report_path,
        "rows": len(validation),
        "evaluated_rows": int((validation["status"] == "evaluated").sum()),
    }

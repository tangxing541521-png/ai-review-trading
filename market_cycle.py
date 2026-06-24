from __future__ import annotations

from pathlib import Path
from typing import Dict

import pandas as pd


CYCLE_COLUMNS = [
    "date",
    "avg_momentum_score",
    "avg_trend_score",
    "combined_score_std",
    "market_cycle",
    "market_strength_momentum",
    "market_strength_trend",
    "market_regime_confidence",
    "momentum_direction",
    "trend_direction",
    "trade_mode",
]


def _safe_mean(df: pd.DataFrame, column: str) -> float:
    series = pd.to_numeric(df.get(column, pd.Series(dtype=float)), errors="coerce").dropna()
    return round(float(series.mean()), 2) if not series.empty else 0.0


def _safe_std(df: pd.DataFrame, column: str) -> float:
    series = pd.to_numeric(df.get(column, pd.Series(dtype=float)), errors="coerce").dropna()
    return round(float(series.std()), 2) if len(series) > 1 else 0.0


def _read_cycle_daily(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=CYCLE_COLUMNS)
    try:
        data = pd.read_csv(path, dtype={"date": str})
    except Exception as exc:
        print(f"读取市场周期文件失败，将重新生成：{exc}")
        return pd.DataFrame(columns=CYCLE_COLUMNS)
    for column in CYCLE_COLUMNS:
        if column not in data.columns:
            data[column] = ""
    return data[CYCLE_COLUMNS]


def _direction(current: float, previous: float, neutral_line: float = 70.0) -> str:
    # 首日没有历史对比时，用中性强度线做临时方向判断，避免引入未来数据。
    if previous is None:
        return "↑" if current >= neutral_line else "↓"
    return "↑" if current >= previous else "↓"


def _classify_cycle(momentum_direction: str, trend_direction: str) -> tuple[str, str]:
    if momentum_direction == "↓" and trend_direction == "↓":
        return "冰点期", "防守"
    if momentum_direction == "↑" and trend_direction == "↓":
        return "启动期", "混合"
    if momentum_direction == "↑" and trend_direction == "↑":
        return "主升期", "进攻"
    return "退潮期", "防守"


def _confidence(
    avg_momentum: float,
    avg_trend: float,
    combined_std: float,
    previous_momentum: float | None,
    previous_trend: float | None,
) -> float:
    if previous_momentum is None or previous_trend is None:
        base = 50.0
        strength_gap = abs(avg_momentum - 70.0) + abs(avg_trend - 70.0)
    else:
        base = 55.0
        strength_gap = abs(avg_momentum - previous_momentum) + abs(avg_trend - previous_trend)

    # 分数离散度越高、强弱变化越明显，周期判断置信度越高。
    value = base + strength_gap * 1.5 + min(combined_std, 20.0) * 0.8
    return round(max(0.0, min(100.0, value)), 2)


def _format_recent_table(data: pd.DataFrame) -> str:
    if data.empty:
        return "暂无市场周期记录。"
    columns = [
        "date",
        "avg_momentum_score",
        "avg_trend_score",
        "combined_score_std",
        "market_cycle",
        "trade_mode",
        "market_regime_confidence",
    ]
    recent = data[columns].tail(10)
    lines = [
        "| 日期 | 动量均值 | 趋势均值 | 综合分标准差 | 市场周期 | 建议模式 | 置信度 |",
        "| --- | ---: | ---: | ---: | --- | --- | ---: |",
    ]
    for _, row in recent.iterrows():
        lines.append(
            "| "
            f"{row['date']} | "
            f"{row['avg_momentum_score']} | "
            f"{row['avg_trend_score']} | "
            f"{row['combined_score_std']} | "
            f"{row['market_cycle']} | "
            f"{row['trade_mode']} | "
            f"{row['market_regime_confidence']}% |"
        )
    return "\n".join(lines)


def _write_cycle_report(path: Path, cycle_daily: pd.DataFrame, latest: Dict) -> None:
    content = f"""# 市场情绪周期报告

## 当前市场状态

- 日期：{latest['date']}
- 当前市场周期：{latest['market_cycle']}
- 当前交易建议模式：{latest['trade_mode']}
- 动量强度：{latest['market_strength_momentum']}
- 趋势强度：{latest['market_strength_trend']}
- 综合分离散度：{latest['combined_score_std']}
- 周期置信度：{latest['market_regime_confidence']}%

## 周期判定依据

- 冰点期：momentum ↓ + trend ↓
- 启动期：momentum ↑ + trend ↓
- 主升期：momentum ↑ + trend ↑
- 退潮期：momentum ↓ + trend ↑

## 最近周期记录

{_format_recent_table(cycle_daily)}
"""
    path.write_text(content, encoding="utf-8")


def update_market_cycle(target_date: str, pool: pd.DataFrame, project_root: Path) -> Dict:
    """根据当天双模型分数计算市场周期，只做状态判断，不参与选股和交易。"""
    cycle_path = project_root / "cycle_daily.csv"
    report_path = project_root / "cycle_report.md"

    avg_momentum = _safe_mean(pool, "momentum_score")
    avg_trend = _safe_mean(pool, "trend_score")
    combined_std = _safe_std(pool, "combined_score")

    cycle_daily = _read_cycle_daily(cycle_path)
    history = cycle_daily[cycle_daily["date"].astype(str) != target_date].copy()
    previous = history.tail(1)
    if previous.empty:
        previous_momentum = None
        previous_trend = None
    else:
        previous_momentum = float(pd.to_numeric(previous["avg_momentum_score"], errors="coerce").iloc[0])
        previous_trend = float(pd.to_numeric(previous["avg_trend_score"], errors="coerce").iloc[0])

    momentum_direction = _direction(avg_momentum, previous_momentum)
    trend_direction = _direction(avg_trend, previous_trend)
    market_cycle, trade_mode = _classify_cycle(momentum_direction, trend_direction)
    confidence = _confidence(avg_momentum, avg_trend, combined_std, previous_momentum, previous_trend)

    row = {
        "date": target_date,
        "avg_momentum_score": avg_momentum,
        "avg_trend_score": avg_trend,
        "combined_score_std": combined_std,
        "market_cycle": market_cycle,
        "market_strength_momentum": avg_momentum,
        "market_strength_trend": avg_trend,
        "market_regime_confidence": confidence,
        "momentum_direction": momentum_direction,
        "trend_direction": trend_direction,
        "trade_mode": trade_mode,
    }

    updated = pd.concat([history, pd.DataFrame([row])], ignore_index=True)
    updated = updated.sort_values("date").reset_index(drop=True)
    updated.to_csv(cycle_path, index=False, encoding="utf-8-sig")
    _write_cycle_report(report_path, updated, row)
    return row | {"cycle_path": cycle_path, "cycle_report_path": report_path}

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

import akshare as ak
import numpy as np
import pandas as pd


REQUIRED_COLUMNS = [
    "date",
    "code",
    "name",
    "momentum_score",
    "trend_score",
    "combined_score",
    "reason",
    "close",
    "pct_chg",
    "amount",
    "turnover",
    "ma5",
    "ma10",
    "ma20",
    "pct_5d",
    "pct_10d",
    "pct_20d",
    "distance_to_20d_high",
    "rank",
]


def _is_beijing_stock(code: str) -> bool:
    """过滤北交所股票，常见代码以 8、4 开头。"""
    raw_code = str(code).strip().lower()
    pure_code = _normalize_code(raw_code)
    return raw_code.startswith("bj") or pure_code.startswith(("8", "4"))


def _normalize_code(code: str) -> str:
    digits = "".join(ch for ch in str(code).strip() if ch.isdigit())
    return digits[-6:].zfill(6)


def _akshare_daily_symbol(code: str) -> str:
    """Sina 日线接口需要带市场前缀的代码。"""
    return f"sh{code}" if code.startswith(("6", "9")) else f"sz{code}"


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _load_stock_universe() -> pd.DataFrame:
    """获取 A 股股票列表。失败时抛出中文错误，便于 main.py 打印。"""
    try:
        spot_df = ak.stock_zh_a_spot()
    except Exception as exc:
        try:
            spot_df = ak.stock_zh_a_spot_em()
        except Exception as fallback_exc:
            raise RuntimeError(f"akshare 获取 A 股股票列表失败：{exc}；备用接口也失败：{fallback_exc}") from fallback_exc

    if spot_df is None or spot_df.empty:
        raise RuntimeError("akshare 获取 A 股股票列表失败：返回数据为空。")

    rename_map = {"代码": "code", "名称": "name"}
    spot_df = spot_df.rename(columns=rename_map)
    if "code" not in spot_df.columns or "name" not in spot_df.columns:
        raise RuntimeError("akshare 返回的股票列表缺少代码或名称字段。")

    universe = spot_df[["code", "name"]].copy()
    universe["raw_code"] = universe["code"].astype(str)
    universe["code"] = universe["code"].map(_normalize_code)
    universe["name"] = universe["name"].astype(str)
    universe = universe[~universe["name"].str.contains("ST", case=False, na=False)]
    universe = universe[~universe["raw_code"].map(_is_beijing_stock)]
    if "成交额" in spot_df.columns:
        universe["spot_amount"] = pd.to_numeric(spot_df["成交额"], errors="coerce").fillna(0)
        # V2：不再要求今日涨幅必须大于 0，只保留成交额预筛。
        universe = universe[universe["spot_amount"] > 1_000_000_000]
    return universe.drop_duplicates("code")[["code", "name"]]


def _fetch_stock_history(code: str, target_date: str) -> pd.DataFrame:
    """获取单只股票最近一段日线，字段缺失时尽量补默认值。"""
    end_dt = datetime.strptime(target_date, "%Y%m%d")
    start_dt = end_dt - timedelta(days=450)
    try:
        hist = ak.stock_zh_a_daily(
            symbol=_akshare_daily_symbol(code),
            start_date=start_dt.strftime("%Y%m%d"),
            end_date=target_date,
            adjust="",
        )
    except Exception:
        try:
            hist = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start_dt.strftime("%Y%m%d"),
                end_date=target_date,
                adjust="",
            )
        except Exception:
            return pd.DataFrame()

    if hist is None or hist.empty:
        return pd.DataFrame()

    rename_map = {
        "日期": "date",
        "收盘": "close",
        "涨跌幅": "pct_chg",
        "成交额": "amount",
        "换手率": "turnover",
    }
    hist = hist.rename(columns=rename_map)
    for col in ["date", "open", "close", "pct_chg", "amount", "turnover"]:
        if col not in hist.columns:
            hist[col] = np.nan

    hist["date"] = pd.to_datetime(hist["date"], errors="coerce")
    hist = hist.dropna(subset=["date"]).sort_values("date")
    hist["close"] = pd.to_numeric(hist["close"], errors="coerce")
    hist["open"] = pd.to_numeric(hist["open"], errors="coerce")
    if hist["pct_chg"].isna().all():
        hist["pct_chg"] = hist["close"].pct_change() * 100
    return hist


def _is_abnormal_name(name: str) -> bool:
    """剔除名称异常或风险标识明显的股票。"""
    text = str(name).strip()
    abnormal_words = ["ST", "*ST", "退", "N", "C"]
    return not text or any(word in text.upper() for word in abnormal_words)


def _score_stock(row: pd.Series) -> tuple[float, str]:
    """按增强后的趋势模型生成 trend_score，满分 100 分。"""
    pct_5d = _safe_float(row.get("pct_5d"))
    pct_10d = _safe_float(row.get("pct_10d"))
    pct_20d = _safe_float(row.get("pct_20d"))
    amount = _safe_float(row.get("amount"))
    pct_chg = _safe_float(row.get("pct_chg"))
    close = _safe_float(row.get("close"))
    ma5 = _safe_float(row.get("ma5"))
    ma10 = _safe_float(row.get("ma10"))
    ma20 = _safe_float(row.get("ma20"))
    distance = _safe_float(row.get("distance_to_20d_high"))

    ma_score = 20.0 if close > ma5 > ma10 > ma20 else 0.0
    trend_score = min(25.0, max(0.0, pct_5d * 0.5 + pct_10d * 0.45 + pct_20d * 0.35))
    high_score = min(15.0, max(0.0, 15.0 * (1 - distance / 10.0)))
    liquidity_score = min(20.0, max(0.0, amount / 3_000_000_000 * 20.0))

    risk_penalty = 0.0
    if pct_5d > 30:
        risk_penalty += 4
    if pct_chg > 8:
        risk_penalty += 3
    if distance > 8:
        risk_penalty += 2
    risk_score = max(0.0, 10.0 - risk_penalty)

    if 1 <= pct_chg <= 5:
        today_score = 10.0
    elif 0 < pct_chg < 1:
        today_score = 6.0
    elif 5 < pct_chg <= 8:
        today_score = 7.0
    else:
        today_score = 3.0

    score = round(min(100.0, ma_score + trend_score + high_score + liquidity_score + risk_score + today_score), 2)
    reason = (
        f"均线{ma_score:.1f} 趋势{trend_score:.1f} "
        f"新高{high_score:.1f} 流动性{liquidity_score:.1f} "
        f"风险{risk_score:.1f} 今日{today_score:.1f}"
    )
    return score, reason


def _rank_score(series: pd.Series, min_score: float, max_score: float, higher_better: bool = True) -> pd.Series:
    """把原始指标转换成相对排名分，避免绝对阈值导致头部分数饱和。"""
    values = pd.to_numeric(series, errors="coerce")
    valid_count = values.notna().sum()
    if valid_count <= 1:
        return pd.Series(max_score, index=series.index)
    ranked = values.rank(method="average", ascending=True if higher_better else False)
    percentile = ((ranked - 1) / (valid_count - 1)).fillna(0)
    return min_score + percentile * (max_score - min_score)


def _amount_rank_score(amount: pd.Series) -> pd.Series:
    """成交额按市场排名分桶：Top10/30/50/其余。"""
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


def _blend_score(*parts: tuple[pd.Series, float]) -> pd.Series:
    """按权重混合多个 30~100 的排名分。"""
    total = None
    for score, weight in parts:
        weighted = pd.to_numeric(score, errors="coerce").fillna(30) * weight
        total = weighted if total is None else total + weighted
    return total.clip(30, 100).round(2)


def _apply_relative_rank_scores(pool: pd.DataFrame, market_base: pd.DataFrame) -> pd.DataFrame:
    """在市场样本上计算双模型排名分，再映射回趋势池；过滤条件不在这里改变。"""
    if pool.empty:
        return pool

    base = market_base.drop_duplicates("code").copy()
    base["amount_rank_component"] = _rank_score(base["amount"], 30.0, 100.0, higher_better=True)
    base["acceleration_5_10"] = (
        pd.to_numeric(base["pct_5d"], errors="coerce")
        - pd.to_numeric(base["pct_10d"], errors="coerce") / 2
    )
    base["acceleration_component"] = _rank_score(base["acceleration_5_10"], 30.0, 100.0, higher_better=True)
    base["near_high_component"] = _rank_score(-pd.to_numeric(base["distance_to_52w_high"], errors="coerce"), 30.0, 100.0, higher_better=True)
    base["volatility_component"] = _rank_score(base["volatility_20d"], 30.0, 100.0, higher_better=True)
    base["turnover_component"] = _rank_score(base["turnover"], 30.0, 100.0, higher_better=True)
    base["vol_turn_component"] = ((base["volatility_component"] + base["turnover_component"]) / 2).round(2)

    base["trend_strength"] = (
        pd.to_numeric(base["pct_5d"], errors="coerce") * 0.30
        + pd.to_numeric(base["pct_10d"], errors="coerce") * 0.30
        + pd.to_numeric(base["pct_20d"], errors="coerce") * 0.40
    )
    base["ma_strength"] = (
        (pd.to_numeric(base["close"], errors="coerce") / pd.to_numeric(base["ma5"], errors="coerce") - 1) * 100
        + (pd.to_numeric(base["ma5"], errors="coerce") / pd.to_numeric(base["ma10"], errors="coerce") - 1) * 100
        + (pd.to_numeric(base["ma10"], errors="coerce") / pd.to_numeric(base["ma20"], errors="coerce") - 1) * 100
    )
    base["ma_component"] = _rank_score(base["ma_strength"], 30.0, 100.0, higher_better=True)
    base["drawdown_component"] = _rank_score(-pd.to_numeric(base["distance_to_52w_high"], errors="coerce"), 30.0, 100.0, higher_better=True)
    base["trend_days_component"] = _rank_score(base["trend_days"], 30.0, 100.0, higher_better=True)
    base["amount_stability_component"] = _rank_score(-pd.to_numeric(base["amount_cv_20d"], errors="coerce"), 30.0, 100.0, higher_better=True)

    base["momentum_score"] = _blend_score(
        (base["amount_rank_component"], 0.30),
        (base["acceleration_component"], 0.30),
        (base["near_high_component"], 0.20),
        (base["vol_turn_component"], 0.20),
    )
    base["trend_score"] = _blend_score(
        (base["ma_component"], 0.30),
        (base["drawdown_component"], 0.30),
        (base["trend_days_component"], 0.20),
        (base["amount_stability_component"], 0.20),
    )
    base["combined_score"] = (
        np.maximum(base["momentum_score"], base["trend_score"]) * 0.60
        + np.minimum(base["momentum_score"], base["trend_score"]) * 0.40
    ).round(2)
    base["reason"] = base.apply(
        lambda row: (
            f"游资:成交{row['amount_rank_component']:.1f}/加速{row['acceleration_component']:.1f}/"
            f"新高{row['near_high_component']:.1f}/波换{row['vol_turn_component']:.1f}; "
            f"机构:均线{row['ma_component']:.1f}/回撤{row['drawdown_component']:.1f}/"
            f"持续{row['trend_days_component']:.1f}/稳定{row['amount_stability_component']:.1f}"
        ),
        axis=1,
    )

    score_cols = [
        "code",
        "momentum_score",
        "trend_score",
        "combined_score",
        "reason",
        "amount_rank_component",
        "acceleration_component",
        "near_high_component",
        "vol_turn_component",
        "ma_component",
        "drawdown_component",
        "trend_days_component",
        "amount_stability_component",
        "trend_strength",
        "ma_strength",
        "distance_to_52w_high",
    ]
    scored = pool.drop(columns=["momentum_score", "trend_score", "combined_score", "reason"], errors="ignore").merge(base[score_cols], on="code", how="left")
    for col in ["momentum_score", "trend_score", "combined_score"]:
        scored[col] = scored[col].fillna(30).round(2)
    scored["reason"] = scored["reason"].fillna("双模型相对排名评分缺失，使用保底分")
    return scored


def _write_score_distribution(project_root: Path, pool: pd.DataFrame, target_date: str) -> None:
    """输出三类评分分布和双模型说明报告。"""
    if pool.empty:
        return

    def distribution(score_col: str) -> pd.DataFrame:
        scores = pd.to_numeric(pool[score_col], errors="coerce")
        bins = [30, 40, 50, 60, 70, 80, 90, 100.0001]
        labels = ["30-40", "40-50", "50-60", "60-70", "70-80", "80-90", "90-100"]
        counts = pd.cut(scores, bins=bins, labels=labels, include_lowest=True, right=False).value_counts().sort_index()
        return pd.DataFrame(
            {
                "date": target_date,
                "score_bucket": counts.index.astype(str),
                "count": counts.values,
                "mean": round(float(scores.mean()), 2),
                "variance": round(float(scores.var()), 2),
                "std": round(float(scores.std()), 2),
                "min": round(float(scores.min()), 2),
                "max": round(float(scores.max()), 2),
            }
        )

    momentum_dist = distribution("momentum_score")
    trend_dist = distribution("trend_score")
    combined_dist = distribution("combined_score")
    momentum_dist.to_csv(project_root / "score_distribution_momentum.csv", index=False, encoding="utf-8-sig")
    trend_dist.to_csv(project_root / "score_distribution_trend.csv", index=False, encoding="utf-8-sig")
    combined_dist.to_csv(project_root / "score_distribution_combined.csv", index=False, encoding="utf-8-sig")

    momentum_mean = float(pd.to_numeric(pool["momentum_score"], errors="coerce").mean())
    trend_mean = float(pd.to_numeric(pool["trend_score"], errors="coerce").mean())
    momentum_count = int((pd.to_numeric(pool["momentum_score"], errors="coerce") > 85).sum())
    trend_count = int((pd.to_numeric(pool["trend_score"], errors="coerce") > 85).sum())
    attack_pool = pool[pd.to_numeric(pool["momentum_score"], errors="coerce") > 85]
    institution_pool = pool[pd.to_numeric(pool["trend_score"], errors="coerce") > 85]
    watch_pool = pool[(pd.to_numeric(pool["momentum_score"], errors="coerce") - pd.to_numeric(pool["trend_score"], errors="coerce")).abs() > 20]
    market_style = "游资风格" if momentum_mean > trend_mean and momentum_count >= trend_count else "机构风格"

    forward_path = project_root / "reports" / "forward_test" / "forward_test.csv"
    profit_text = "暂无足够 Forward Test 收益样本，不能判断哪个模型更赚钱。"
    if forward_path.exists() and forward_path.stat().st_size > 0:
        forward = pd.read_csv(forward_path, dtype={"code": str})
        score_map = pool[["code", "momentum_score", "trend_score"]].rename(
            columns={"momentum_score": "current_momentum_score", "trend_score": "current_trend_score"}
        )
        merged = forward.merge(score_map, on="code", how="left")
        merged["model_bias"] = np.where(
            merged["current_momentum_score"] >= merged["current_trend_score"], "游资模型", "机构模型"
        )
        returns = []
        for col in ["day1_return", "day3_return", "day5_return"]:
            if col in merged.columns:
                temp = merged.dropna(subset=[col]).copy()
                if not temp.empty:
                    temp[col] = pd.to_numeric(temp[col], errors="coerce")
                    returns.append((col, temp.groupby("model_bias")[col].mean().round(2).to_dict()))
        if returns:
            profit_text = "；".join(f"{col}: {value}" for col, value in returns)

    def md_table(data: pd.DataFrame, cols: list[str], max_rows: int = 10) -> str:
        if data.empty:
            return "暂无数据"
        view = data[cols].head(max_rows).fillna("")
        rows = [[str(value) for value in row] for row in view.to_numpy().tolist()]
        widths = [max(len(col), *(len(row[idx]) for row in rows)) for idx, col in enumerate(cols)]
        header = "| " + " | ".join(col.ljust(widths[idx]) for idx, col in enumerate(cols)) + " |"
        sep = "| " + " | ".join("-" * widths[idx] for idx in range(len(cols))) + " |"
        body = ["| " + " | ".join(row[idx].ljust(widths[idx]) for idx in range(len(cols))) + " |" for row in rows]
        return "\n".join([header, sep, *body])

    comparison = pd.DataFrame(
        [
            {
                "model": "游资模型 momentum_score",
                "mean": round(float(pool["momentum_score"].mean()), 2),
                "variance": round(float(pool["momentum_score"].var()), 2),
                "std": round(float(pool["momentum_score"].std()), 2),
                "gt85_count": momentum_count,
            },
            {
                "model": "机构模型 trend_score",
                "mean": round(float(pool["trend_score"].mean()), 2),
                "variance": round(float(pool["trend_score"].var()), 2),
                "std": round(float(pool["trend_score"].std()), 2),
                "gt85_count": trend_count,
            },
            {
                "model": "综合分 combined_score",
                "mean": round(float(pool["combined_score"].mean()), 2),
                "variance": round(float(pool["combined_score"].var()), 2),
                "std": round(float(pool["combined_score"].std()), 2),
                "gt85_count": int((pool["combined_score"] > 85).sum()),
            },
        ]
    )

    report = f"""# 双模型评分报告 {target_date}

## 当前市场风格

当前市场更偏：{market_style}

- 游资模型均值：{momentum_mean:.2f}
- 机构模型均值：{trend_mean:.2f}
- 游资主攻池数量：{momentum_count}
- 机构趋势池数量：{trend_count}
- 两者差值大于 20 的观察池数量：{len(watch_pool)}

## 哪个模型更赚钱

{profit_text}

说明：本模块没有修改交易执行逻辑，也没有新增双路交易回测。模型赚钱能力只能在 Forward Test 样本积累后，按实际收益字段归因统计。

## 两者分布对比图（均值/方差）

{md_table(comparison, ["model", "mean", "variance", "std", "gt85_count"], 20)}

## 游资主攻池 momentum_score > 85

{md_table(attack_pool, ["code", "name", "momentum_score", "trend_score", "combined_score"], 20)}

## 机构趋势池 trend_score > 85

{md_table(institution_pool, ["code", "name", "momentum_score", "trend_score", "combined_score"], 20)}

## 观察池 abs(momentum_score - trend_score) > 20

{md_table(watch_pool, ["code", "name", "momentum_score", "trend_score", "combined_score"], 20)}
"""
    (project_root / "dual_model_report.md").write_text(report, encoding="utf-8")


def _build_stock_record(item: tuple[str, str], target_date: str, min_amount: float) -> tuple[dict | None, dict | None]:
    """处理单只股票，返回趋势池记录和原始行情记录。"""
    raw_code, name = item
    code = _normalize_code(raw_code)
    if len(code) != 6 or _is_abnormal_name(name):
        return None, None

    hist = _fetch_stock_history(code, target_date)
    if len(hist) < 21:
        return None, None

    latest = hist.iloc[-1].copy()
    trade_date = latest["date"].strftime("%Y%m%d")
    if trade_date > target_date:
        return None, None

    close_series = pd.to_numeric(hist["close"], errors="coerce")
    open_series = pd.to_numeric(hist["open"], errors="coerce")
    latest["ma5"] = close_series.rolling(5).mean().iloc[-1]
    latest["ma10"] = close_series.rolling(10).mean().iloc[-1]
    latest["ma20"] = close_series.rolling(20).mean().iloc[-1]
    latest["pct_5d"] = (close_series.iloc[-1] / close_series.iloc[-6] - 1) * 100 if len(close_series) >= 6 else np.nan
    latest["pct_10d"] = (close_series.iloc[-1] / close_series.iloc[-11] - 1) * 100 if len(close_series) >= 11 else np.nan
    latest["pct_20d"] = (close_series.iloc[-1] / close_series.iloc[-21] - 1) * 100 if len(close_series) >= 21 else np.nan
    high_20d = close_series.tail(20).max()
    latest["distance_to_20d_high"] = (high_20d / close_series.iloc[-1] - 1) * 100 if close_series.iloc[-1] else np.nan
    high_52w = close_series.tail(252).max()
    latest["distance_to_52w_high"] = (high_52w / close_series.iloc[-1] - 1) * 100 if close_series.iloc[-1] else np.nan
    amount_series = pd.to_numeric(hist["amount"], errors="coerce")
    latest["volatility_20d"] = close_series.pct_change().tail(20).std() * 100
    amount_mean_20d = amount_series.tail(20).mean()
    latest["amount_cv_20d"] = amount_series.tail(20).std() / amount_mean_20d if amount_mean_20d else np.nan
    ma5_series = close_series.rolling(5).mean()
    ma10_series = close_series.rolling(10).mean()
    ma20_series = close_series.rolling(20).mean()
    trend_days = 0
    for close_value, ma5_value, ma10_value, ma20_value in zip(
        reversed(close_series.tolist()),
        reversed(ma5_series.tolist()),
        reversed(ma10_series.tolist()),
        reversed(ma20_series.tolist()),
    ):
        if pd.notna(close_value) and pd.notna(ma5_value) and pd.notna(ma10_value) and pd.notna(ma20_value) and close_value > ma5_value > ma10_value > ma20_value:
            trend_days += 1
        else:
            break
    latest["trend_days"] = trend_days

    close = _safe_float(latest.get("close"))
    open_price = _safe_float(latest.get("open"))
    pct_chg = _safe_float(latest.get("pct_chg"))
    amount = _safe_float(latest.get("amount"))
    ma5 = _safe_float(latest.get("ma5"))
    ma10 = _safe_float(latest.get("ma10"))
    ma20 = _safe_float(latest.get("ma20"))
    pct_5d = _safe_float(latest.get("pct_5d"))
    pct_10d = _safe_float(latest.get("pct_10d"))
    pct_20d = _safe_float(latest.get("pct_20d"))
    distance_to_high = _safe_float(latest.get("distance_to_20d_high"), 100)
    distance_to_52w_high = _safe_float(latest.get("distance_to_52w_high"), 100)
    volatility_20d = _safe_float(latest.get("volatility_20d"))
    amount_cv_20d = _safe_float(latest.get("amount_cv_20d"))
    trend_days = _safe_float(latest.get("trend_days"))
    turnover = _safe_float(latest.get("turnover"))
    big_bear_candle = open_price > 0 and close < open_price * 0.97 and pct_chg < -3

    quote_record = {
        "date": trade_date,
        "code": code,
        "name": name,
        "close": round(close, 2),
        "pct_chg": round(pct_chg, 2),
        "turnover": round(turnover, 2),
        "amount": round(amount, 2),
        "ma5": round(ma5, 2),
        "ma10": round(ma10, 2),
        "ma20": round(ma20, 2),
        "pct_5d": round(pct_5d, 2),
        "pct_10d": round(pct_10d, 2),
        "pct_20d": round(pct_20d, 2),
        "distance_to_20d_high": round(distance_to_high, 2),
        "distance_to_52w_high": round(distance_to_52w_high, 2),
        "volatility_20d": round(volatility_20d, 4),
        "amount_cv_20d": round(amount_cv_20d, 4),
        "trend_days": int(trend_days),
    }

    if not (
        amount > min_amount
        and close > ma5
        and ma5 > ma10
        and ma10 > ma20
        and pct_5d > 5
        and pct_10d > 10
        and pct_20d > 15
        and distance_to_high <= 10
        and pct_5d <= 35
        and not big_bear_candle
        and turnover >= 0
    ):
        return None, quote_record

    pool_record = {
        "date": trade_date,
        "code": code,
        "name": name,
        "momentum_score": 30.0,
        "trend_score": 30.0,
        "combined_score": 30.0,
        "reason": "待相对排名评分",
        "close": round(close, 2),
        "pct_chg": round(pct_chg, 2),
        "amount": round(amount, 2),
        "turnover": round(turnover, 2),
        "ma5": round(ma5, 2),
        "ma10": round(ma10, 2),
        "ma20": round(ma20, 2),
        "pct_5d": round(pct_5d, 2),
        "pct_10d": round(pct_10d, 2),
        "pct_20d": round(pct_20d, 2),
        "distance_to_20d_high": round(distance_to_high, 2),
    }
    return pool_record, quote_record


def build_trend_core_pool(target_date: str, config: Dict, project_root: Path) -> Path:
    """生成趋势核心池 CSV。"""
    try:
        universe = _load_stock_universe()
    except RuntimeError as exc:
        cache_path = project_root / "data" / "raw" / f"daily_quotes_{target_date}.csv"
        if not cache_path.exists():
            cached_files = sorted((project_root / "data" / "raw").glob("daily_quotes_*.csv"), reverse=True)
            cache_path = cached_files[0] if cached_files else cache_path
        if not cache_path.exists():
            raise
        print(f"行情列表获取失败，使用本地缓存继续运行：{exc}")
        universe = pd.read_csv(cache_path, dtype={"code": str})[["code", "name"]].drop_duplicates("code")
    records: List[dict] = []
    quote_records: List[dict] = []
    min_amount = float(config.get("min_amount", 1_000_000_000))

    # akshare 的部分底层组件在线程中不稳定，使用进程隔离保证 Windows 下可运行。
    with ProcessPoolExecutor(max_workers=6) as executor:
        items = [(str(row["code"]), str(row["name"])) for _, row in universe.iterrows()]
        futures = [
            executor.submit(_build_stock_record, item, target_date, min_amount)
            for item in items
        ]
        for future in as_completed(futures):
            pool_record, quote_record = future.result()
            if quote_record:
                quote_records.append(quote_record)
            if pool_record:
                records.append(pool_record)

    pool = pd.DataFrame(records)
    if pool.empty:
        pool = pd.DataFrame(columns=REQUIRED_COLUMNS)
    else:
        market_base = pd.DataFrame(quote_records)
        pool = _apply_relative_rank_scores(pool, market_base)
        pool = pool.sort_values(["combined_score", "amount"], ascending=False).head(100).reset_index(drop=True)
        pool["rank"] = pool.index + 1
        pool = pool[REQUIRED_COLUMNS]

    out_dir = project_root / str(config.get("processed_dir", "data/processed"))
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"trend_core_pool_{target_date}.csv"
    pool.to_csv(out_path, index=False, encoding="utf-8-sig")
    _write_score_distribution(project_root, pool, target_date)

    watchlist_path = project_root / "portfolio" / "watchlist.csv"
    watchlist_path.parent.mkdir(parents=True, exist_ok=True)
    pool[["date", "code", "name", "momentum_score", "trend_score", "combined_score", "rank", "reason"]].to_csv(
        watchlist_path, index=False, encoding="utf-8-sig"
    )

    raw_dir = project_root / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(quote_records).to_csv(raw_dir / f"daily_quotes_{target_date}.csv", index=False, encoding="utf-8-sig")
    return out_path

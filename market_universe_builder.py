from __future__ import annotations

import argparse
import time
from concurrent.futures import ProcessPoolExecutor, TimeoutError, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

import akshare as ak
import pandas as pd

from backtest import fetch_history_worker, parse_date
from strategy.trend_core import _is_beijing_stock, _normalize_code


PROJECT_ROOT = Path(__file__).resolve().parent


def _safe_date(value: object) -> str:
    """把 akshare 返回的日期统一成 YYYYMMDD，失败时返回空字符串。"""
    dt = pd.to_datetime(value, errors="coerce")
    if pd.isna(dt):
        return ""
    return dt.strftime("%Y%m%d")


def _normalize_records(df: pd.DataFrame, code_col: str, name_col: str, list_col: str, delist_col: str, source: str) -> pd.DataFrame:
    """兼容不同交易所列表字段，统一成候选股票池字段。"""
    if df is None or df.empty or code_col not in df.columns or name_col not in df.columns:
        return pd.DataFrame(columns=["code", "name", "list_date", "delist_date", "source"])

    out = pd.DataFrame()
    out["code"] = df[code_col].astype(str).map(_normalize_code)
    out["name"] = df[name_col].astype(str)
    out["list_date"] = df[list_col].map(_safe_date) if list_col in df.columns else ""
    out["delist_date"] = df[delist_col].map(_safe_date) if delist_col in df.columns else ""
    out["source"] = source
    return out


def _call_akshare_with_retry(func, label: str, retries: int = 3, sleep_seconds: float = 2.0):
    """AkShare 偶发网络失败时重试，仍失败则交给审计报告记录。"""
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            return func()
        except Exception as exc:
            last_exc = exc
            print(f"{label} 第 {attempt}/{retries} 次失败：{exc}")
            time.sleep(sleep_seconds)
    raise RuntimeError(str(last_exc))


def load_candidate_universe() -> tuple[pd.DataFrame, list[str]]:
    """加载当前沪深股票和沪深退市股票，尽量减少幸存者偏差。"""
    frames: list[pd.DataFrame] = []
    defects: list[str] = []

    try:
        sh = _call_akshare_with_retry(ak.stock_info_sh_name_code, "获取沪市当前股票列表")
        frames.append(_normalize_records(sh, "证券代码", "证券简称", "上市日期", "", "sh_current"))
    except Exception as exc:
        defects.append(f"获取沪市当前股票列表失败：{exc}")

    try:
        sz = _call_akshare_with_retry(ak.stock_info_sz_name_code, "获取深市当前股票列表")
        frames.append(_normalize_records(sz, "A股代码", "A股简称", "A股上市日期", "", "sz_current"))
    except Exception as exc:
        defects.append(f"获取深市当前股票列表失败：{exc}")

    try:
        sh_delist = _call_akshare_with_retry(ak.stock_info_sh_delist, "获取沪市退市股票列表")
        frames.append(_normalize_records(sh_delist, "公司代码", "公司简称", "上市日期", "暂停上市日期", "sh_delisted"))
    except Exception as exc:
        defects.append(f"获取沪市退市股票列表失败：{exc}")

    try:
        sz_delist = _call_akshare_with_retry(ak.stock_info_sz_delist, "获取深市退市股票列表")
        frames.append(_normalize_records(sz_delist, "证券代码", "证券简称", "上市日期", "终止上市日期", "sz_delisted"))
    except Exception as exc:
        defects.append(f"获取深市退市股票列表失败：{exc}")

    if not frames:
        raise RuntimeError("历史股票池构建失败：当前股票列表和退市股票列表都无法获取。")

    universe = pd.concat(frames, ignore_index=True)
    universe = universe[universe["code"].str.len().eq(6)]
    universe = universe[~universe["code"].map(_is_beijing_stock)]
    universe = universe.drop_duplicates("code", keep="first").sort_values("code").reset_index(drop=True)
    return universe, defects


def filter_active_candidates(universe: pd.DataFrame, start_date: str, end_date: str) -> pd.DataFrame:
    """只保留回测区间内可能上市交易的股票，减少无效退市样本请求。"""
    data = universe.copy()
    data["list_num"] = pd.to_numeric(data["list_date"], errors="coerce")
    data["delist_num"] = pd.to_numeric(data["delist_date"], errors="coerce")
    start_num = int(start_date)
    end_num = int(end_date)
    mask = (
        (data["list_num"].isna() | (data["list_num"] <= end_num))
        & (data["delist_num"].isna() | (data["delist_num"] >= start_num))
    )
    return data[mask].drop(columns=["list_num", "delist_num"]).reset_index(drop=True)


def fetch_market_histories(universe: pd.DataFrame, start_date: str, end_date: str, max_workers: int) -> tuple[pd.DataFrame, list[str]]:
    """拉取候选股票历史日线；实际有日线记录的股票才进入每日可交易池。"""
    processed_dir = PROJECT_ROOT / "data" / "processed"
    partial_path = processed_dir / f"market_histories_{start_date}_{end_date}.partial.csv"
    fetch_start = (datetime.strptime(start_date, "%Y%m%d") - timedelta(days=140)).strftime("%Y%m%d")
    records: List[dict] = []
    errors: list[str] = []

    fetched_codes: set[str] = set()
    if partial_path.exists() and partial_path.stat().st_size > 0:
        partial = pd.read_csv(partial_path, dtype={"code": str})
        if not partial.empty:
            partial["date"] = pd.to_datetime(partial["date"], errors="coerce")
            records.extend(partial.dropna(subset=["date"]).to_dict("records"))
            fetched_codes = set(partial["code"].astype(str).str.zfill(6))
            print(f"发现历史股票池临时缓存，已读取股票数：{len(fetched_codes)}")

    pending = universe[~universe["code"].astype(str).str.zfill(6).isin(fetched_codes)]
    items = [(str(row["code"]), str(row["name"])) for _, row in pending.iterrows()]
    print(f"开始构建历史股票池，待拉取股票数：{len(items)}，已缓存股票数：{len(fetched_codes)}")

    batch_size = max(100, max_workers * 25)
    chunk_timeout = 240
    for batch_start in range(0, len(items), batch_size):
        batch = items[batch_start : batch_start + batch_size]
        completed = 0
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(fetch_history_worker, item, fetch_start, end_date): item for item in batch}
            try:
                iterator = as_completed(futures, timeout=chunk_timeout)
                for future in iterator:
                    code, name = futures[future]
                    completed += 1
                    try:
                        rows = future.result()
                        if rows:
                            records.extend(rows)
                    except Exception as exc:
                        errors.append(f"{code} {name} 历史日线获取异常：{exc}")
            except TimeoutError:
                unfinished = [item for future, item in futures.items() if not future.done()]
                for code, name in unfinished:
                    errors.append(f"{code} {name} 历史日线获取超时，已跳过")

        if records:
            temp = pd.DataFrame(records)
            temp.to_csv(partial_path, index=False, encoding="utf-8-sig")
        done = min(batch_start + len(batch), len(items))
        print(f"历史股票池进度：{done}/{len(items)}，本批完成：{completed}/{len(batch)}")

    if not records:
        raise RuntimeError("历史股票池构建失败：没有获取到任何历史日线。")

    histories = pd.DataFrame(records)
    histories["date"] = pd.to_datetime(histories["date"], errors="coerce")
    histories = histories.dropna(subset=["date", "code", "close"]).sort_values(["code", "date"])
    return histories, errors


def build_daily_universe(histories: pd.DataFrame, start_date: str, end_date: str) -> pd.DataFrame:
    """按交易日输出当日实际有行情记录的可交易股票。"""
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    daily = histories[(histories["date"] >= start_dt) & (histories["date"] <= end_dt)].copy()
    daily["date"] = daily["date"].dt.strftime("%Y%m%d")
    return daily[["date", "code", "name"]].drop_duplicates(["date", "code"]).sort_values(["date", "code"])


def write_audit(
    universe: pd.DataFrame,
    histories: pd.DataFrame,
    daily_universe: pd.DataFrame,
    defects: list[str],
    errors: list[str],
    start_date: str,
    end_date: str,
) -> None:
    """生成历史股票池审计报告。"""
    processed_dir = PROJECT_ROOT / "data" / "processed"
    counts = daily_universe.groupby("date")["code"].nunique()
    first_trade = histories.groupby("code")["date"].min().dt.strftime("%Y%m%d")
    last_trade = histories.groupby("code")["date"].max().dt.strftime("%Y%m%d")
    new_count = int(((first_trade >= start_date) & (first_trade <= end_date)).sum())
    removed_count = int(((last_trade >= start_date) & (last_trade < end_date)).sum())
    missing_codes = sorted(set(universe["code"]) - set(histories["code"].astype(str)))
    delisted_candidates = int(universe["source"].astype(str).str.contains("delisted").sum())

    top_counts = counts.reset_index(name="stock_count")
    top_counts["new_stock_count"] = top_counts["date"].map(
        first_trade[(first_trade >= start_date) & (first_trade <= end_date)].value_counts()
    ).fillna(0).astype(int)
    top_counts["removed_stock_count"] = top_counts["date"].map(
        last_trade[(last_trade >= start_date) & (last_trade <= end_date)].value_counts()
    ).fillna(0).astype(int)
    top_counts.to_csv(processed_dir / "market_universe_daily_stats.csv", index=False, encoding="utf-8-sig")

    defect_text = "\n".join(f"- {item}" for item in defects) if defects else "- 无"
    error_preview = "\n".join(f"- {item}" for item in errors[:20]) if errors else "- 无"
    missing_preview = "、".join(missing_codes[:50]) if missing_codes else "无"

    content = f"""# 全市场历史股票池审计

构建区间：{start_date} 至 {end_date}

## 股票池来源

- 当前沪市股票列表：ak.stock_info_sh_name_code
- 当前深市股票列表：ak.stock_info_sz_name_code
- 沪市退市股票列表：ak.stock_info_sh_delist
- 深市退市股票列表：ak.stock_info_sz_delist
- 每日可交易股票：以上候选股票在当日实际存在日线行情记录的股票

## 统计结果

- 候选总股票数：{len(universe)}
- 退市候选股票数：{delisted_candidates}
- 有历史行情股票数：{histories['code'].nunique()}
- 缺失股票数：{len(missing_codes)}
- 每日股票数最小值：{int(counts.min()) if not counts.empty else 0}
- 每日股票数最大值：{int(counts.max()) if not counts.empty else 0}
- 每日股票数平均值：{round(float(counts.mean()), 2) if not counts.empty else 0}
- 区间内新增股票数：{new_count}
- 区间内疑似退市或停止交易股票数：{removed_count}

## 接口缺陷记录

{defect_text}

## 历史行情获取异常样例

{error_preview}

## 缺失股票样例

{missing_preview}

## 审计结论

本次股票池不再使用单日当前快照，而是使用当前沪深股票列表叠加沪深退市列表，再以每日实际日线行情记录确认当日可交易股票。它比 V2 的 `daily_quotes_20260622.csv` 当前快照更接近历史全市场股票池，能显著降低幸存者偏差。

仍然存在的缺陷：

1. AkShare 未提供完全可靠的任意历史日期全市场成分列表，本模块用“候选列表 + 历史日线存在性”近似。
2. 历史 ST 状态无法逐日还原，不能精确执行“当日非 ST”过滤。
3. 停牌、涨跌停不可成交、手续费、滑点仍未纳入。
4. 如果某些退市股票历史日线接口无法返回，仍会残留部分幸存者偏差。
"""
    (PROJECT_ROOT / "universe_audit.md").write_text(content, encoding="utf-8")


def build_market_universe(start_date: str, end_date: str, max_workers: int) -> None:
    processed_dir = PROJECT_ROOT / "data" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    raw_universe, defects = load_candidate_universe()
    universe = filter_active_candidates(raw_universe, start_date, end_date)
    universe.to_csv(processed_dir / "market_universe_candidates.csv", index=False, encoding="utf-8-sig")

    histories, errors = fetch_market_histories(universe, start_date, end_date, max_workers)
    histories_path = processed_dir / f"market_histories_{start_date}_{end_date}.csv"
    histories.to_csv(histories_path, index=False, encoding="utf-8-sig")

    daily_universe = build_daily_universe(histories, start_date, end_date)
    daily_universe.to_csv(processed_dir / "market_universe_daily.csv", index=False, encoding="utf-8-sig")

    write_audit(universe, histories, daily_universe, defects, errors, start_date, end_date)
    print(f"候选股票池：{processed_dir / 'market_universe_candidates.csv'}")
    print(f"历史行情缓存：{histories_path}")
    print(f"每日股票池：{processed_dir / 'market_universe_daily.csv'}")
    print(f"股票池审计报告：{PROJECT_ROOT / 'universe_audit.md'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="构建全市场历史股票池")
    parser.add_argument("--start", default="2026-04-01", help="开始日期，格式 YYYY-MM-DD 或 YYYYMMDD")
    parser.add_argument("--end", default="2026-06-22", help="结束日期，格式 YYYY-MM-DD 或 YYYYMMDD")
    parser.add_argument("--max-workers", type=int, default=6, help="并发进程数")
    args = parser.parse_args()

    build_market_universe(parse_date(args.start), parse_date(args.end), args.max_workers)


if __name__ == "__main__":
    main()

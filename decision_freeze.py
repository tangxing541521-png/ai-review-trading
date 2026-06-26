from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd

from system_clock import assert_generation_allowed


PROJECT_ROOT = Path(__file__).resolve().parent
FROZEN_DIR = PROJECT_ROOT / "frozen_decisions"
DISCLAIMER = "仅供学习研究和模拟验证，不构成投资建议；冻结订单不代表真实交易指令。"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_orders_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    return pd.read_csv(path, dtype={"stock_code": str})


def frozen_paths(target_date: str) -> dict[str, Path]:
    FROZEN_DIR.mkdir(parents=True, exist_ok=True)
    return {
        "csv": FROZEN_DIR / f"orders_{target_date}.csv",
        "json": FROZEN_DIR / f"orders_{target_date}.json",
        "report": FROZEN_DIR / f"final_report_{target_date}.md",
        "meta": FROZEN_DIR / f"decision_meta_{target_date}.json",
    }


def is_frozen(target_date: str) -> bool:
    paths = frozen_paths(target_date)
    return paths["json"].exists() or paths["csv"].exists()


def _orders_to_packets(orders: pd.DataFrame) -> list[dict]:
    if orders.empty:
        return []
    clean = orders.copy().fillna("")
    if "stock_code" in clean.columns:
        clean["stock_code"] = clean["stock_code"].astype(str).str.zfill(6)
    return clean.to_dict(orient="records")


def _write_orders_json(target_date: str, orders: pd.DataFrame, out_path: Path, source_order_file: Path) -> Path:
    payload = {
        "date": target_date,
        "is_frozen": True,
        "frozen_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_order_file": str(source_order_file),
        "order_count": int(len(orders)),
        "orders": _orders_to_packets(orders),
        "disclaimer": DISCLAIMER,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def _load_meta(path: Path, target_date: str) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {
        "date": target_date,
        "freeze_time": "",
        "data_snapshot_time": "",
        "mode": "Trading Mode",
        "is_frozen": True,
        "source_order_file": "",
        "hash": "",
        "json_hash": "",
        "csv_hash": "",
        "note": "历史冻结文件存在，但元数据缺失；系统按只读冻结处理。",
        "disclaimer": DISCLAIMER,
    }


def _ensure_json_sidecar(target_date: str, paths: dict[str, Path]) -> None:
    """兼容早期只冻结 CSV 的日期：只补 JSON 侧车文件，不覆盖原订单。"""
    if paths["json"].exists() or not paths["csv"].exists():
        return
    orders = _read_orders_csv(paths["csv"])
    _write_orders_json(target_date, orders, paths["json"], paths["csv"])


def _write_frozen_report(target_date: str, order_path: Path, meta: dict) -> Path:
    orders = _read_orders_csv(order_path)
    order_count = int(len(orders))
    buy_orders = orders[orders.get("action", "") == "BUY"] if not orders.empty and "action" in orders.columns else pd.DataFrame()
    sell_orders = orders[orders.get("action", "") == "SELL"] if not orders.empty and "action" in orders.columns else pd.DataFrame()
    no_trade = order_count == 0 or buy_orders.empty

    preview_lines = []
    if not orders.empty:
        for _, row in orders.head(10).iterrows():
            code = str(row.get("stock_code", "")).zfill(6)
            action = row.get("action", "")
            ratio = row.get("position_ratio", "")
            score = row.get("score", "")
            reason = row.get("reason", "")
            preview_lines.append(f"- {code} | {action} | 仓位 {ratio} | 分数 {score} | {reason}")
    if not preview_lines:
        preview_lines.append("- 今日无冻结订单。")

    content = f"""# 冻结交易决策 {target_date}

> {DISCLAIMER}

## 冻结状态

- 当前模式：{meta.get("mode", "Trading Mode")}
- 是否已冻结：{meta.get("is_frozen", False)}
- 冻结时间：{meta.get("freeze_time", "")}
- 数据快照时间：{meta.get("data_snapshot_time", "")}
- 订单来源：{meta.get("source_order_file", "")}
- CSV哈希：{meta.get("csv_hash", meta.get("hash", ""))}
- JSON哈希：{meta.get("json_hash", "")}
- 备注：{meta.get("note", "")}

## 冻结订单概览

- 订单总数：{order_count}
- BUY 数量：{len(buy_orders)}
- SELL 数量：{len(sell_orders)}
- 今日是否 NO TRADE DAY：{"YES" if no_trade else "NO"}

## 订单预览

{chr(10).join(preview_lines)}
"""
    report_path = frozen_paths(target_date)["report"]
    report_path.write_text(content, encoding="utf-8")
    return report_path


def freeze_order_files(target_date: str, source_csv: Path, source_json: Path | None = None, note: str | None = None) -> dict:
    """冻结订单文件。已有冻结文件绝不覆盖，保证可复现。"""
    paths = frozen_paths(target_date)
    if paths["json"].exists() or paths["csv"].exists():
        _ensure_json_sidecar(target_date, paths)
        meta = _load_meta(paths["meta"], target_date)
        print("今日订单已冻结，禁止修改历史冻结文件。")
        return {
            "date": target_date,
            "is_new_freeze": False,
            "orders_csv": paths["csv"],
            "orders_json": paths["json"],
            "report_path": paths["report"],
            "meta_path": paths["meta"],
            "meta": meta,
        }

    if not source_csv.exists():
        raise FileNotFoundError(f"未找到订单CSV：{source_csv}")

    shutil.copy2(source_csv, paths["csv"])
    orders = _read_orders_csv(paths["csv"])
    if source_json and source_json.exists():
        shutil.copy2(source_json, paths["json"])
    else:
        _write_orders_json(target_date, orders, paths["json"], source_csv)

    freeze_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    csv_hash = _sha256_file(paths["csv"])
    json_hash = _sha256_file(paths["json"])
    meta = {
        "date": target_date,
        "freeze_time": freeze_time,
        "data_snapshot_time": freeze_time,
        "mode": "Trading Mode",
        "is_frozen": True,
        "source_order_file": str(source_csv),
        "hash": json_hash,
        "json_hash": json_hash,
        "csv_hash": csv_hash,
        "note": note or "策略在收盘冻结窗口生成后永久冻结；夜间信息只允许进入风险标签。",
        "disclaimer": DISCLAIMER,
    }
    paths["meta"].write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_frozen_report(target_date, paths["csv"], meta)
    print("今日交易决策已冻结。")
    return {
        "date": target_date,
        "is_new_freeze": True,
        "orders_csv": paths["csv"],
        "orders_json": paths["json"],
        "report_path": paths["report"],
        "meta_path": paths["meta"],
        "meta": meta,
    }


def freeze_decision(target_date: str | None = None) -> dict:
    target_date = target_date or datetime.now().strftime("%Y%m%d")
    paths = frozen_paths(target_date)
    if is_frozen(target_date):
        _ensure_json_sidecar(target_date, paths)
        meta = _load_meta(paths["meta"], target_date)
        if paths["csv"].exists() and not paths["report"].exists():
            _write_frozen_report(target_date, paths["csv"], meta)
        print("今日订单已冻结，本次只读取冻结结果。")
        return {
            "date": target_date,
            "is_new_freeze": False,
            "orders_csv": paths["csv"],
            "orders_json": paths["json"],
            "report_path": paths["report"],
            "meta_path": paths["meta"],
            "meta": meta,
        }

    assert_generation_allowed(target_date)
    print("今日尚未冻结订单，开始执行收盘唯一策略生成。")
    from forward_test import run_forward_test

    result = run_forward_test(target_date)
    return result["frozen"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 14 决策冻结层 Trading Mode")
    parser.add_argument("--date", help="指定冻结日期，格式 YYYYMMDD；不传则默认今天")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = freeze_decision(args.date)
    print(f"日期：{result['date']}")
    print(f"是否新冻结：{result['is_new_freeze']}")
    print(f"冻结订单CSV：{result['orders_csv']}")
    print(f"冻结订单JSON：{result['orders_json']}")
    print(f"冻结报告：{result['report_path']}")
    print(f"冻结元数据：{result['meta_path']}")
    print(f"订单哈希：{result['meta'].get('hash', '')}")


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
from datetime import datetime, time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
FROZEN_DIR = PROJECT_ROOT / "frozen_decisions"
FREEZE_START = time(15, 20)
FREEZE_END = time(15, 40)


def now_local() -> datetime:
    return datetime.now()


def is_freeze_window(moment: datetime | None = None) -> bool:
    """收盘后固定冻结窗口，窗口外禁止生成新订单。"""
    moment = moment or now_local()
    current = moment.time().replace(second=0, microsecond=0)
    return FREEZE_START <= current <= FREEZE_END


def frozen_order_exists(target_date: str) -> bool:
    return (FROZEN_DIR / f"orders_{target_date}.json").exists() or (FROZEN_DIR / f"orders_{target_date}.csv").exists()


def assert_generation_allowed(target_date: str, moment: datetime | None = None) -> None:
    """只控制新订单生成；已有冻结订单允许随时读取。"""
    moment = moment or now_local()
    today = moment.strftime("%Y%m%d")
    if frozen_order_exists(target_date):
        return
    if target_date != today:
        raise RuntimeError(f"禁止为非今日日期生成新订单：{target_date}。历史结果必须读取已冻结文件。")
    if not is_freeze_window(moment):
        raise RuntimeError(
            f"当前时间 {moment.strftime('%H:%M')} 不在收盘冻结窗口 15:20-15:40，禁止生成新订单。"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 14 系统时钟门禁")
    parser.add_argument("--date", help="检查日期，格式 YYYYMMDD；默认今天")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    target_date = args.date or now_local().strftime("%Y%m%d")
    try:
        assert_generation_allowed(target_date)
        print("允许生成或读取：处于冻结窗口，或今日订单已经冻结。")
    except RuntimeError as exc:
        print(f"禁止生成新订单：{exc}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()

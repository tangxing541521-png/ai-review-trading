from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, scrolledtext


PROJECT_ROOT = Path(__file__).resolve().parent


def _read_csv_rows(path: Path) -> list[dict]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def _latest_row(path: Path) -> dict:
    rows = _read_csv_rows(path)
    return rows[-1] if rows else {}


def _json_list(text: str) -> list[str]:
    try:
        value = json.loads(text or "[]")
        return value if isinstance(value, list) else []
    except Exception:
        return []


def _read_json(path: Path) -> dict:
    if not path.exists() or path.stat().st_size == 0:
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def latest_frozen_date() -> str:
    meta_files = sorted((PROJECT_ROOT / "frozen_decisions").glob("decision_meta_*.json"))
    if meta_files:
        return meta_files[-1].stem.replace("decision_meta_", "")
    return datetime.now().strftime("%Y%m%d")


def _run_command(args: list[str]) -> None:
    completed = subprocess.run(args, cwd=PROJECT_ROOT)
    if completed.returncode != 0:
        raise RuntimeError(f"命令执行失败：{' '.join(args)}")


def run_today_flow(target_date: str | None = None) -> dict:
    target_date = target_date or datetime.now().strftime("%Y%m%d")
    print(f"开始执行 Trading Mode 冻结交易员流程：{target_date}")
    print("第一步：运行 decision_freeze.py")
    _run_command([sys.executable, "-u", "-X", "utf8", "decision_freeze.py", "--date", target_date])

    print("第二步：运行 paper_trading.py")
    _run_command([sys.executable, "-u", "-X", "utf8", "paper_trading.py"])

    print("第三步：生成 final_report.md")
    summary = generate_final_report(target_date)
    print_final_summary(summary)
    return summary


def generate_final_report(target_date: str) -> dict:
    validation = _latest_row(PROJECT_ROOT / "forward_validation.csv")
    master = _latest_row(PROJECT_ROOT / "market_master_signal.csv")
    risk = _latest_row(PROJECT_ROOT / "risk_control_report.csv")
    account = _latest_row(PROJECT_ROOT / "paper_account.csv")
    equity = _latest_row(PROJECT_ROOT / "paper_equity_curve.csv")
    meta_path = PROJECT_ROOT / "frozen_decisions" / f"decision_meta_{target_date}.json"
    meta = _read_json(meta_path)
    positions = [
        row for row in _read_csv_rows(PROJECT_ROOT / "paper_positions.csv")
        if row.get("status") == "holding"
    ]

    recommended = _json_list(validation.get("recommended_names", "[]"))
    leaders = _json_list(validation.get("leader_names", "[]"))
    holdings = [row.get("name") or row.get("stock_code", "") for row in positions]
    frozen_order_path = PROJECT_ROOT / "frozen_decisions" / f"orders_{target_date}.csv"

    summary = {
        "date": target_date,
        "mode": meta.get("mode", "Trading Mode" if frozen_order_path.exists() else "Analysis Mode"),
        "is_frozen": str(bool(meta.get("is_frozen", frozen_order_path.exists()))),
        "freeze_time": meta.get("freeze_time", ""),
        "order_source": str(frozen_order_path if frozen_order_path.exists() else meta.get("source_order_file", "")),
        "market_cycle": master.get("cycle", ""),
        "market_regime_final": validation.get("market_regime_final") or master.get("market_regime_final", ""),
        "allow_trade": validation.get("allow_trade", "NO"),
        "recommended_stocks": "、".join(recommended) if recommended else "暂无",
        "leader_stocks": "、".join(leaders) if leaders else "暂无",
        "position_advice": validation.get("position_advice", ""),
        "risk_level": risk.get("risk_level", ""),
        "total_assets": account.get("total_assets", ""),
        "holdings": "、".join(holdings) if holdings else "无",
        "daily_return": equity.get("daily_return", ""),
        "cumulative_return": equity.get("cumulative_return", ""),
        "report_path": str(PROJECT_ROOT / "final_report.md"),
    }

    content = f"""# AI复盘交易最终日报 {target_date}

> 本报告由一键交易员模式自动生成。系统只做模拟验证，不自动下单，不连接券商。

## 决策冻结

- 当前模式：{summary['mode']}
- 是否已冻结：{summary['is_frozen']}
- 冻结时间：{summary['freeze_time']}
- 订单来源：{summary['order_source']}

## 最终结论

- 当前市场周期：{summary['market_cycle']}
- 市场最终状态：{summary['market_regime_final']}
- 是否允许交易：{summary['allow_trade']}
- 推荐股票：{summary['recommended_stocks']}
- 龙头股票：{summary['leader_stocks']}
- 建议仓位：{summary['position_advice']}
- 风险等级：{summary['risk_level']}
- 当前账户资金：{summary['total_assets']}
- 当前持仓：{summary['holdings']}
- 当日收益：{summary['daily_return']}%
- 累计收益：{summary['cumulative_return']}%

## 报告文件

- Frozen Decision：`frozen_decisions/final_report_{target_date}.md`
- Forward Validation：`validation_report.md`
- Paper Trading：`paper_report.md`
- 资金曲线：`paper_equity_curve.csv`
- Forward Report：`reports/forward_test/forward_report_{target_date}.md`

## 操作纪律

- 禁止修改策略。
- 禁止新增模型。
- 禁止调整参数。
- 禁止自动下单。
- 只执行、记录、复盘。
"""
    (PROJECT_ROOT / "final_report.md").write_text(content, encoding="utf-8")
    return summary


def print_final_summary(summary: dict) -> None:
    print()
    print("当前模式：", summary["mode"])
    print("是否已冻结：", summary["is_frozen"])
    print("冻结时间：", summary["freeze_time"])
    print("订单来源：", summary["order_source"])
    print("今日市场状态：", summary["market_regime_final"])
    print("是否允许交易：", summary["allow_trade"])
    print("推荐股票：", summary["recommended_stocks"])
    print("建议仓位：", summary["position_advice"])
    print("风险等级：", summary["risk_level"])
    print("当前账户资金：", summary["total_assets"])
    print("当前持仓：", summary["holdings"])
    print("今日收益：", f"{summary['daily_return']}%")
    print("累计收益：", f"{summary['cumulative_return']}%")
    print("报告路径：", summary["report_path"])


def open_file(path: Path) -> None:
    if not path.exists():
        messagebox.showwarning("文件不存在", f"未找到文件：{path.name}\n请先运行今日交易员流程。")
        return
    os.startfile(path)


def launch_gui() -> None:
    root = tk.Tk()
    root.title("AI复盘交易 - 一键交易员模式")
    root.geometry("760x520")

    output = scrolledtext.ScrolledText(root, height=18)
    output.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

    def log(text: str) -> None:
        output.insert(tk.END, text + "\n")
        output.see(tk.END)
        root.update_idletasks()

    def run_button() -> None:
        try:
            log("开始运行 Trading Mode 冻结交易员流程，请等待...")
            summary = run_today_flow()
            log("运行完成。")
            for key, value in summary.items():
                log(f"{key}: {value}")
            messagebox.showinfo("完成", "今日交易员流程已完成。")
        except Exception as exc:
            log(f"运行失败：{exc}")
            messagebox.showerror("运行失败", str(exc))

    button_frame = tk.Frame(root)
    button_frame.pack(fill=tk.X, padx=12, pady=(0, 12))

    tk.Button(button_frame, text="运行今日交易员流程", command=run_button, height=2).pack(fill=tk.X, pady=4)
    tk.Button(button_frame, text="打开 paper_report.md", command=lambda: open_file(PROJECT_ROOT / "paper_report.md")).pack(fill=tk.X, pady=4)
    tk.Button(button_frame, text="打开 validation_report.md", command=lambda: open_file(PROJECT_ROOT / "validation_report.md")).pack(fill=tk.X, pady=4)
    tk.Button(button_frame, text="打开 final_report.md", command=lambda: open_file(PROJECT_ROOT / "final_report.md")).pack(fill=tk.X, pady=4)

    root.mainloop()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI复盘交易一键启动器")
    parser.add_argument("--run-today", action="store_true", help="运行今日交易员流程")
    parser.add_argument("--date", help="指定日期，格式 YYYYMMDD")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.run_today:
        run_today_flow(args.date)
    else:
        launch_gui()


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict

import pandas as pd
from jinja2 import Template

from strategy.sim_trade import run_sim_trade
from strategy.trend_core import build_trend_core_pool


PROJECT_ROOT = Path(__file__).resolve().parent


def load_config() -> Dict:
    """读取简单 YAML 配置，避免 MVP 阶段额外依赖 PyYAML。"""
    config_path = PROJECT_ROOT / "config" / "config.yaml"
    config: Dict[str, object] = {}
    for line in config_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip()
        if value.replace(".", "", 1).isdigit():
            config[key.strip()] = float(value) if "." in value else int(value)
        else:
            config[key.strip()] = value
    return config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI复盘交易 MVP")
    parser.add_argument("--date", help="复盘日期，格式 YYYYMMDD，例如 20260621")
    parser.add_argument("--forward-test", action="store_true", help="只运行 V3 前向验证，不执行模拟交易")
    return parser.parse_args()


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    return pd.read_csv(path, dtype={"code": str})


def _to_markdown_table(df: pd.DataFrame, columns: list[str], max_rows: int | None = None) -> str:
    if df.empty:
        return "暂无数据"
    view = df.copy()
    if max_rows:
        view = view.head(max_rows)
    exist_cols = [col for col in columns if col in view.columns]
    if not exist_cols:
        return "暂无数据"
    view = view[exist_cols].fillna("")
    rows = [[str(value) for value in row] for row in view.to_numpy().tolist()]
    widths = [
        max(len(str(col)), *(len(row[index]) for row in rows))
        for index, col in enumerate(exist_cols)
    ]
    header = "| " + " | ".join(str(col).ljust(widths[index]) for index, col in enumerate(exist_cols)) + " |"
    separator = "| " + " | ".join("-" * widths[index] for index in range(len(exist_cols))) + " |"
    body = [
        "| " + " | ".join(row[index].ljust(widths[index]) for index in range(len(exist_cols))) + " |"
        for row in rows
    ]
    return "\n".join([header, separator, *body])


def generate_report(target_date: str, pool_path: Path, sim_result: Dict, config: Dict) -> Path:
    """生成 Markdown 日报。"""
    report_dir = PROJECT_ROOT / str(config.get("report_dir", "reports/daily"))
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"daily_report_{target_date}.md"

    pool = _read_csv(pool_path)
    positions = sim_result["positions"]
    today_trades = sim_result["today_trades"]
    buy_logs = sim_result["buy_logs"]
    equity = sim_result["equity_row"]
    strategy = sim_result["strategy_row"]
    position_analysis = sim_result["position_analysis"]
    previous_assets = sim_result["previous_assets"]

    buys = today_trades[today_trades["side"] == "BUY"] if not today_trades.empty else pd.DataFrame()
    sells = today_trades[today_trades["side"] == "SELL"] if not today_trades.empty else pd.DataFrame()

    template = Template(
        """# AI复盘交易日报 {{ date }}

## 今日趋势核心池
{{ trend_pool }}

## 模拟账户
- 初始资金：{{ initial_cash }} 元
- 现金：{{ cash }} 元
- 持仓市值：{{ market_value }} 元
- 当前总资产：{{ total_assets }} 元
- 今日盈亏：{{ daily_pnl }} 元
- 累计收益率：{{ cumulative_return }}%
- 最大回撤：{{ max_drawdown }}%
- 当前持仓数：{{ holding_count }}

## 账户收益变化
- 今日总资产：{{ total_assets }} 元
- 昨日总资产：{{ previous_assets }} 元
- 今日收益：{{ daily_pnl }} 元
- 今日收益率：{{ daily_return }}%
- 累计收益：{{ cumulative_pnl }} 元
- 累计收益率：{{ cumulative_return }}%

## 持仓盈亏分析
- 盈利股票数量：{{ profit_count }}
- 亏损股票数量：{{ loss_count }}
- 持仓胜率：{{ position_win_rate }}%
- 平均收益率：{{ avg_position_pnl_pct }}%
- 最大盈利：{{ max_profit_pct }}%
- 最大亏损：{{ max_loss_pct }}%

### 持仓盈利前三
{{ top_profit_positions }}

### 持仓亏损前三
{{ top_loss_positions }}

## 今日买入明细
{{ buy_logs }}

## 今日卖出明细
{{ sells }}

## 当前持仓
{{ positions }}

## 策略统计
- 胜率：{{ win_rate }}%
- 平均收益率：{{ avg_pnl_pct }}%
- 最佳交易：{{ best_trade_pct }}%
- 最差交易：{{ worst_trade_pct }}%
- 最大回撤：{{ strategy_max_drawdown }}%

## 明日观察
{{ tomorrow_watch }}
"""
    )

    content = template.render(
        date=target_date,
        trend_pool=_to_markdown_table(pool, ["rank", "code", "name", "momentum_score", "trend_score", "combined_score", "close", "pct_chg", "amount", "reason"], 20),
        initial_cash=config.get("initial_cash", 100000),
        cash=equity["cash"],
        market_value=equity["market_value"],
        total_assets=equity["total_assets"],
        previous_assets=previous_assets,
        daily_pnl=equity["daily_pnl"],
        daily_return=equity["daily_return"],
        cumulative_pnl=round(float(equity["total_assets"]) - float(config.get("initial_cash", 100000)), 2),
        cumulative_return=equity["cumulative_return"],
        max_drawdown=equity["max_drawdown"],
        holding_count=equity["holding_count"],
        profit_count=position_analysis["profit_count"],
        loss_count=position_analysis["loss_count"],
        position_win_rate=position_analysis["position_win_rate"],
        avg_position_pnl_pct=position_analysis["avg_position_pnl_pct"],
        max_profit_pct=position_analysis["max_profit_pct"],
        max_loss_pct=position_analysis["max_loss_pct"],
        top_profit_positions=_to_markdown_table(
            positions.sort_values("pnl", ascending=False) if not positions.empty and "pnl" in positions.columns else positions,
            ["code", "name", "latest_price", "market_value", "pnl", "pnl_pct", "holding_days"],
            3,
        ),
        top_loss_positions=_to_markdown_table(
            positions.sort_values("pnl", ascending=True) if not positions.empty and "pnl" in positions.columns else positions,
            ["code", "name", "latest_price", "market_value", "pnl", "pnl_pct", "holding_days"],
            3,
        ),
        buy_logs=_to_markdown_table(
            buy_logs,
            ["code", "name", "price", "shares", "required_amount", "cash_before", "success", "fail_reason"],
        ),
        sells=_to_markdown_table(sells, ["code", "name", "price", "shares", "amount", "pnl", "pnl_pct", "reason"]),
        positions=_to_markdown_table(
            positions,
            ["code", "name", "buy_price", "shares", "latest_price", "market_value", "pnl", "pnl_pct", "holding_days", "status"],
        ),
        win_rate=strategy["win_rate"],
        avg_pnl_pct=strategy["avg_pnl_pct"],
        best_trade_pct=strategy["best_trade_pct"],
        worst_trade_pct=strategy["worst_trade_pct"],
        strategy_max_drawdown=strategy["max_drawdown"],
        tomorrow_watch=_to_markdown_table(pool, ["rank", "code", "name", "momentum_score", "trend_score", "combined_score", "reason"], 10),
    )
    report_path.write_text(content, encoding="utf-8")
    return report_path


def main() -> None:
    args = parse_args()
    target_date = args.date or datetime.now().strftime("%Y%m%d")
    config = load_config()

    if args.forward_test:
        from forward_test import run_forward_test

        result = run_forward_test(target_date)
        print("【模拟】Forward Test 已完成")
        print(f"前向记录：{result['forward_path']}")
        print(f"汇总统计：{result['summary_path']}")
        print(f"日报路径：{result['report_path']}")
        print(f"月报路径：{result['monthly_path']}")
        print(f"【模拟】Top5买入建议数量：{result['top5_count']}")
        print(f"【模拟】卖出建议数量：{result['sell_count']}")
        print(f"【模拟】继续持有数量：{result['hold_count']}")
        print(f"【模拟】风险观察数量：{result['risk_count']}")
        print(f"累计观察股票数：{result['total_observed']}")
        return

    try:
        pool_path = build_trend_core_pool(target_date, config, PROJECT_ROOT)
    except RuntimeError as exc:
        print(f"行情数据获取失败：{exc}")
        return

    sim_result = run_sim_trade(target_date, pool_path, config, PROJECT_ROOT)
    report_path = generate_report(target_date, pool_path, sim_result, config)
    trend_pool_count = len(_read_csv(pool_path))

    print(f"趋势池文件路径：{pool_path}")
    print(f"日报文件路径：{report_path}")
    print(f"趋势核心池数量：{trend_pool_count}")
    print(f"今日买入数量：{sim_result['buy_count']}")
    print(f"今日卖出数量：{sim_result['sell_count']}")
    print(f"现金：{sim_result['equity_row']['cash']}")
    print(f"持仓市值：{sim_result['equity_row']['market_value']}")
    print(f"当前总资产：{sim_result['equity_row']['total_assets']}")
    print(f"今日收益率：{sim_result['equity_row']['daily_return']}%")
    print(f"累计收益率：{sim_result['equity_row']['cumulative_return']}%")


if __name__ == "__main__":
    main()

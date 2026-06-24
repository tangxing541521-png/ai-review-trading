# 部署与运行

本文档说明如何在 Windows 本地运行 AI复盘交易项目。

## 环境要求

- Windows
- Python 3.10 或更高版本
- 网络可访问 AkShare 数据源

## 安装依赖

在项目根目录执行：

```bash
pip install -r requirements.txt
```

依赖文件：

```text
pandas
akshare
openpyxl
numpy
jinja2
```

## 项目目录

进入项目根目录：

```bash
cd C:\Users\tangxin\Documents\ai复盘交易\ai-review-trading
```

## 每日运行流程

### 1. 运行 Forward Test

```bash
python forward_test.py --date YYYYMMDD
```

例如：

```bash
python forward_test.py --date 20260624
```

如果不传日期：

```bash
python forward_test.py
```

### 2. 运行 Paper Trading

```bash
python paper_trading.py
```

### 3. 查看结果

重点查看：

- `reports/forward_test/forward_report_YYYYMMDD.md`
- `validation_report.md`
- `paper_report.md`
- `paper_equity_curve.csv`

## 回测运行

```bash
python backtest.py
```

回测输出：

- `backtest_report.csv`
- `backtest_report.md`
- `backtest_trades.csv`

## 基础复盘运行

```bash
python main.py --date YYYYMMDD
```

输出：

- `data/processed/trend_core_pool_YYYYMMDD.csv`
- `reports/daily/daily_report_YYYYMMDD.md`

## 每日操作员手册

见根目录：

- `daily_operator.md`

## 常见问题

### AkShare 接口失败

如果 AkShare 接口短暂失败，系统可能使用本地缓存继续运行。

建议：

1. 稍后重试。
2. 确认网络正常。
3. 确认 AkShare 版本可用。

### 订单文件被占用

如果 `orders_YYYYMMDD.csv` 被 Excel 或其他程序打开，可能导致写入失败。

解决方法：

1. 关闭打开该 CSV 的程序。
2. 重新运行 `forward_test.py`。

### 当前没有交易

如果系统输出：

```text
NO TRADE DAY
```

说明当前只做记录，不开仓。这是风控结果，不是运行失败。

## 安全边界

本项目只允许本地模拟：

- 不接券商 API
- 不自动下单
- 不控制同花顺或其他交易软件
- 不提供确定性收益承诺

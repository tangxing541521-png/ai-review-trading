# Source Of Truth

本文件定义系统唯一真相源，后续开发必须遵守。

## Paper Trading

- `portfolio/trades.csv` 是唯一交易流水真相源。
- `portfolio/positions.csv` 只能由 `ledger_rebuilder.py` 根据 trades replay 生成。
- `portfolio/equity_curve.csv` 只能由 `ledger_rebuilder.py` 根据 trades replay 和最新行情生成。
- 如果 `positions.csv` 有股票但 `trades.csv` 没有 BUY，该股票是 orphan position，不进入正式持仓。
- 如果 `trades.csv` 有 BUY 无 SELL，则该股票必须保留为 open position，不允许假装已卖出。

## 行情价格

- `data/raw/daily_quotes_YYYYMMDD.csv` 是估值价格真相源。
- 文件名日期必须等于内部 `date` 字段。
- 如果文件名和内部日期不一致，必须由 sanitizer 隔离或由 health check 标红。
- 不允许静默使用旧价。

## 分析数据

- Market Brain 只读 Data Center 的统一上下文。
- Mainline、Daily AI Report、Decision Center 应优先复用 Market Brain 和 Data Center。
- Dashboard 只读 API，不直接读 CSV。

## 报告与展示

- markdown 报告是展示产物，不是账户真相源。
- 页面不得把旧 markdown 中的资产、持仓或订单当作最新状态。
- 如果报告日期和 Data Center 最新日期不一致，Health Check 必须给出 warning 或 failed。

## 写文件权限边界

允许写：

- `pipeline_runner.py`：写日志、触发编排。
- `data_sanitizer.py`：移动脏数据到 quarantine，备份受保护文件。
- `quote_sync.py`：写 daily quotes。
- `ledger_rebuilder.py`：写 positions/equity/rebuild report。

禁止写：

- Market Brain、Mainline、Decision Center、Trader Agent 不得写交易账本。
- 前端不得写本地 CSV。
- Broker Adapter 在 Mock 模式下不得发送真实委托。

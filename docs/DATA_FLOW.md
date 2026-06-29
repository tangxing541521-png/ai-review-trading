# Data Flow

## 一键 AI 复盘数据流

```mermaid
sequenceDiagram
  participant UI as Dashboard
  participant API as /api/run-pipeline
  participant P as pipeline_runner
  participant M as main.py
  participant Q as quote_sync
  participant L as ledger_rebuilder
  participant D as DataCenter
  participant B as MarketBrain
  participant R as Reports

  UI->>API: POST /api/run-pipeline
  API->>P: create job
  P->>P: preflight health check
  P->>P: sanitize dirty data
  P->>M: python -X utf8 main.py
  M-->>P: trend_core_pool / reports / portfolio artifacts
  P->>Q: sync_latest_quotes_for_trading_date
  Q-->>P: data/raw/daily_quotes_YYYYMMDD.csv
  P->>L: trades replay rebuild
  L-->>P: positions.csv / equity_curve.csv
  P->>D: refresh latest context
  P->>B: refresh Market Brain
  P->>R: refresh Mainline / AI Report / Trader / Broker
  P->>P: final health check
  P-->>UI: job status + full logs
```

## 固定顺序

1. preflight health check
2. sanitize dirty data
3. run `main.py`
4. sync latest quotes
5. trades replay rebuild
6. refresh Data Center
7. refresh Market Brain
8. refresh Mainline
9. refresh AI Report
10. refresh Paper Trading
11. refresh Trader Agent
12. refresh Broker Center
13. final health check

## 价格估值流

`daily_quotes_YYYYMMDD.csv` 是最新价真相源。Paper Trading 估值顺序：

1. `data/raw/daily_quotes_YYYYMMDD.csv`
2. `data/processed/daily_quotes_YYYYMMDD.csv`
3. 全量行情缓存或 MarketHub snapshot
4. `trend_core_pool_YYYYMMDD.csv`
5. `positions.csv` 旧价 fallback
6. 成本价 fallback

如果使用 5 或 6，必须在 `/api/paper/data.debug.fallback_price_codes` 中暴露。

## 页面数据流

Dashboard、Paper Trading、Market、Leaders 等页面只调用 API：

- `/api/market-brain`
- `/api/dashboard`
- `/api/paper/data`
- `/api/leaders`
- `/api/pipeline-health`

页面不得直接读取本地 CSV 或 markdown。

# API Map

所有 API 统一返回：

```json
{
  "success": true,
  "allowed": true,
  "membership_level": "admin",
  "data": {}
}
```

## Core APIs

| API | 读取来源 | 关键返回字段 | 是否写文件 | 调用方 |
| --- | --- | --- | --- | --- |
| `POST /api/run-pipeline` | `pipeline_runner` | `job_id` | 是，间接触发 pipeline | Dashboard |
| `GET /api/job-status/{job_id}` | `job_manager` | `status`, `progress`, `steps`, `message` | 否 | Dashboard |
| `GET /api/pipeline-health` | DataCenter, Paper, Market Brain, Broker | `health_score`, `status`, `checks`, `errors` | 否 | Dashboard / 运维 |
| `POST /api/sanitize-data` | data_sanitizer | `quarantined_files`, `protected_backups` | 是，隔离/备份 | 运维 |
| `GET /api/paper/data` | DataCenter, ledger status | `account`, `positions`, `equity_curve`, `ledger_source` | 否 | PaperTrading |
| `GET /api/market-brain` | DataCenter, emotion/leader engines | `emotion`, `theme`, `leader`, `risk`, `decision` | 否 | Dashboard / AI日报 |
| `GET /api/mainline` | Market Brain / DataCenter | `market_emotion`, `mainlines`, `leader_tiers` | 否 | Mainline |
| `GET /api/daily-ai-report` | Market Brain / DataCenter | `title`, `summary`, `full_report` | 否 | AI日报 |
| `GET /api/ai-decision` | Market Brain, Auction, Realtime | `global_decision`, `decisions`, `stats` | 否 | AI决策页 / Trader |
| `GET /api/trader-agent` | AI Decision, Order Queue | `agent`, `workflow`, `statistics` | 否 | Trader Agent |
| `GET /api/order-queue` | AI Decision, risk gate | `queue_status`, `orders`, `risk_gate` | 否 | Order Queue |
| `GET /api/broker-center` | MockBroker / Broker Health | `connection_status`, `health`, `balance` | 否 | Broker Center |
| `GET /api/leaders` | DataCenter latest trend pool or leader tier | `code`, `name`, `master_score`, `leader_tier` | 否 | 龙头排行榜 |
| `GET /api/dashboard` | DataCenter, Paper, validation/risk files | `market_status`, `allow_trade`, `total_assets` | 否 | 今日市场 |

## API Rules

- Write APIs must never delete historical files directly.
- Read APIs must expose `latest_report_date` when data is date-sensitive.
- If a fallback source is used, it must appear in `debug`.
- If an exception occurs, Pipeline APIs must expose traceback in job status/logs.

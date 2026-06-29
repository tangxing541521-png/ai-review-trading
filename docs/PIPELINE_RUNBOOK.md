# Pipeline Runbook

## Daily Operation

推荐入口：Dashboard 点击“一键AI复盘”。

后端入口：

```bash
POST /api/run-pipeline
GET /api/job-status/{job_id}
```

本地排查入口：

```bash
GET /api/pipeline-health
```

## Pipeline Order

1. Preflight health check
2. Sanitize dirty data
3. Run `python -X utf8 main.py`
4. Sync latest quotes
5. Trades replay rebuild
6. Refresh Data Center
7. Refresh Market Brain
8. Refresh Mainline
9. Refresh Daily AI Report
10. Refresh Paper Trading
11. Refresh Trader Agent
12. Refresh Broker Center
13. Final health check

## Success Criteria

- `health_score >= 90`
- `status = healthy`
- `latest_report_date` 全系统一致
- `quote_sync_status = success`
- `ledger_source = trades replay`
- `ledger_consistent = true`
- `daily_quotes_YYYYMMDD.csv` 文件名日期等于内部 `date`
- Market Brain、AI Report、Paper Trading、Broker Center 均可读

## Failure Handling

如果 Pipeline 失败：

1. 先看 Dashboard Job 详情。
2. 再看 `logs/pipeline.log`。
3. 查看对应：
   - `logs/pipeline_{job_id}_stdout.log`
   - `logs/pipeline_{job_id}_stderr.log`
4. 优先修复第一个 failed step。
5. 禁止手工改 `positions.csv` 或 `equity_curve.csv` 来掩盖问题。

## Dirty Data Handling

`data_sanitizer.py` 只能隔离和备份，不允许直接删除：

- 脏文件移动到 `data/quarantine/YYYYMMDD_HHMMSS/`
- manifest 记录原路径、原因、大小、修改时间
- `trades.csv` 不允许删除
- `positions.csv` 和 `equity_curve.csv` 只能备份

## Common Risks

- `leader_tier.csv` 可能是旧日快照，龙头页必须优先最新趋势池或明确显示来源日期。
- AkShare 子进程可能在产物生成后滞留，Pipeline 以关键产物就绪和最终健康检查为成功标准。
- 成本价 fallback 会让估值失真，必须在 `/api/paper/data.debug` 标记。
- 旧 markdown 报告可能滞后，不能作为账户或持仓真相。

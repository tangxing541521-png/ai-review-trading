# Emotion Cycle Engine 情绪周期引擎

Emotion Cycle Engine 是 Market Brain 的情绪周期判断模块，只做分析层归因，不参与选股、买卖、回测或自动下单。

## 禁止边界

- 不修改策略逻辑。
- 不修改评分逻辑。
- 不修改回测逻辑。
- 不修改交易逻辑。
- 不连接同花顺或券商。
- 不自动下单。
- 不联网，不调用大模型。

## 数据来源

模块只读取本地已有文件：

- `cycle_strength_report.csv`
- `market_master_signal.csv`
- `risk_gate.csv`
- `strategy_health_score.csv`
- `frozen_decisions/orders_*.json`
- `leader_detection.csv`
- `data/processed/trend_core_pool_*.csv`

## 输出结构

```json
{
  "stage": "冰点 / 修复 / 分歧 / 一致 / 高潮 / 退潮",
  "score": 0,
  "stage_reason": [],
  "risk_level": "低 / 中 / 高",
  "trade_mode": "空仓 / 观察 / 轻仓 / 进攻",
  "position_suggestion": "0% / 30% / 60%",
  "next_stage_guess": "可能修复 / 继续退潮 / 进入分歧 / 高潮后风险",
  "warning": []
}
```

## 规则说明

- 如果交易许可为 `NO`，优先判定防守或空仓。
- 如果市场强度低、策略健康分低，判定为退潮或冰点。
- 如果主线热度提升、T1 龙头数量增加，判定为修复。
- 如果高分股集中但风险升高，判定为分歧。
- 如果多个主线高热且风险低，判定为一致。
- 如果高热后风险升高，提示高潮风险。

## 与 Market Brain 的关系

`market_brain.py` 调用 `emotion_cycle_engine.py`，并将结果写入：

```json
{
  "emotion": {
    "stage": "...",
    "score": 0,
    "description": "...",
    "stage_reason": [],
    "risk_level": "...",
    "trade_mode": "...",
    "position_suggestion": "...",
    "next_stage_guess": "...",
    "warning": []
  }
}
```

Dashboard 和 AI日报均从 `/api/market-brain` 或其下游接口读取该统一情绪周期结果。

# Leader Life Cycle Engine 龙头生命周期引擎

Leader Life Cycle Engine 用于判断核心股票当前处于哪个龙头生命周期阶段。它只做分析展示，不参与交易执行。

## 禁止边界

- 不修改策略逻辑。
- 不修改交易逻辑。
- 不修改 Paper Trading。
- 不接券商。
- 不自动下单。
- 不联网。
- 不调用大模型。

## 数据来源

模块只读取本地已有文件：

- `leader_detection.csv`
- `leader_tier.csv`
- `data/processed/trend_core_pool_*.csv`
- `frozen_decisions/orders_*.json`
- `cycle_strength_report.csv`
- `market_master_signal.csv`

## 输出结构

```json
{
  "leaders": [
    {
      "code": "688525",
      "name": "佰维存储",
      "score": 83.93,
      "tier": "T1",
      "life_stage": "分歧期",
      "stage_score": 88,
      "days_in_stage": 3,
      "risk": "中",
      "action": "回避",
      "reason": ["高分T1龙头，趋势与动量双强。"],
      "warning": ["冻结订单整体偏防守，生命周期判断只作观察。"]
    }
  ],
  "summary": "冻结订单偏防守，当前龙头生命周期以观察和回避为主。"
}
```

## 生命周期阶段

- 启动期
- 确认期
- 加速期
- 高潮期
- 分歧期
- 二波期
- 见顶期
- 退潮期

## 规则说明

- 高 score + T1 + 趋势强：确认期或加速期。
- 高 score + 高风险 + 市场退潮：分歧期或见顶期。
- trend_core 多次出现：趋势核心延续。
- 冻结订单全是 `SKIP`：整体偏防守，操作建议降低为观察、减仓或回避。
- 每只股票输出生命周期判断、操作建议、理由和风险提示。

## 与 Market Brain 的关系

`market_brain.py` 调用 `leader_lifecycle_engine.py`，并在 `/api/market-brain` 的 `leader` 字段中加入：

```json
{
  "leader": {
    "lifecycle": [],
    "lifecycle_summary": "",
    "tier_summary": {
      "T1": [],
      "T2": [],
      "trend_core": []
    }
  }
}
```

Dashboard、Mainline 页面和 AI日报均读取该统一生命周期结果。

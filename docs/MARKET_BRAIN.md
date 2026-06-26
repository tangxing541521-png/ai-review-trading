# Market Brain 市场大脑

Market Brain 是 Web2 分析层的统一入口，用于把 Dashboard、主线分析、AI 决策中心、AI 日报中的判断逻辑收敛到一个只读引擎。

## 边界

- 不修改策略逻辑。
- 不修改评分逻辑。
- 不修改回测逻辑。
- 不修改 Paper Trading。
- 不自动下单。
- 不联网，不调用大模型。

## 数据来源

Market Brain 只读取项目已有本地文件：

- `leader_detection.csv`
- `leader_tier.csv`
- `cycle_strength_report.csv`
- `strategy_health_score.csv`
- `data/processed/trend_core_pool_*.csv`
- `frozen_decisions/orders_*.json`

## 输出结构

接口：

```text
GET /api/market-brain
```

统一返回格式：

```json
{
  "success": true,
  "allowed": true,
  "membership_level": "admin",
  "data": {
    "emotion": {
      "stage": "退潮",
      "score": 91.63,
      "description": "市场周期处于退潮，交易权限应以防守为主。"
    },
    "theme": {
      "main_theme": "AI硬件",
      "theme_rank": [
        {"name": "AI硬件", "score": 88.5, "reason": "主题内高分股票数..."}
      ]
    },
    "leader": {
      "top_leaders": [],
      "tier_summary": {
        "T1": [],
        "T2": [],
        "trend_core": []
      }
    },
    "risk": {
      "risk_level": 60,
      "risk_label": "中",
      "warnings": []
    },
    "position": {
      "suggested_position": "0%",
      "reason": "市场风险或周期状态不支持开仓。"
    },
    "decision": {
      "action": "防守",
      "summary": "退潮阶段，主线为AI硬件，建议防守，仓位0%。",
      "watchlist": []
    }
  }
}
```

## 复用关系

以下服务不再各自重复分析，而是复用 Market Brain：

- `mainline_engine.py`
- `decision_center.py`
- `daily_ai_report.py`

这样可以保证 Dashboard、AI日报、主线分析、AI决策中心使用同一套市场状态、主线、风险、仓位和观察名单口径。

## 前端说明

本阶段不新增前端页面。可直接访问后端接口做测试：

```text
http://127.0.0.1:8000/api/market-brain
```

后续如果需要展示独立 Market Brain 页面，只读取该接口，不再重复读取多个分析接口拼判断。

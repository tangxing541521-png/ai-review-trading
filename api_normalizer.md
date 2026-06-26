# API 数据标准化规范

> 本规范只约束 Web2 API 返回格式和前端解析方式，不修改策略、评分、回测或交易逻辑。

## 统一响应格式

除 `/api/health`、`/api/login` 等基础接口外，业务接口统一返回：

```json
{
  "success": true,
  "allowed": true,
  "membership_level": "admin",
  "data": {}
}
```

字段说明：

- `success`：接口是否正常返回。
- `allowed`：当前用户是否有权限查看业务数据。
- `membership_level`：当前用户等级。
- `data`：业务数据。前端统一只从 `response.data` 读取。

## 前端解析规则

前端禁止再混用：

- `res.items`
- `res.leaders`
- `res.result`
- `res.data.data`

统一使用：

```js
const res = await api.xxx()
const businessData = res.data
```

如果 `data` 为空，页面显示：

```text
暂无数据，请先运行今日策略。
```

## 接口规范

### GET /api/dashboard

`data` 为对象：

```json
{
  "market_status": "空仓（防守）",
  "allow_trade": "NO",
  "risk_level": "11.77",
  "position_advice": "空仓（防守）; max_position=0.0%",
  "total_assets": "100000.0",
  "daily_return": "0.0",
  "cumulative_return": "0.0",
  "one_sentence_summary": "空仓（防守）",
  "disclaimer": "..."
}
```

### GET /api/leaders

`data` 为数组：

```json
[
  {
    "code": "688525",
    "name": "佰维存储",
    "master_score": "83.93",
    "leader_tier": "T1（核心龙头）",
    "momentum_score": "89.35",
    "trend_score": "92.15",
    "risk_level": "2.75"
  }
]
```

### GET /api/frozen-orders

`data` 为对象：

```json
{
  "date": "20260625",
  "is_frozen": true,
  "freeze_time": "2026-06-25 14:36:04",
  "order_count": 100,
  "orders": [
    {
      "stock_code": "600105",
      "action": "SKIP",
      "position_ratio": 0.0,
      "score": 86.17,
      "cycle": "退潮期",
      "reason": "market_cycle=退潮；cycle进入退潮"
    }
  ]
}
```

### GET /api/paper/data

`data` 为对象：

```json
{
  "account": {},
  "positions": [],
  "equity_curve": []
}
```

### GET /api/strategy-judge

`data` 为对象：

```json
{
  "health": {},
  "metrics": [],
  "report": "..."
}
```

### GET /api/validation

`data` 为对象：

```json
{
  "title": "Forward Validation 验证结果",
  "content": "...",
  "disclaimer": "..."
}
```

### GET /api/reports/final

`data` 为对象：

```json
{
  "title": "最终日报",
  "content": "...",
  "disclaimer": "..."
}
```

## 权限约定

- `free`：`allowed=false` 时，`data` 可以为空对象或空数组。
- `member`：可查看完整业务数据。
- `admin`：可查看全部业务数据。
- 本地开发无 token 时，后端临时返回 mock admin，避免前端调试出现 `Not authenticated`。

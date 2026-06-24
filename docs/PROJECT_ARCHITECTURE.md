# 项目架构

本文档说明 AI复盘交易项目当前的正式架构。

## 项目结构图

```text
ai-review-trading/
├─ config/
│  └─ config.yaml
├─ data/
│  ├─ raw/
│  └─ processed/
│     └─ trend_core_pool_YYYYMMDD.csv
├─ docs/
│  ├─ PROJECT_ARCHITECTURE.md
│  ├─ DEPLOYMENT.md
│  └─ CHANGELOG.md
├─ portfolio/
│  ├─ watchlist.csv
│  ├─ positions.csv
│  ├─ trades.csv
│  ├─ equity_curve.csv
│  └─ strategy_report.csv
├─ reports/
│  ├─ daily/
│  └─ forward_test/
├─ strategy/
│  ├─ trend_core.py
│  └─ sim_trade.py
├─ backtest.py
├─ forward_test.py
├─ forward_validation.py
├─ market_cycle.py
├─ trade_decision_engine.py
├─ execution_layer.py
├─ execution_alignment_layer.py
├─ paper_trading.py
├─ main.py
├─ daily_operator.md
├─ requirements.txt
└─ README.md
```

## 总体链路

```text
数据层
  -> 趋势层
  -> 龙头层
  -> 周期层
  -> 风控层
  -> 决策层
  -> 订单层
  -> 验证层
  -> Paper Trading层
```

## 数据层

主要文件：

- `strategy/trend_core.py`
- `data/raw/`
- `data/processed/`

作用：

- 使用 AkShare 获取 A 股日线行情。
- 生成每日趋势核心池。
- 输出 `trend_core_pool_YYYYMMDD.csv`。

关键输出：

- `data/processed/trend_core_pool_YYYYMMDD.csv`
- `data/raw/daily_quotes_YYYYMMDD.csv`

## 趋势层

主要文件：

- `strategy/trend_core.py`

作用：

- 计算趋势核心池。
- 输出游资风格 `momentum_score`。
- 输出机构风格 `trend_score`。
- 输出综合分 `combined_score`。

该层负责候选池和评分，不负责真实交易。

## 龙头层

主要文件：

- `trade_decision_engine.py`

作用：

- 从趋势池中识别核心龙头。
- 输出 `leader_rank`。
- 输出 `leader_strength_score`。
- 输出 `leader_tier`。

关键输出：

- `leader_detection.csv`
- `leader_tier.csv`

## 周期层

主要文件：

- `market_cycle.py`
- `trade_decision_engine.py`

作用：

- 记录市场周期状态。
- 生成强化周期判断。
- 输出当前市场状态，例如冰点期、启动期、主升期、加速期、退潮期。

关键输出：

- `cycle_daily.csv`
- `cycle_report.md`
- `cycle_strength_report.csv`

## 风控层

主要文件：

- `trade_decision_engine.py`
- `execution_layer.py`
- `execution_alignment_layer.py`

作用：

- 统一判断是否允许交易。
- 生成风险闸门。
- 判断 NO TRADE DAY。
- 判断订单在真实市场中的可执行性。

关键输出：

- `risk_gate.csv`
- `risk_control_report.csv`
- `risk_check_report.md`
- `execution_feasibility_report.md`
- `signal_quality_report.csv`

## 决策层

主要文件：

- `trade_decision_engine.py`

作用：

- 将游资、机构、周期、龙头、资金行为统一收敛。
- 输出唯一核心结论：今天是否值得参与市场。
- 输出 `market_regime_final`。

关键输出：

- `market_master_signal.csv`
- `final_decision_report.md`
- `trade_decision_report.md`

## 订单层

主要文件：

- `execution_layer.py`

作用：

- 根据最终决策生成模拟订单包。
- 生成 `BUY / SELL / SKIP`。
- 输出仓位比例。
- 输出订单优先级和原因。

关键输出：

- `orders_YYYYMMDD.csv`
- `orders_YYYYMMDD.json`
- `position_plan.csv`
- `trade_log.csv`
- `execution_report.md`

## 验证层

主要文件：

- `forward_test.py`
- `forward_validation.py`
- `backtest.py`

作用：

- 历史回测验证策略历史表现。
- Forward Validation 连续记录未来交易日表现。
- 统计推荐股票涨跌幅、指数涨跌幅、胜率和超额收益。

关键输出：

- `backtest_report.md`
- `backtest_report.csv`
- `forward_validation.csv`
- `validation_report.md`

## Paper Trading层

主要文件：

- `paper_trading.py`

作用：

- 按订单信号进行虚拟账户执行。
- 初始资金 100000。
- 统计如果完全按系统信号执行，账户最终赚多少钱。

关键输出：

- `paper_account.csv`
- `paper_positions.csv`
- `paper_trades.csv`
- `paper_equity_curve.csv`
- `paper_report.md`

## 每日运行关系

```text
python forward_test.py --date YYYYMMDD
  -> 更新趋势池
  -> 更新决策
  -> 更新订单
  -> 更新实盘对齐
  -> 更新 Forward Validation

python paper_trading.py
  -> 读取 forward_validation.csv
  -> 读取 orders_YYYYMMDD.csv
  -> 更新虚拟账户
  -> 更新资金曲线
```

## 禁止事项

当前阶段为验证期：

- 不修改策略逻辑。
- 不修改评分逻辑。
- 不修改交易逻辑。
- 不新增模型。
- 不新增过滤器。
- 不调整参数。

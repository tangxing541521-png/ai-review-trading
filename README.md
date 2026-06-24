# AI复盘交易

AI复盘交易是一个本地 Python A 股复盘、验证和虚拟交易项目。系统目标不是接入真实交易，而是把“趋势核心池 -> 决策 -> 订单生成 -> 前向验证 -> 虚拟账户”串成一个可每日执行、可长期跟踪的模拟交易闭环。

当前项目只做研究、模拟和记录：

- 不接券商 API
- 不自动下单
- 不控制任何交易软件
- 不承诺收益

## 项目目标

1. 每日收盘后自动生成 A 股趋势核心池。
2. 使用游资评分、机构趋势评分、情绪周期、龙头识别和风控决策生成模拟信号。
3. 通过 Order Engine 生成本地订单包。
4. 通过 Forward Validation 记录未来表现。
5. 通过 Paper Trading 验证如果完全按系统信号执行，虚拟账户最终会赚多少钱。

## 系统架构

核心链路：

```text
行情数据
  -> 趋势核心池
  -> 双模型评分
  -> 市场周期
  -> 龙头与风险识别
  -> 最终交易裁决
  -> Order Engine
  -> Execution Alignment
  -> Forward Validation
  -> Paper Trading
```

主要模块：

- `strategy/trend_core.py`：趋势核心池与双模型评分。
- `market_cycle.py`：市场情绪周期记录。
- `trade_decision_engine.py`：统一交易决策与最终市场裁决。
- `execution_layer.py`：订单引擎，生成模拟订单包。
- `execution_alignment_layer.py`：实盘可执行性对齐验证。
- `forward_test.py`：每日前向验证入口。
- `forward_validation.py`：未来交易日表现跟踪。
- `paper_trading.py`：虚拟账户执行与资金曲线。
- `backtest.py`：历史回测验证。

更详细架构见：[docs/PROJECT_ARCHITECTURE.md](docs/PROJECT_ARCHITECTURE.md)

## 安装依赖

```bash
pip install -r requirements.txt
```

依赖尽量保持轻量：

- pandas
- akshare
- openpyxl
- numpy
- jinja2

## 如何运行

### 1. 每日完整执行

```bash
python forward_test.py --date YYYYMMDD
python paper_trading.py
```

例如：

```bash
python forward_test.py --date 20260624
python paper_trading.py
```

### 2. 快速查看每日操作手册

见：[daily_operator.md](daily_operator.md)

### 3. 生成基础复盘日报

```bash
python main.py --date YYYYMMDD
```

## 回测流程

历史回测入口：

```bash
python backtest.py
```

回测相关输出：

- `backtest_report.csv`
- `backtest_report.md`
- `backtest_trades.csv`
- `backtest_v2_report.md`
- `backtest_v3_report.md`

回测用于验证历史表现，不用于自动交易。

## Forward Validation 流程

Forward Validation 从 `forward_test.py` 自动触发。

每日运行：

```bash
python forward_test.py --date YYYYMMDD
```

输出：

- `forward_validation.csv`
- `validation_report.md`

记录内容：

- `market_regime_final`
- `master_score`
- 是否允许交易
- 推荐股票
- 龙头股票
- 建议仓位
- 次日推荐股涨跌幅
- 指数涨跌幅
- 胜率
- 超额收益

未来 10 个交易日内只做记录和统计，不新增策略逻辑。

## Paper Trading 流程

Paper Trading 用于验证如果完全按系统信号执行，虚拟账户最终表现如何。

运行：

```bash
python paper_trading.py
```

输出：

- `paper_account.csv`
- `paper_positions.csv`
- `paper_trades.csv`
- `paper_equity_curve.csv`
- `paper_report.md`

统计内容：

- 总资产
- 累计收益
- 最大回撤
- 胜率
- 盈亏比
- 夏普比率

## 常用输出文件

- `data/processed/trend_core_pool_YYYYMMDD.csv`
- `reports/forward_test/forward_report_YYYYMMDD.md`
- `orders_YYYYMMDD.csv`
- `orders_YYYYMMDD.json`
- `execution_feasibility_report.md`
- `forward_validation.csv`
- `validation_report.md`
- `paper_report.md`
- `paper_equity_curve.csv`

## 文档

- [docs/PROJECT_ARCHITECTURE.md](docs/PROJECT_ARCHITECTURE.md)
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)
- [docs/CHANGELOG.md](docs/CHANGELOG.md)

## 风险提示

本项目所有信号、订单和账户均为模拟结果。任何输出都不构成投资建议，不应直接用于真实交易。

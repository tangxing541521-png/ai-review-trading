# Git 工作流规范

## 目标

GitHub 仓库只保存源码、配置、文档和可复现的项目骨架，不保存每日运行产生的数据文件。

这样做可以让仓库保持干净，避免把大量行情缓存、账户曲线、冻结订单、日志和本地运行结果误提交到远端。

## 平时怎么提交代码

1. 修改源码、配置或文档。
2. 本地运行必要检查，例如：

```powershell
python -m py_compile main.py
```

3. 查看变更：

```powershell
git status
```

4. 只提交源码、配置、文档：

```powershell
git add README.md docs/ strategy/ web2/ *.py
git commit -m "更新说明"
```

5. 推送到 GitHub：

```powershell
git push
```

## 哪些文件不应该提交

以下文件属于本地运行结果，不应该提交：

- `data/raw/`
- `data/cache/`
- `reports/`
- `portfolio/`
- `frozen_decisions/`
- `orders_*.csv`
- `orders_*.json`
- `paper_account.csv`
- `paper_positions.csv`
- `paper_trades.csv`
- `paper_equity_curve.csv`
- `trade_log.csv`
- `strategy_metrics.csv`
- `strategy_health_score.csv`
- `*.log`
- `web2/frontend/node_modules/`
- `web2/frontend/dist/`

这些内容已经写入 `.gitignore`。

## 为什么每日运行数据不上传 GitHub

每日运行数据具有以下特点：

- 会频繁变化。
- 文件数量和体积会持续增加。
- 包含本地模拟账户、冻结订单、日志等运行状态。
- 不是源码，不适合做版本管理。
- 不同电脑重新运行可以再生成。

GitHub 应该保存“如何生成结果”的代码，而不是每天生成出来的结果。

## 新电脑如何 clone 项目

```powershell
git clone <你的仓库地址>
cd ai-review-trading
```

安装 Python 依赖：

```powershell
python -m pip install -r requirements.txt
```

如果使用 Web2 前端，需要安装 Node.js 后执行：

```powershell
cd web2/frontend
npm install
npm run dev
```

启动 Web2 后端：

```powershell
cd web2/backend
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

## 如何重新运行生成本地数据

运行主复盘：

```powershell
python main.py
```

运行前向验证：

```powershell
python forward_test.py
```

运行交易冻结流程：

```powershell
python decision_freeze.py
```

运行虚拟账户：

```powershell
python paper_trading.py
```

运行策略评估：

```powershell
python strategy_judge.py
```

这些命令会重新生成本地数据文件。生成结果会被 `.gitignore` 忽略，不会污染 GitHub 仓库。

## 提交前检查清单

- 没有提交每日行情缓存。
- 没有提交冻结订单。
- 没有提交 Paper Trading 账户结果。
- 没有提交日志文件。
- 没有提交 `node_modules` 或前端构建产物。
- 只提交源码、配置、文档和必要的项目骨架。

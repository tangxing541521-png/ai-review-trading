# AI Review Trading Web 2.0 架构骨架

> 免责声明：本系统仅用于学习研究和模拟验证，不构成任何投资建议，不承诺收益，交易风险自担。

## 当前阶段

本阶段只搭建正式 Web 产品架构骨架，不迁移全部功能，不接支付，不上线部署，不修改原策略系统。

## 技术栈

- 后端：FastAPI
- 前端：Vue3 + Vite
- 数据库：SQLite，本阶段仅初始化元数据表，后续可迁移 MySQL
- 认证：JWT
- UI 风格：深色金融仪表盘，参考 TradingView / 富途 / 同花顺的信息密度与暗色风格

## 目录结构

```text
web2/
├─ backend/
│  ├─ main.py
│  ├─ requirements.txt
│  └─ app/
│     ├─ api/
│     ├─ core/
│     ├─ models/
│     ├─ services/
│     ├─ schemas/
│     └─ database.py
└─ frontend/
   ├─ package.json
   ├─ vite.config.js
   └─ src/
      ├─ main.js
      ├─ App.vue
      ├─ router/
      ├─ views/
      ├─ components/
      └─ assets/
```

## 后端启动

```powershell
cd C:\Users\tangxin\Documents\ai复盘交易\ai-review-trading\web2\backend
C:\Users\tangxin\AppData\Local\Programs\Python\Python312\python.exe -m pip install -r requirements.txt
C:\Users\tangxin\AppData\Local\Programs\Python\Python312\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

健康检查：

```text
http://127.0.0.1:8000/api/health
```

## 前端启动

```powershell
cd C:\Users\tangxin\Documents\ai复盘交易\ai-review-trading\web2\frontend
npm install
npm run dev
```

默认访问：

```text
http://127.0.0.1:5173
```

## 测试账号

- 免费用户：`free / free123`
- 会员用户：`member / member123`
- 管理员：`admin / admin123`

用户数据仍读取项目根目录 `users.json`，当前只做本地模拟。

## 当前 API

- `GET /api/health`：系统状态
- `POST /api/login`：模拟登录并返回 JWT
- `GET /api/dashboard`：市场状态、允许交易、风险等级、当前资产、收益
- `GET /api/reports/final`：读取 `final_report.md`
- `GET /api/paper/account`：读取 `paper_report.md`
- `GET /api/paper/data`：读取 Paper Trading 账户、持仓、资金曲线
- `GET /api/validation`：读取 `validation_report.md`
- `GET /api/leaders`：读取 `leader_tier.csv` 龙头排行榜
- `GET /api/frozen-orders`：读取 `frozen_decisions/orders_*.json`
- `GET /api/strategy-judge`：读取 `strategy_health_score.csv` 和 `strategy_metrics.csv`
- `GET /api/membership`：读取当前用户会员权限
- `GET /api/disclaimer`：读取免责声明

## 权限规则

免费用户：

- 可查看市场状态
- 可查看风险等级
- 可查看免责声明
- 不显示龙头排行榜、冻结订单、完整报告、虚拟账户、验证结果、策略评分

会员用户：

- 可查看完整报告
- 可查看 Paper Trading 账户
- 可查看 Forward Validation 结果
- 可查看龙头排行榜
- 可查看冻结订单
- 可查看 Strategy Judge 策略评分

管理员：

- 当前与会员同等可见全部内容
- 后续可扩展用户管理、运行日志、任务审计

## 禁止事项

- 不修改原策略代码
- 不修改 `forward_test.py`
- 不修改 `paper_trading.py`
- 不接真实支付
- 不接同花顺
- 不自动下单
- 不上线部署

## 正式上线前缺口

- 后端真实用户系统和权限表
- 密码加盐哈希和登录风控
- 支付系统合规审查
- 用户协议、隐私政策、风险揭示书
- 数据库迁移到 MySQL/PostgreSQL
- 服务端审计日志和操作留痕
- 报告生成任务队列
- HTTPS、域名、备份、监控、告警
- 内容合规审核和免责声明强确认

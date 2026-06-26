# 本地 Web App 架构

> 免责声明：本项目仅供学习研究和模拟验证，不构成任何投资建议，不提供真实投顾服务，不承诺收益。

## 架构目标

在不修改策略、评分、回测和交易逻辑的前提下，用 Streamlit 构建一个本地产品原型，把现有脚本输出组织成可视化页面。

## 模块结构

```text
web_app_prototype.py
├─ 登录与会员模拟
│  └─ users.json
├─ 首页仪表盘
│  ├─ market_master_signal.csv
│  ├─ risk_control_report.csv
│  └─ paper_account.csv
├─ 今日市场状态
│  ├─ forward_validation.csv
│  └─ final_report.md
├─ 今日复盘报告
│  ├─ final_report.md
│  └─ reports/forward_test/forward_report_YYYYMMDD.md
├─ Paper Trading 账户
│  ├─ paper_account.csv
│  ├─ paper_positions.csv
│  ├─ paper_trades.csv
│  └─ paper_equity_curve.csv
├─ Forward Validation 结果
│  ├─ forward_validation.csv
│  └─ validation_report.md
├─ 会员权限模拟
│  └─ users.json
└─ 免责声明页面
```

## 数据流

1. 原策略脚本生成 CSV 和 Markdown。
2. Web App 只读取已有结果，不改变策略逻辑。
3. 免费用户看到摘要和风险提示。
4. 会员用户看到完整报告、账户、验证统计和导出入口。
5. 管理员看到用户列表和系统文件状态。

## 页面说明

- 首页仪表盘：聚合市场状态、是否允许交易、风险等级、账户资产。
- 今日市场状态：展示市场周期、最终状态、建议仓位。
- 今日复盘报告：会员看完整 Markdown，免费用户隐藏核心内容。
- Paper Trading 账户：会员可查看虚拟账户表现和当前持仓。
- Forward Validation：会员可查看前向验证样本和报告。
- 会员权限模拟：显示当前账号权限和本地用户列表。
- 免责声明页面：展示产品合规边界。

## 技术边界

- 不上线服务。
- 不接真实支付。
- 不接券商接口。
- 不控制外部交易软件。
- 不修改任何交易执行逻辑。

# Order Engine 风险检查报告

> 本报告只用于【模拟】订单生成前检查，不自动下单。

- 日期：20260624
- 今日是否可交易：NO
- 今日是否 NO TRADE DAY：YES
- 风险等级：14.16
- 周期状态：退潮期
- 风险检查结论：market_cycle=退潮；cycle进入退潮
- 可执行订单数量：0
- 最大仓位：0.0%

## 过滤规则

- market_cycle = 退潮：禁止交易
- continuation_score < threshold：禁止交易
- leader 数量 = 0：禁止交易
- risk_level > 70：禁止交易

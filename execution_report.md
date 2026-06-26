# 交易执行闭环报告

> 本报告只生成【模拟】交易动作，不自动下单，不连接券商。

## 最终执行结论

- 今日是否可以交易：NO
- 今日是否 NO TRADE DAY：YES
- 今日交易强度：0
- 可执行订单数量：0
- 最大仓位：0.0%
- 市场状态：空仓（防守）
- 周期状态：退潮期
- 风险等级：11.77
- 风控原因：market_cycle=退潮；cycle进入退潮

## 可执行订单 Order Packet

| stock_code | action | position_ratio | score | cycle | reason                    |
| ---------- | ------ | -------------- | ----- | ----- | ------------------------- |
| 000021     | SKIP   | 0.0            | 86.17 | 退潮期   | market_cycle=退潮；cycle进入退潮 |
| 000725     | SKIP   | 0.0            | 86.05 | 退潮期   | market_cycle=退潮；cycle进入退潮 |
| 603005     | SKIP   | 0.0            | 84.96 | 退潮期   | market_cycle=退潮；cycle进入退潮 |
| 301308     | SKIP   | 0.0            | 84.65 | 退潮期   | market_cycle=退潮；cycle进入退潮 |
| 600584     | SKIP   | 0.0            | 84.59 | 退潮期   | market_cycle=退潮；cycle进入退潮 |
| 300398     | SKIP   | 0.0            | 84.49 | 退潮期   | market_cycle=退潮；cycle进入退潮 |
| 002371     | SKIP   | 0.0            | 84.21 | 退潮期   | market_cycle=退潮；cycle进入退潮 |
| 001309     | SKIP   | 0.0            | 84.2  | 退潮期   | market_cycle=退潮；cycle进入退潮 |
| 688525     | SKIP   | 0.0            | 83.93 | 退潮期   | market_cycle=退潮；cycle进入退潮 |
| 688072     | SKIP   | 0.0            | 83.61 | 退潮期   | market_cycle=退潮；cycle进入退潮 |
| 301013     | SKIP   | 0.0            | 83.52 | 退潮期   | market_cycle=退潮；cycle进入退潮 |
| 688048     | SKIP   | 0.0            | 83.36 | 退潮期   | market_cycle=退潮；cycle进入退潮 |
| 600105     | SKIP   | 0.0            | 83.34 | 退潮期   | market_cycle=退潮；cycle进入退潮 |
| 002384     | SKIP   | 0.0            | 83.31 | 退潮期   | market_cycle=退潮；cycle进入退潮 |
| 603986     | SKIP   | 0.0            | 83.13 | 退潮期   | market_cycle=退潮；cycle进入退潮 |
| 600522     | SKIP   | 0.0            | 83.12 | 退潮期   | market_cycle=退潮；cycle进入退潮 |
| 600487     | SKIP   | 0.0            | 83.0  | 退潮期   | market_cycle=退潮；cycle进入退潮 |
| 300604     | SKIP   | 0.0            | 82.99 | 退潮期   | market_cycle=退潮；cycle进入退潮 |
| 600246     | SKIP   | 0.0            | 82.92 | 退潮期   | market_cycle=退潮；cycle进入退潮 |
| 688507     | SKIP   | 0.0            | 82.87 | 退潮期   | market_cycle=退潮；cycle进入退潮 |

## 可执行标的列表

暂无数据

## 禁止交易标的列表

| stock_code | name | action | position_size | master_score | hold_action | trigger_reason |
| ---------- | ---- | ------ | ------------- | ------------ | ----------- | -------------- |
| 000021     | 深科技  | SKIP   | zero          | 86.17        | 清仓          | 退潮周期，强制SKIP    |
| 000725     | 京东方Ａ | SKIP   | zero          | 86.05        | 清仓          | 退潮周期，强制SKIP    |
| 603005     | 晶方科技 | SKIP   | zero          | 84.96        | 清仓          | 退潮周期，强制SKIP    |
| 301308     | 江波龙  | SKIP   | zero          | 84.65        | 清仓          | 退潮周期，强制SKIP    |
| 600584     | 长电科技 | SKIP   | zero          | 84.59        | 清仓          | 退潮周期，强制SKIP    |
| 300398     | 飞凯材料 | SKIP   | zero          | 84.49        | 清仓          | 退潮周期，强制SKIP    |
| 002371     | 北方华创 | SKIP   | zero          | 84.21        | 清仓          | 退潮周期，强制SKIP    |
| 001309     | 德明利  | SKIP   | zero          | 84.2         | 清仓          | 退潮周期，强制SKIP    |
| 688525     | 佰维存储 | SKIP   | zero          | 83.93        | 清仓          | 退潮周期，强制SKIP    |
| 688072     | 拓荆科技 | SKIP   | zero          | 83.61        | 清仓          | 退潮周期，强制SKIP    |
| 301013     | 利和兴  | SKIP   | zero          | 83.52        | 清仓          | 退潮周期，强制SKIP    |
| 688048     | 长光华芯 | SKIP   | zero          | 83.36        | 清仓          | 退潮周期，强制SKIP    |
| 600105     | 永鼎股份 | SKIP   | zero          | 83.34        | 清仓          | 退潮周期，强制SKIP    |
| 002384     | 东山精密 | SKIP   | zero          | 83.31        | 清仓          | 退潮周期，强制SKIP    |
| 603986     | 兆易创新 | SKIP   | zero          | 83.13        | 清仓          | 退潮周期，强制SKIP    |
| 600522     | 中天科技 | SKIP   | zero          | 83.12        | 清仓          | 退潮周期，强制SKIP    |
| 600487     | 亨通光电 | SKIP   | zero          | 83.0         | 清仓          | 退潮周期，强制SKIP    |
| 300604     | 长川科技 | SKIP   | zero          | 82.99        | 清仓          | 退潮周期，强制SKIP    |
| 600246     | 万通发展 | SKIP   | zero          | 82.92        | 清仓          | 退潮周期，强制SKIP    |
| 688507     | 索辰科技 | SKIP   | zero          | 82.87        | 清仓          | 退潮周期，强制SKIP    |

## 仓位建议

- full：主升/加速 + 龙头，单票模拟高关注，组合仓位80~100%
- medium：启动 + 趋势，组合仓位50~80%
- small：震荡或非龙头，组合仓位10~50%
- zero：退潮或风控闸门关闭，组合仓位0

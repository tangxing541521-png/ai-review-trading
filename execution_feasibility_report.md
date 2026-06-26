# Execution Alignment 实盘对齐报告

> 本报告只验证【模拟】订单信号在真实市场中的可执行性，不接券商、不自动下单。

## 最终对齐结论

- 今日信号是否真实可交易：NO
- 信号质量评分：33.56
- 是否存在滑点风险：YES
- 是否建议放弃交易：YES
- 对齐原因：没有通过实盘过滤的订单

## 可真实执行信号

暂无数据

## 被实盘过滤信号

| stock_code | name | original_action | aligned_action | signal_filled_probability | signal_decay_score | alignment_reason                  |
| ---------- | ---- | --------------- | -------------- | ------------------------- | ------------------ | --------------------------------- |
| 000021     | 深科技  | SKIP            | SKIP           | HIGH                      | 0.0                | market_cycle=退潮；原始订单为SKIP         |
| 000725     | 京东方Ａ | SKIP            | SKIP           | HIGH                      | 0.0                | market_cycle=退潮；原始订单为SKIP         |
| 603005     | 晶方科技 | SKIP            | SKIP           | HIGH                      | 0.0                | market_cycle=退潮；原始订单为SKIP         |
| 301308     | 江波龙  | SKIP            | SKIP           | HIGH                      | 0.0                | market_cycle=退潮；原始订单为SKIP         |
| 600584     | 长电科技 | SKIP            | SKIP           | LOW                       | 0.0                | 可成交性LOW；market_cycle=退潮；原始订单为SKIP |
| 300398     | 飞凯材料 | SKIP            | SKIP           | HIGH                      | 1.77               | market_cycle=退潮；原始订单为SKIP         |
| 002371     | 北方华创 | SKIP            | SKIP           | HIGH                      | 0.0                | market_cycle=退潮；原始订单为SKIP         |
| 001309     | 德明利  | SKIP            | SKIP           | LOW                       | 0.78               | 可成交性LOW；market_cycle=退潮；原始订单为SKIP |
| 688525     | 佰维存储 | SKIP            | SKIP           | LOW                       | 0.0                | 可成交性LOW；market_cycle=退潮；原始订单为SKIP |
| 688072     | 拓荆科技 | SKIP            | SKIP           | HIGH                      | 0.0                | market_cycle=退潮；原始订单为SKIP         |
| 301013     | 利和兴  | SKIP            | SKIP           | LOW                       | 4.16               | 可成交性LOW；market_cycle=退潮；原始订单为SKIP |
| 688048     | 长光华芯 | SKIP            | SKIP           | HIGH                      | 0.0                | market_cycle=退潮；原始订单为SKIP         |
| 600105     | 永鼎股份 | SKIP            | SKIP           | HIGH                      | 18.65              | market_cycle=退潮；原始订单为SKIP         |
| 002384     | 东山精密 | SKIP            | SKIP           | HIGH                      | 0.0                | market_cycle=退潮；原始订单为SKIP         |
| 603986     | 兆易创新 | SKIP            | SKIP           | LOW                       | 8.77               | 可成交性LOW；market_cycle=退潮；原始订单为SKIP |
| 600522     | 中天科技 | SKIP            | SKIP           | LOW                       | 0.63               | 可成交性LOW；market_cycle=退潮；原始订单为SKIP |
| 600487     | 亨通光电 | SKIP            | SKIP           | HIGH                      | 0.0                | market_cycle=退潮；原始订单为SKIP         |
| 300604     | 长川科技 | SKIP            | SKIP           | HIGH                      | 12.68              | market_cycle=退潮；原始订单为SKIP         |
| 600246     | 万通发展 | SKIP            | SKIP           | HIGH                      | 6.54               | market_cycle=退潮；原始订单为SKIP         |
| 688507     | 索辰科技 | SKIP            | SKIP           | HIGH                      | 2.82               | market_cycle=退潮；原始订单为SKIP         |

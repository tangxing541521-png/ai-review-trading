# Execution Alignment 实盘对齐报告

> 本报告只验证【模拟】订单信号在真实市场中的可执行性，不接券商、不自动下单。

## 最终对齐结论

- 今日信号是否真实可交易：NO
- 信号质量评分：36.96
- 是否存在滑点风险：YES
- 是否建议放弃交易：YES
- 对齐原因：没有通过实盘过滤的订单

## 可真实执行信号

暂无数据

## 被实盘过滤信号

| stock_code | name | original_action | aligned_action | signal_filled_probability | signal_decay_score | alignment_reason                  |
| ---------- | ---- | --------------- | -------------- | ------------------------- | ------------------ | --------------------------------- |
| 300346     | 南大光电 | SKIP            | SKIP           | HIGH                      | 0.0                | market_cycle=退潮；原始订单为SKIP         |
| 600707     | 彩虹股份 | SKIP            | SKIP           | LOW                       | 0.0                | 可成交性LOW；market_cycle=退潮；原始订单为SKIP |
| 600522     | 中天科技 | SKIP            | SKIP           | HIGH                      | 0.0                | market_cycle=退潮；原始订单为SKIP         |
| 300223     | 北京君正 | SKIP            | SKIP           | HIGH                      | 2.59               | market_cycle=退潮；原始订单为SKIP         |
| 600703     | 三安光电 | SKIP            | SKIP           | HIGH                      | 0.0                | market_cycle=退潮；原始订单为SKIP         |
| 002281     | 光迅科技 | SKIP            | SKIP           | HIGH                      | 19.98              | market_cycle=退潮；原始订单为SKIP         |
| 600105     | 永鼎股份 | SKIP            | SKIP           | HIGH                      | 6.57               | market_cycle=退潮；原始订单为SKIP         |
| 002747     | 埃斯顿  | SKIP            | SKIP           | HIGH                      | 0.0                | market_cycle=退潮；原始订单为SKIP         |
| 002428     | 云南锗业 | SKIP            | SKIP           | HIGH                      | 0.0                | market_cycle=退潮；原始订单为SKIP         |
| 688347     | 华虹宏力 | SKIP            | SKIP           | HIGH                      | 5.11               | market_cycle=退潮；原始订单为SKIP         |
| 688396     | 华润微  | SKIP            | SKIP           | HIGH                      | 8.18               | market_cycle=退潮；原始订单为SKIP         |
| 301013     | 利和兴  | SKIP            | SKIP           | HIGH                      | 6.07               | market_cycle=退潮；原始订单为SKIP         |
| 600552     | 凯盛科技 | SKIP            | SKIP           | HIGH                      | 0.32               | market_cycle=退潮；原始订单为SKIP         |
| 601869     | 长飞光纤 | SKIP            | SKIP           | LOW                       | 0.0                | 可成交性LOW；market_cycle=退潮；原始订单为SKIP |
| 300037     | 新宙邦  | SKIP            | SKIP           | HIGH                      | 13.13              | market_cycle=退潮；原始订单为SKIP         |
| 002056     | 横店东磁 | SKIP            | SKIP           | HIGH                      | 1.16               | market_cycle=退潮；原始订单为SKIP         |
| 600487     | 亨通光电 | SKIP            | SKIP           | HIGH                      | 4.8                | market_cycle=退潮；原始订单为SKIP         |
| 688143     | 长盈通  | SKIP            | SKIP           | HIGH                      | 0.0                | market_cycle=退潮；原始订单为SKIP         |
| 300835     | 龙磁科技 | SKIP            | SKIP           | MEDIUM                    | 0.0                | market_cycle=退潮；原始订单为SKIP         |
| 301611     | 珂玛科技 | SKIP            | SKIP           | HIGH                      | 0.0                | market_cycle=退潮；原始订单为SKIP         |

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
- 风险等级：14.16
- 风控原因：market_cycle=退潮；cycle进入退潮

## 可执行订单 Order Packet

| stock_code | action | position_ratio | score | cycle | reason                    |
| ---------- | ------ | -------------- | ----- | ----- | ------------------------- |
| 300346     | SKIP   | 0.0            | 86.7  | 退潮期   | market_cycle=退潮；cycle进入退潮 |
| 600707     | SKIP   | 0.0            | 86.01 | 退潮期   | market_cycle=退潮；cycle进入退潮 |
| 600522     | SKIP   | 0.0            | 85.8  | 退潮期   | market_cycle=退潮；cycle进入退潮 |
| 300223     | SKIP   | 0.0            | 85.61 | 退潮期   | market_cycle=退潮；cycle进入退潮 |
| 600703     | SKIP   | 0.0            | 85.36 | 退潮期   | market_cycle=退潮；cycle进入退潮 |
| 002281     | SKIP   | 0.0            | 84.7  | 退潮期   | market_cycle=退潮；cycle进入退潮 |
| 600105     | SKIP   | 0.0            | 84.65 | 退潮期   | market_cycle=退潮；cycle进入退潮 |
| 002747     | SKIP   | 0.0            | 84.35 | 退潮期   | market_cycle=退潮；cycle进入退潮 |
| 002428     | SKIP   | 0.0            | 84.19 | 退潮期   | market_cycle=退潮；cycle进入退潮 |
| 688347     | SKIP   | 0.0            | 84.17 | 退潮期   | market_cycle=退潮；cycle进入退潮 |
| 688396     | SKIP   | 0.0            | 84.12 | 退潮期   | market_cycle=退潮；cycle进入退潮 |
| 301013     | SKIP   | 0.0            | 83.92 | 退潮期   | market_cycle=退潮；cycle进入退潮 |
| 600552     | SKIP   | 0.0            | 83.9  | 退潮期   | market_cycle=退潮；cycle进入退潮 |
| 601869     | SKIP   | 0.0            | 83.73 | 退潮期   | market_cycle=退潮；cycle进入退潮 |
| 300037     | SKIP   | 0.0            | 82.94 | 退潮期   | market_cycle=退潮；cycle进入退潮 |
| 002056     | SKIP   | 0.0            | 82.37 | 退潮期   | market_cycle=退潮；cycle进入退潮 |
| 600487     | SKIP   | 0.0            | 82.35 | 退潮期   | market_cycle=退潮；cycle进入退潮 |
| 688143     | SKIP   | 0.0            | 82.29 | 退潮期   | market_cycle=退潮；cycle进入退潮 |
| 300835     | SKIP   | 0.0            | 82.28 | 退潮期   | market_cycle=退潮；cycle进入退潮 |
| 301611     | SKIP   | 0.0            | 82.22 | 退潮期   | market_cycle=退潮；cycle进入退潮 |

## 可执行标的列表

暂无数据

## 禁止交易标的列表

| stock_code | name | action | position_size | master_score | hold_action | trigger_reason |
| ---------- | ---- | ------ | ------------- | ------------ | ----------- | -------------- |
| 300346     | 南大光电 | SKIP   | zero          | 86.7         | 清仓          | 退潮周期，强制SKIP    |
| 600707     | 彩虹股份 | SKIP   | zero          | 86.01        | 清仓          | 退潮周期，强制SKIP    |
| 600522     | 中天科技 | SKIP   | zero          | 85.8         | 清仓          | 退潮周期，强制SKIP    |
| 300223     | 北京君正 | SKIP   | zero          | 85.61        | 清仓          | 退潮周期，强制SKIP    |
| 600703     | 三安光电 | SKIP   | zero          | 85.36        | 清仓          | 退潮周期，强制SKIP    |
| 002281     | 光迅科技 | SKIP   | zero          | 84.7         | 清仓          | 退潮周期，强制SKIP    |
| 600105     | 永鼎股份 | SKIP   | zero          | 84.65        | 清仓          | 退潮周期，强制SKIP    |
| 002747     | 埃斯顿  | SKIP   | zero          | 84.35        | 清仓          | 退潮周期，强制SKIP    |
| 002428     | 云南锗业 | SKIP   | zero          | 84.19        | 清仓          | 退潮周期，强制SKIP    |
| 688347     | 华虹宏力 | SKIP   | zero          | 84.17        | 清仓          | 退潮周期，强制SKIP    |
| 688396     | 华润微  | SKIP   | zero          | 84.12        | 清仓          | 退潮周期，强制SKIP    |
| 301013     | 利和兴  | SKIP   | zero          | 83.92        | 清仓          | 退潮周期，强制SKIP    |
| 600552     | 凯盛科技 | SKIP   | zero          | 83.9         | 清仓          | 退潮周期，强制SKIP    |
| 601869     | 长飞光纤 | SKIP   | zero          | 83.73        | 清仓          | 退潮周期，强制SKIP    |
| 300037     | 新宙邦  | SKIP   | zero          | 82.94        | 清仓          | 退潮周期，强制SKIP    |
| 002056     | 横店东磁 | SKIP   | zero          | 82.37        | 清仓          | 退潮周期，强制SKIP    |
| 600487     | 亨通光电 | SKIP   | zero          | 82.35        | 清仓          | 退潮周期，强制SKIP    |
| 688143     | 长盈通  | SKIP   | zero          | 82.29        | 清仓          | 退潮周期，强制SKIP    |
| 300835     | 龙磁科技 | SKIP   | zero          | 82.28        | 清仓          | 退潮周期，强制SKIP    |
| 301611     | 珂玛科技 | SKIP   | zero          | 82.22        | 清仓          | 退潮周期，强制SKIP    |

## 仓位建议

- full：主升/加速 + 龙头，单票模拟高关注，组合仓位80~100%
- medium：启动 + 趋势，组合仓位50~80%
- small：震荡或非龙头，组合仓位10~50%
- zero：退潮或风控闸门关闭，组合仓位0

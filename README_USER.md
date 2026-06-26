# AI复盘交易普通用户使用说明

这份说明写给完全不会代码的用户。

本系统只做模拟验证：

- 不自动下单
- 不连接券商
- 不控制同花顺
- 不保证收益

## 1. 如何下载项目

把整个项目文件夹保存到电脑本地，例如：

```text
C:\Users\你的用户名\Documents\ai复盘交易\ai-review-trading
```

以后所有操作都在这个文件夹里完成。

## 2. 第一次使用：双击 setup.bat

第一次使用前，请双击：

```text
setup.bat
```

它会自动检查 Python，并安装项目需要的依赖。

如果提示没有 Python，请先安装 Python 3.10 或更高版本。

安装 Python 时请勾选：

```text
Add Python to PATH
```

## 3. 每天使用：双击 start_trader.bat

每天收盘后，双击：

```text
start_trader.bat
```

它会自动完成：

1. 运行今日交易员流程
2. 更新 Forward Validation
3. 更新 Paper Trading 虚拟账户
4. 生成最终日报 `final_report.md`

## 4. 每天什么时候运行

建议在 A 股收盘后运行。

推荐时间：

```text
15:30 以后
```

如果 AkShare 数据接口暂时失败，可以稍后再运行一次。

## 5. 看哪个报告

普通用户重点看这三个文件：

```text
final_report.md
paper_report.md
validation_report.md
```

其中：

- `final_report.md`：当天最终结论
- `paper_report.md`：虚拟账户表现
- `validation_report.md`：前向验证统计

## 6. 图形界面

如果不想看命令窗口，可以双击或运行：

```text
app_launcher.py
```

界面里有四个按钮：

1. 运行今日交易员流程
2. 打开 `paper_report.md`
3. 打开 `validation_report.md`
4. 打开 `final_report.md`

## 7. 每日报告怎么看

每天重点看：

1. 当前市场周期
2. 是否允许交易
3. 推荐股票
4. 龙头股票
5. 建议仓位
6. 风险等级
7. 当前账户总资产
8. 当前持仓
9. 当日收益
10. 累计收益

## 8. 重要注意

本系统是模拟验证工具，不是自动交易工具。

请记住：

- 不会自动买股票
- 不会自动卖股票
- 不会连接券商
- 不会控制同花顺
- 不保证赚钱

系统的目标是验证：

```text
如果完全按照系统信号执行，长期结果到底如何。
```

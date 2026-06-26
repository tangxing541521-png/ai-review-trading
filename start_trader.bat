@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo AI复盘交易 - Trading Mode 交易冻结模式
echo ========================================
echo.
echo 本模式会每天固定生成一次正式交易决策。
echo 如果今天已经生成 frozen_decisions\orders_YYYYMMDD.csv，
echo 本次运行只读取冻结订单，不会重新生成交易决策。
echo.

set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not exist "%PYTHON_EXE%" (
    set "PYTHON_EXE=python"
)

"%PYTHON_EXE%" --version >nul 2>nul
if errorlevel 1 (
    echo [失败] 未检测到可用 Python，请先双击 setup.bat。
    echo 错误码：1
    echo.
    pause
    exit /b 1
)

echo [第一步/三步] 开始运行 decision_freeze.py
echo 说明：如果今日未冻结，会运行 forward_test 并冻结订单；如果已冻结，只读取冻结结果。
echo ----------------------------------------
"%PYTHON_EXE%" -u -X utf8 decision_freeze.py
set FREEZE_CODE=%ERRORLEVEL%
echo ----------------------------------------
if not "%FREEZE_CODE%"=="0" (
    echo [失败] decision_freeze.py 执行失败。
    echo 错误码：%FREEZE_CODE%
    echo 请查看上方错误信息。
    echo.
    pause
) else (
    echo [成功] decision_freeze.py 执行完成。
)
echo.

echo [第二步/三步] 开始运行 paper_trading.py
echo 说明：虚拟账户只读取 frozen_decisions 里的冻结订单。
echo ----------------------------------------
"%PYTHON_EXE%" -u -X utf8 paper_trading.py
set PAPER_CODE=%ERRORLEVEL%
echo ----------------------------------------
if not "%PAPER_CODE%"=="0" (
    echo [失败] paper_trading.py 执行失败。
    echo 错误码：%PAPER_CODE%
    echo 请查看上方错误信息。
    echo.
    pause
) else (
    echo [成功] paper_trading.py 执行完成。
)
echo.

echo [第三步/三步] 开始生成 final_report.md
echo 说明：汇总冻结状态、订单来源、账户资金和今日结论。
echo ----------------------------------------
"%PYTHON_EXE%" -u -X utf8 -c "from app_launcher import generate_final_report, print_final_summary, latest_frozen_date; s=generate_final_report(latest_frozen_date()); print_final_summary(s)"
set FINAL_CODE=%ERRORLEVEL%
echo ----------------------------------------
if not "%FINAL_CODE%"=="0" (
    echo [失败] final_report.md 生成失败。
    echo 错误码：%FINAL_CODE%
    echo 请查看上方错误信息。
    echo.
    pause
) else (
    echo [成功] final_report.md 已生成。
)
echo.

echo ========================================
echo 今日交易员流程执行结束。
echo 请打开 final_report.md 查看最终结论。
echo ========================================
echo.
pause

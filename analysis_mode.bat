@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo AI复盘交易 - Analysis Mode 实时分析模式
echo ========================================
echo.
echo 【实时分析模式，仅供观察，不作为正式交易依据】
echo 本模式允许重新读取最新数据，结果可能变化。
echo 本模式不会写入 frozen_decisions 冻结订单。
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

echo [开始] 运行 forward_test.py 实时分析
echo ----------------------------------------
"%PYTHON_EXE%" -u -X utf8 forward_test.py
set ANALYSIS_CODE=%ERRORLEVEL%
echo ----------------------------------------
if not "%ANALYSIS_CODE%"=="0" (
    echo [失败] forward_test.py 实时分析失败。
    echo 错误码：%ANALYSIS_CODE%
    echo 请查看上方错误信息。
    echo.
    pause
) else (
    echo [成功] 实时分析已完成。
)
echo.
echo 【实时分析模式，仅供观察，不作为正式交易依据】
echo.
pause

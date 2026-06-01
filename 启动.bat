@echo off
setlocal

:: ============================================================
:: AI 鹊桥启动脚本
::
:: 默认优先使用 Windows Python Launcher：py
:: 如果你的电脑没有 py，则自动尝试使用 python。
::
:: 如需指定自己的本地 Python 路径，请修改下面这一行：
:: 示例：
:: set "CUSTOM_PYTHON_EXE=C:\Users\你的用户名\AppData\Local\Programs\Python\Python312\python.exe"
::
:: 留空则自动检测：
set "CUSTOM_PYTHON_EXE="
:: ============================================================

:: 切换到 bat 文件所在目录
cd /d "%~dp0"

echo 正在启动 AI 鹊桥...

:: 优先使用用户手动指定的 Python
if not "%CUSTOM_PYTHON_EXE%"=="" (
    if exist "%CUSTOM_PYTHON_EXE%" (
        set "PY_CMD=%CUSTOM_PYTHON_EXE%"
    ) else (
        echo [ERROR] 你指定的 Python 路径不存在。
        echo 请检查启动.bat 中的 CUSTOM_PYTHON_EXE 配置。
        pause
        exit /b 1
    )
) else (
    :: 自动检测系统 Python
    where py >nul 2>nul
    if %errorlevel%==0 (
        set "PY_CMD=py"
    ) else (
        where python >nul 2>nul
        if %errorlevel%==0 (
            set "PY_CMD=python"
        ) else (
            echo [ERROR] 未找到 Python。
            echo.
            echo 解决方法：
            echo 1. 安装 Python，并勾选 Add Python to PATH
            echo 2. 或者修改本脚本中的 CUSTOM_PYTHON_EXE，指向你本机的 python.exe
            echo.
            echo 示例：
            echo set "CUSTOM_PYTHON_EXE=C:\Users\你的用户名\AppData\Local\Programs\Python\Python312\python.exe"
            pause
            exit /b 1
        )
    )
)

:: 不输出本地 Python 真实路径，避免暴露本机目录信息
%PY_CMD% -c "import sys; print('Python 已就绪：' + sys.version.split()[0])"

:: 运行程序
%PY_CMD% main.py

pause
endlocal
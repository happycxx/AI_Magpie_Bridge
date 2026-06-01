@echo off
setlocal

:: 切换到 bat 文件所在目录
cd /d "%~dp0"

:: 优先使用 Windows Python Launcher，调用系统已安装的 Python
where py >nul 2>nul
if %errorlevel%==0 (
    set "PY_CMD=py"
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        set "PY_CMD=python"
    ) else (
        echo [ERROR] 未找到 Python。
        echo 请先安装 Python，并勾选 "Add Python to PATH"，或安装 Windows Python Launcher。
        pause
        exit /b 1
    )
)

:: 验证 Python 路径
echo Current Python Path:
%PY_CMD% -c "import sys; print(sys.executable)"

:: 运行程序
%PY_CMD% main.py

pause
endlocal
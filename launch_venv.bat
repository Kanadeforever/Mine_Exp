@echo off
chcp 936 >nul
rem 设置当前目录为脚本所在目录
cd /d "%~dp0"

rem 激活虚拟环境
call ".\.venv\Scripts\activate"

color 06
echo 虚拟环境已启动！
echo.

python --version
echo.

rem 保持命令窗口开启
cmd /k

@echo on
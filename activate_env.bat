@echo off
chcp 65001 >nul
echo 虚拟环境快速启动工具
echo ====================

REM 检查是否已在虚拟环境中
if not "%VIRTUAL_ENV%"=="" (
    echo 虚拟环境已激活: %VIRTUAL_ENV%
    echo 当前Python: %VIRTUAL_ENV%\Scripts\python.exe
    goto :stay_open
)

REM 查找虚拟环境
if exist "venv\Scripts\activate.bat" (
    set VENV_DIR=venv
    goto :activate_venv
)

if exist ".venv\Scripts\activate.bat" (
    set VENV_DIR=.venv
    goto :activate_venv
)

if exist "env\Scripts\activate.bat" (
    set VENV_DIR=env
    goto :activate_venv
)

REM 未找到虚拟环境，询问是否创建
echo 未找到虚拟环境
choice /c yn /m "是否创建虚拟环境？(Y/N)"
if %errorlevel% equ 2 goto :end

set /p VENV_NAME=输入虚拟环境名称 [默认: venv]: 
if "%VENV_NAME%"=="" set VENV_NAME=venv

echo 正在创建虚拟环境...
python -m venv %VENV_NAME%
set VENV_DIR=%VENV_NAME%

:activate_venv
echo 正在激活虚拟环境: %VENV_DIR%
call %VENV_DIR%\Scripts\activate.bat
echo 已激活虚拟环境！
echo Python路径: %VENV_DIR%\Scripts\python.exe
echo Python版本:
python --version

:stay_open
echo.
echo 现在可以在虚拟环境中执行命令
echo 输入 deactivate 退出虚拟环境,输入exit关闭窗口退出
echo ====================
cmd /k "title Python虚拟环境 - %CD%"

:end
pause
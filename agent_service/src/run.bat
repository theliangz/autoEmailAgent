@echo off
REM Windows启动脚本

REM 检查.env文件是否存在
if not exist .env (
    echo 错误: .env 文件不存在，请先配置环境变量
    exit /b 1
)

REM 运行Agent
echo 启动 autoEmailAgent...
python entrypoint.py


#!/bin/bash
# 启动脚本

# 检查.env文件是否存在
if [ ! -f .env ]; then
    echo "错误: .env 文件不存在，请先配置环境变量"
    exit 1
fi

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到Python3"
    exit 1
fi

# 运行Agent
echo "启动 autoEmailAgent..."
python3 entrypoint.py


#!/bin/bash

# 设置环境变量
export FRONTEND_DIST_DIR="/home/phcool/dlmonitor/frontend/dist"
export DISABLE_SCHEDULER="true"
export API_HOST="0.0.0.0"
export API_PORT="8000"
export API_RELOAD="False"
export LOG_LEVEL="INFO"  # 改回INFO级别

# 确认前端目录存在
if [ ! -d "$FRONTEND_DIST_DIR" ]; then
  echo "错误: 前端目录不存在: $FRONTEND_DIST_DIR"
  exit 1
fi

if [ ! -f "$FRONTEND_DIST_DIR/index.html" ]; then
  echo "错误: index.html不存在于前端目录: $FRONTEND_DIST_DIR"
  exit 1
fi

# 进入后端目录
cd /home/phcool/dlmonitor/backend

# 启动FastAPI服务器
echo "正在启动服务器..."
python run.py 
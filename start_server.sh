

# 获取当前路径
CURRENT_DIR=$(pwd)
echo "Starting server from $CURRENT_DIR"

# 确保日志文件存在
touch backend/logs/output.log

# 用nohup运行后端服务，后台执行，输出重定向到日志文件
echo "Starting backend server with nohup..."
nohup python backend/run.py > backend/logs/output.log 2>&1 &

# 保存进程ID到文件
echo $! > backend/logs/server.pid
echo "Server started with PID: $!"
echo "Logs are being written to: backend/logs/output.log"
echo "To stop the server, run: kill \$(cat backend/logs/server.pid)" 
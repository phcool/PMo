mkdir -p logs

mkdir -p lo
touch logs/output.log

# redirect output to log file
echo "Starting backend server with nohup..."
nohup python run.py > logs/output.log 2>&1 &


#!/bin/bash
# This script sets up cron jobs for fetching and analyzing papers

# Get the absolute path to the scripts
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
FETCH_SCRIPT="$SCRIPT_DIR/fetch_papers.py"
ANALYZE_SCRIPT="$SCRIPT_DIR/analyze_papers.py"

# Get the Python interpreter path
PYTHON_PATH=$(which python)

# Get the virtualenv path if we're in one
if [[ -n "$VIRTUAL_ENV" ]]; then
    PYTHON_PATH="$VIRTUAL_ENV/bin/python"
    echo "Using virtualenv Python at $PYTHON_PATH"
else
    echo "Using system Python at $PYTHON_PATH"
    echo "Warning: It's recommended to run this script from within a virtualenv"
fi

# Create temporary crontab file
TEMP_CRON=$(mktemp)

# Export any existing crontab
crontab -l > "$TEMP_CRON" 2>/dev/null || echo "# New crontab" > "$TEMP_CRON"

# Check if our jobs are already in the crontab
if grep -q "fetch_papers.py" "$TEMP_CRON"; then
    echo "Fetch papers job already exists in crontab. Removing it to update."
    sed -i '/fetch_papers.py/d' "$TEMP_CRON"
fi

if grep -q "analyze_papers.py" "$TEMP_CRON"; then
    echo "Analyze papers job already exists in crontab. Removing it to update."
    sed -i '/analyze_papers.py/d' "$TEMP_CRON"
fi

# Add fetch papers job - run every 4 hours (at hour 0, 4, 8, 12, 16, 20)
echo "0 */4 * * * $PYTHON_PATH $FETCH_SCRIPT >> $SCRIPT_DIR/../logs/cron_fetch.log 2>&1" >> "$TEMP_CRON"
echo "Added fetch papers job to crontab (every 4 hours)"

# Add analyze papers job - run 30 minutes after fetch papers job (at hour 0:30, 4:30, 8:30, 12:30, 16:30, 20:30)
# 使用--concurrency 1参数限制并发，以便处理所有待分析论文但不会被API限流
echo "30 */4 * * * $PYTHON_PATH $ANALYZE_SCRIPT --concurrency 1 >> $SCRIPT_DIR/../logs/cron_analyze.log 2>&1" >> "$TEMP_CRON"
echo "Added analyze papers job to crontab (30 minutes after fetch job, processing all papers with concurrency=1)"

# Install new crontab
crontab "$TEMP_CRON"
rm "$TEMP_CRON"

echo "Cron jobs have been set up successfully!"
echo "To check your crontab, run: crontab -l"

# Create logs directory if it doesn't exist
mkdir -p "$SCRIPT_DIR/../logs"
echo "Created logs directory at $SCRIPT_DIR/../logs"

# Disable the scheduler service in the web app to avoid duplication
echo "
Note: The scheduler has been disabled in your .env file with DISABLE_SCHEDULER=true
The following cron jobs have been set up:
1. Fetch papers: Every 4 hours (0:00, 4:00, 8:00, 12:00, 16:00, 20:00)
2. Analyze papers: 30 minutes after fetch (0:30, 4:30, 8:30, 12:30, 16:30, 20:30) - processing all pending papers with concurrency=1
" 
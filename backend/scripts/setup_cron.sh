#!/bin/bash
# This script sets up cron jobs for fetching and analyzing papers

# Get the absolute path to the scripts
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
FETCH_SCRIPT="$SCRIPT_DIR/fetch_papers.py"

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

# Add fetch papers job - run every 4 hours (at hour 0, 4, 8, 12, 16, 20)
echo "0 */12 * * * $PYTHON_PATH $FETCH_SCRIPT >> $SCRIPT_DIR/../logs/cron_fetch.log 2>&1" >> "$TEMP_CRON"
echo "Added fetch papers job to crontab (every 12 hours)"

# Install new crontab
crontab "$TEMP_CRON"
rm "$TEMP_CRON"

echo "Cron jobs have been set up successfully!"
echo "To check your crontab, run: crontab -l"

# Create logs directory if it doesn't exist
mkdir -p "$SCRIPT_DIR/../logs"
echo "Created logs directory at $SCRIPT_DIR/../logs"
echo "
Note: The scheduler has been disabled in your .env file with DISABLE_SCHEDULER=true
The following cron jobs have been set up:
Fetch papers: Every 12 hours (0:00, 12:00)
" 
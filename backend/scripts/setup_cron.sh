SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

CRON_JOB="0 2 * * * cd $SCRIPT_DIR && python3 fetch_papers.py --days 2 >> ../logs/cron_fetch.log 2>&1"

(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

echo "Cron job has been set up successfully!"

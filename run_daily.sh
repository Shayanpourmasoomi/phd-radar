#!/usr/bin/env bash
# Daily run (macOS/Linux).  cron example (every day 07:30):
#   30 7 * * *  /full/path/to/phd-agent/run_daily.sh >> /full/path/to/phd-agent/data/run.log 2>&1
cd "$(dirname "$0")" || exit 1
python3 -m agent run

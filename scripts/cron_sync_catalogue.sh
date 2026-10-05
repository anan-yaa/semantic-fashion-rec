#!/usr/bin/env bash
# Cron entry point for scripts/sync_catalogue.py.
# Cron runs with a minimal environment, so set the working directory (for .env)
# and PYTHONPATH here. flock skips this run if the previous one is still going.
#
# Install (daily at 02:00):
#   (crontab -l 2>/dev/null; echo "0 2 * * * $PWD/scripts/cron_sync_catalogue.sh") | crontab -
set -uo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$REPO_DIR/logs"
LOCK_HELD=75
mkdir -p "$LOG_DIR"

cd "$REPO_DIR"
export PYTHONPATH="$REPO_DIR"
export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"

{
  echo "=== $(date -u '+%Y-%m-%dT%H:%M:%SZ') sync start ==="
  flock -n -E "$LOCK_HELD" "$LOG_DIR/sync_catalogue.lock" python3 scripts/sync_catalogue.py "$@"
  status=$?
  if [ "$status" -eq "$LOCK_HELD" ]; then
    echo "previous sync still running; skipped"
  fi
  echo "=== $(date -u '+%Y-%m-%dT%H:%M:%SZ') sync end (exit $status) ==="
} >> "$LOG_DIR/sync_catalogue.log" 2>&1
exit "${status:-1}"

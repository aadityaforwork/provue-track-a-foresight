#!/bin/sh
# Runs the reference solution N times against the running container and reports successes.
#
# On this host (Windows, git-bash), the bare `python` on PATH does not
# reliably have the `requests` and `PyJWT` dependencies that solve.py
# needs - they live in the project's .venv. Point PYTHON at the venv
# interpreter when invoking this script, e.g.:
#
#   PYTHON=.venv/Scripts/python sh calibration/reliability.sh 16
#
# If PYTHON is unset, this script falls back to plain `python`.
set -u
N="${1:-16}"
BASE_URL="${BASE_URL:-http://localhost:8080}"
PYTHON="${PYTHON:-python}"
ok=0
start=$(date +%s)
for i in $(seq 1 "$N"); do
  if BASE_URL="$BASE_URL" "$PYTHON" solution/solve.py >/dev/null 2>&1; then
    ok=$((ok+1))
  fi
done
end=$(date +%s)
echo "reliability: $ok/$N"
echo "total_wallclock_s: $((end-start))"
echo "avg_solve_s: $(awk "BEGIN{print ($end-$start)/$N}")"

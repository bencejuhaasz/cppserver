#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVER_BIN="$ROOT_DIR/build/src/cppserver"
LOG_FILE="/tmp/cppserver.log"
RESULTS_FILE="/tmp/cppserver_results.txt"

if [ ! -x "$SERVER_BIN" ]; then
  echo "Error: server binary not found or not executable: $SERVER_BIN"
  echo "Build with: cmake --build build -- -j"
  exit 1
fi

echo "Starting server: $SERVER_BIN"
"$SERVER_BIN" > "$LOG_FILE" 2>&1 &
PID=$!
echo "Server PID: $PID (logging to $LOG_FILE)"

cleanup() {
  echo "Stopping server PID $PID"
  kill "$PID" 2>/dev/null || true
  wait "$PID" 2>/dev/null || true
}
trap cleanup EXIT

echo "Waiting for server to become ready..."
for i in $(seq 1 20); do
  if curl -sS --connect-timeout 1 http://127.0.0.1:8080/ >/dev/null 2>&1; then
    echo "Server is ready"
    break
  fi
  sleep 0.5
done

if ! curl -sS --connect-timeout 1 http://127.0.0.1:8080/ >/dev/null 2>&1; then
  echo "Server did not start successfully. See $LOG_FILE"
  exit 1
fi

CONCURRENCY=400
echo "Running $CONCURRENCY parallel requests against http://127.0.0.1:8080/"
rm -f "$RESULTS_FILE"
seq 1 $CONCURRENCY | xargs -n1 -P$CONCURRENCY -I{} bash -c \
  'out=$(curl -sS -o /dev/null -w "code:%{http_code} time:%{time_total}" http://127.0.0.1:8080/ 2>/dev/null); ec=$?; if [ "$ec" -ne 0 ]; then printf "id:%s error:exit=%d\n" "{}" "$ec"; else printf "id:%s %s\n" "{}" "$out"; fi' \
  >> "$RESULTS_FILE"

echo "Results (first 20 lines):"
head -n 20 "$RESULTS_FILE" || true

echo "Summary:"
TOTAL=$(wc -l < "$RESULTS_FILE" || echo 0)
AVG_TIME=$(awk -F"time:" '{sum += $2} END { if (NR>0) printf "%.4f", sum/NR; else print "0" }' "$RESULTS_FILE")
echo "- Requests: $TOTAL"
echo "- Avg time (s): $AVG_TIME"

echo "Full results in: $RESULTS_FILE"

exit 0

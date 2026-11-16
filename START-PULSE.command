#!/bin/bash
# Pulse — Student News. Double-click this file on macOS or run it in Terminal.
cd "$(dirname "$0")" || exit 1
if ! command -v python3 >/dev/null 2>&1; then
  echo "Pulse needs Python 3. Install it from https://www.python.org/downloads/ and try again."
  read -r -p "Press Return to close."
  exit 1
fi
python3 run.py &
PID=$!
sleep 2
open "http://localhost:8787" 2>/dev/null || true
wait "$PID"

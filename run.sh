#!/bin/bash
# Starts both dev servers with a single command:
# - leaderboard_server.py (leaderboard, port 8765)
# - pygbag main.py (builds and serves the game in the browser, port 8000)
# Ctrl+C stops both.

cd "$(dirname "$0")"

cleanup() {
    echo
    echo "Stopping servers..."
    kill "$LEADERBOARD_PID" "$PYGBAG_PID" 2>/dev/null
}
trap cleanup EXIT INT TERM

python3 leaderboard_server.py &
LEADERBOARD_PID=$!
echo "leaderboard_server.py running (pid $LEADERBOARD_PID) on http://localhost:8765"

python3 -m pygbag --template pygbag_template.html main.py &
PYGBAG_PID=$!
echo "pygbag main.py running (pid $PYGBAG_PID) on http://localhost:8000"

wait

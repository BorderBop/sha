#!/bin/bash
# Поднимает оба сервера разработки одной командой:
# - leaderboard_server.py (таблица рекордов, порт 8765)
# - pygbag main.py (сборка и раздача игры в браузере, порт 8000)
# Ctrl+C останавливает оба.

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

python3 -m pygbag main.py &
PYGBAG_PID=$!
echo "pygbag main.py running (pid $PYGBAG_PID) on http://localhost:8000"

wait

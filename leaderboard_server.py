import hashlib
import json
import os
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

DB_PATH = os.environ.get("DB_PATH", "leaderboard.db")
PORT = 8765


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS players (username TEXT PRIMARY KEY, pin_hash TEXT NOT NULL)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS scores ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, score INTEGER, "
        "level INTEGER, achieved_at TEXT DEFAULT CURRENT_TIMESTAMP)"
    )
    return conn


def hash_pin(username, pin):
    return hashlib.sha256(f"{username}:{pin}".encode()).hexdigest()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def send_json(self, payload, status=200):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if parsed.path == "/ping":
            self.send_json({"ok": True, "message": "pong"})
            return

        if parsed.path == "/login":
            username = params.get("username", [""])[0].strip()
            pin = params.get("pin", [""])[0].strip()
            if not username or not (pin.isdigit() and len(pin) == 4):
                self.send_json({"ok": False, "error": "invalid_input"}, 400)
                return

            conn = get_connection()
            row = conn.execute(
                "SELECT pin_hash FROM players WHERE username = ?", (username,)
            ).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO players (username, pin_hash) VALUES (?, ?)",
                    (username, hash_pin(username, pin)),
                )
                conn.commit()
                conn.close()
                self.send_json({"ok": True, "new": True})
                return

            conn.close()
            if row[0] == hash_pin(username, pin):
                self.send_json({"ok": True, "new": False})
            else:
                self.send_json({"ok": False, "error": "wrong_pin"}, 403)
            return

        if parsed.path == "/submit_score":
            username = params.get("username", [""])[0].strip()
            pin = params.get("pin", [""])[0].strip()
            try:
                score = int(params.get("score", ["0"])[0])
                level = int(params.get("level", ["0"])[0])
            except ValueError:
                self.send_json({"ok": False, "error": "invalid_input"}, 400)
                return

            conn = get_connection()
            row = conn.execute(
                "SELECT pin_hash FROM players WHERE username = ?", (username,)
            ).fetchone()
            if row is None or row[0] != hash_pin(username, pin):
                conn.close()
                self.send_json({"ok": False, "error": "wrong_pin"}, 403)
                return

            conn.execute(
                "INSERT INTO scores (username, score, level) VALUES (?, ?, ?)",
                (username, score, level),
            )
            conn.commit()
            conn.close()
            self.send_json({"ok": True})
            return

        if parsed.path == "/leaderboard":
            try:
                limit = int(params.get("limit", ["10"])[0])
            except ValueError:
                limit = 10

            conn = get_connection()
            rows = conn.execute(
                "SELECT username, MAX(score) AS best, MAX(level) AS lvl "
                "FROM scores GROUP BY username ORDER BY best DESC LIMIT ?",
                (limit,),
            ).fetchall()
            conn.close()
            entries = [{"username": r[0], "score": r[1], "level": r[2]} for r in rows]
            self.send_json({"ok": True, "entries": entries})
            return

        self.send_json({"ok": False, "error": "not_found"}, 404)


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Leaderboard server running on http://0.0.0.0:{PORT}")
    server.serve_forever()

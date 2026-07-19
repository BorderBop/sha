# sha

A territory-capture arcade game (Qix-style): the cursor drags a line from the frame/already-captured blocks, cut-off areas get painted in, and balls bouncing around the field try to touch the unfinished line and ruin the attempt.

The project is mainly a demo of two libraries working together:

- **[pygame-ce](https://pyga.me/)** — all the game logic, physics, and rendering are written with it like an ordinary desktop game.
- **[pygbag](https://github.com/pygame-web/pygbag)** — compiles that same pygame game to WASM and runs it right in the browser, with no JS rewrite. The exact same code (`main.py` + modules) works both as `python3 main.py` on a computer and as a full web game.

On top of that, a small pure-Python server (`leaderboard_server.py`, no frameworks, just stdlib + SQLite) provides simple name + 4-digit PIN login and a global leaderboard, which the browser client talks to over `pygbag`'s HTTP fetch.

## Game features

- Territory capture via the cursor's line, checked through grid-based flood fill
- Ball hazards: one more gets added every level
- Levels (advance on capturing a set % of the field), a per-level countdown timer (2 minutes for level 1, +1 minute per level, run out of time and it's Game Over), 3 lives, a Game Over screen with restart
- Ball speed ramps up over the level - half base speed at the start, double by the time the timer runs out
- Scoring (percent × difficulty), a banked total that carries over between levels
- Pause (Space), a rotating animated cursor, a side info panel (level / time left / progress / score / lives / leaderboard)
- Name + PIN login, global leaderboard of best scores

## Project structure

| File | Purpose |
|---|---|
| `main.py` | entry point, game loop, login screen, HUD |
| `config.py` | all constants (sizes, colors, speeds, API address) |
| `ball.py`, `cursor.py`, `obstacles.py` | game entities |
| `physics.py` | ball-vs-ball and ball-vs-obstacle collisions |
| `trail.py` | cursor line logic: touching walls, breaking on a ball hit |
| `capture.py` | flood-fill capture of the enclosed territory |
| `scoring.py` | the score formula |
| `images.py` | sprite loading |
| `net.py` | client-side networking — the only place that uses pygbag's `aio.fetch` (browser-only) |
| `leaderboard_server.py` | leaderboard server: HTTP + SQLite, no external dependencies |
| `pics/` | sprites |

## Running locally (development)

Plain desktop mode, no browser and no leaderboard server:

```bash
python3 main.py
```

The full stack (game in the browser + leaderboard server) with one command:

```bash
./run.sh
```

Starts `leaderboard_server.py` on `http://localhost:8765` and the pygbag dev server on `http://localhost:8000`. `Ctrl+C` stops both.

## Deploying to a server (Hetzner)

The game is deployed at `games.glamkit.ai`. The leaderboard server runs in a Docker container; the game's static files and HTTPS are served by the system Caddy already running on that server (not a container of our own - that's why `docker-compose.yml` has no Caddy service, only `leaderboard`).

### Initial setup

```bash
cd /opt
git clone https://github.com/BorderBop/sha.git
cd sha
```

Set up the production override (done once - this file is gitignored, so it survives every future `git pull` without conflicts):
```bash
cp local_settings.example.py local_settings.py
```
It sets `LEADERBOARD_BASE_URL = "/api"` (a relative path - the browser resolves it against the same domain the page was served from). `config.py` imports `local_settings.py` at the end if present, so this overrides the `http://localhost:8765` default used for local development, where there's no proxy in front of the leaderboard server.

Build the static client and bring up the leaderboard server container:
```bash
python3 -m pygbag --build main.py
docker compose up -d --build
```

Add the block from this repo's `Caddyfile` to the end of the existing `/etc/caddy/Caddyfile` (the `root` path should point at `/opt/sha/build/web`), then:
```bash
caddy validate --config /etc/caddy/Caddyfile
systemctl reload caddy
```

### Updating (after code changes)

```bash
cd /opt/sha
git pull

# if the client changed (main.py and other game modules)
python3 -m pygbag --build main.py

# if leaderboard_server.py changed
docker compose up -d --build

# the Caddyfile usually doesn't need touching again
```

The leaderboard is stored in a named Docker volume (`leaderboard_data`) and **is not lost** on a regular update - the volume survives a container rebuild/restart. It's only wiped by an explicit `docker compose down -v`.

Post-deploy check:
```bash
curl https://games.glamkit.ai/api/ping
```

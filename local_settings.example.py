# Copy this file to local_settings.py (gitignored) and adjust for this
# environment. config.py imports it at the end if present, so anything
# defined here overrides the defaults in config.py - and since the real
# local_settings.py is never tracked by git, `git pull` will never
# conflict with it again.

# Production build: same-origin relative path, resolved by the browser
# against whatever domain the page is served from
LEADERBOARD_BASE_URL = "/api"

import sys
import json

# aio.fetch only exists inside the compiled pygbag runtime in the browser -
# just importing it starts a background event loop and breaks a normal
# asyncio.run() when running natively (python3 main.py), so we only import
# it when actually running in the browser
IS_BROWSER = sys.platform == "emscripten"

if IS_BROWSER:
    from aio.fetch import RequestHandler

    _handler = RequestHandler()


async def login(base_url, username, pin):
    text = await _handler.get(f"{base_url}/login", params={"username": username, "pin": pin})
    return json.loads(text)


async def submit_score(base_url, username, pin, score, level, balls_isolated):
    text = await _handler.get(
        f"{base_url}/submit_score",
        params={
            "username": username, "pin": pin, "score": score,
            "level": level, "balls_isolated": balls_isolated,
        },
    )
    return json.loads(text)


async def fetch_leaderboard(base_url, limit=10):
    text = await _handler.get(f"{base_url}/leaderboard", params={"limit": limit})
    return json.loads(text)

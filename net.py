import sys
import json

# aio.fetch существует только внутри скомпилированного pygbag-рантайма в
# браузере - сам его импорт запускает фоновый event loop и ломает обычный
# asyncio.run() при нативном запуске (python3 main.py), поэтому подключаем
# его только когда реально работаем в браузере
IS_BROWSER = sys.platform == "emscripten"

if IS_BROWSER:
    from aio.fetch import RequestHandler

    _handler = RequestHandler()


async def login(base_url, username, pin):
    text = await _handler.get(f"{base_url}/login", params={"username": username, "pin": pin})
    return json.loads(text)


async def submit_score(base_url, username, pin, score, level):
    text = await _handler.get(
        f"{base_url}/submit_score",
        params={"username": username, "pin": pin, "score": score, "level": level},
    )
    return json.loads(text)


async def fetch_leaderboard(base_url, limit=10):
    text = await _handler.get(f"{base_url}/leaderboard", params={"limit": limit})
    return json.loads(text)

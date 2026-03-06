"""
텔레그램 메시지 대시보드
========================

수집된 텔레그램 메시지를 브라우저에서 확인하는 Flask 앱입니다.

실행 방법:
    python dashboard.py

브라우저에서 http://서버주소:8502 접속
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from flask import Flask, render_template

app = Flask(__name__)


def load_dotenv_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def get_messages_path() -> Path:
    return Path(os.getenv("TELEGRAM_OUTPUT_FILE", "data/telegram_messages.json"))


def load_messages() -> tuple[dict[str, object] | None, list[dict[str, object]], str | None]:
    path = get_messages_path()
    if not path.exists():
        return None, [], f"메시지 파일이 없습니다: {path}"

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None, [], f"JSON 파일 형식이 올바르지 않습니다: {path}"

    if isinstance(payload, list):
        messages = payload
        payload = {
            "channel": "unknown",
            "channel_title": "Telegram Dashboard",
            "message_count": len(messages),
            "messages": messages,
        }
    else:
        messages = payload.get("messages", [])

    if not isinstance(messages, list):
        return None, [], "messages 필드가 리스트가 아닙니다."

    return payload, messages, None


@app.route("/")
def index():
    load_dotenv_file(Path(".env"))
    payload, messages, error = load_messages()

    total = len(messages)
    total_views = sum((message.get("views") or 0) for message in messages)
    media_count = sum(1 for message in messages if message.get("has_media"))

    stats = {
        "total": total,
        "total_views": total_views,
        "avg_views": total_views // total if total else 0,
        "media_count": media_count,
    }

    return render_template(
        "dashboard.html",
        messages=messages,
        stats=stats,
        error=error,
        channel_title=(payload or {}).get("channel_title", "Telegram Dashboard"),
        channel_name=(payload or {}).get("channel", ""),
        data_file=str(get_messages_path()),
    )


if __name__ == "__main__":
    load_dotenv_file(Path(".env"))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    host = os.getenv("DASHBOARD_HOST", "0.0.0.0")
    port = int(os.getenv("DASHBOARD_PORT", "8502"))
    app.run(debug=debug, host=host, port=port)

"""
텔레그램 메시지 대시보드
========================
수집된 텔레그램 메시지를 웹 브라우저에서 확인할 수 있는 대시보드입니다.

실행 방법:
    ./venv/bin/python dashboard.py

브라우저에서 http://서버주소:8502 접속
"""

import json
from pathlib import Path
from flask import Flask, render_template

app = Flask(__name__)

DATA_FILE = Path(__file__).parent / "telegram_messages.json"


def load_messages():
    """JSON 파일에서 메시지를 로드합니다. 파일이 없거나 깨지면 빈 리스트를 반환합니다."""
    if not DATA_FILE.exists():
        return []
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


@app.route("/")
def index():
    messages = load_messages()

    # 기본 통계 계산
    total = len(messages)
    total_views = sum(m.get("views") or 0 for m in messages)
    media_count = sum(1 for m in messages if m.get("has_media"))

    stats = {
        "total": total,
        "total_views": total_views,
        "avg_views": total_views // total if total else 0,
        "media_count": media_count,
    }

    return render_template("dashboard.html", messages=messages, stats=stats)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8502)

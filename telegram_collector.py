"""
텔레그램 채널 메시지 수집기
==========================
텔레그램 채널의 메시지를 수집해서 JSON 파일로 저장하는 스크립트입니다.

사전 준비:
1. pip install telethon 으로 라이브러리 설치
2. https://my.telegram.org 에 접속하여 로그인
3. "API development tools" 메뉴에서 앱을 생성
4. .env 파일에 API_ID, API_HASH 등을 입력
"""

import json
import asyncio
import os
from pathlib import Path
from telethon import TelegramClient


def load_env():
    """프로젝트 루트의 .env 파일에서 환경변수를 읽어옵니다."""
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


# .env 파일 로드
load_env()

# ============================================================
# [설정] .env 파일에서 읽어옵니다
# ============================================================
API_ID = int(os.environ.get("TELEGRAM_API_ID", "0"))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "")
CHANNEL = os.environ.get("TELEGRAM_CHANNEL", "")
MESSAGE_LIMIT = int(os.environ.get("TELEGRAM_MESSAGE_LIMIT", "100"))

# 저장할 JSON 파일 이름
OUTPUT_FILE = "telegram_messages.json"


async def collect_messages():
    """텔레그램 채널에서 메시지를 수집하는 메인 함수"""

    # 필수 설정값 확인
    if not API_ID or not API_HASH or not CHANNEL:
        print("오류: .env 파일에 TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_CHANNEL을 설정해주세요.")
        return

    # 텔레그램 클라이언트 생성 (세션 파일이 자동으로 만들어짐)
    client = TelegramClient("session", API_ID, API_HASH)

    # 클라이언트 시작 (처음 실행 시 전화번호 인증 필요)
    await client.start()
    print("텔레그램에 연결되었습니다.")

    # 채널 정보 가져오기
    try:
        channel = await client.get_entity(CHANNEL)
        print(f"채널 '{channel.title}' 에서 메시지를 수집합니다...")
    except ValueError:
        print(f"오류: '{CHANNEL}' 채널을 찾을 수 없습니다.")
        print("채널 이름이 올바른지 확인해주세요.")
        await client.disconnect()
        return

    # 메시지를 저장할 리스트
    messages = []

    # 채널의 메시지를 하나씩 가져오기
    async for message in client.iter_messages(channel, limit=MESSAGE_LIMIT):
        # 메시지 데이터를 딕셔너리로 정리
        msg_data = {
            # 메시지 고유 ID
            "id": message.id,
            # 메시지 전송 날짜 (문자열로 변환)
            "date": message.date.isoformat() if message.date else None,
            # 메시지 텍스트 내용
            "text": message.text or "",
            # 보낸 사람 ID
            "sender_id": message.sender_id,
            # 조회수 (있는 경우)
            "views": message.views,
            # 미디어 포함 여부
            "has_media": message.media is not None,
            # 미디어 종류 (사진, 동영상 등)
            "media_type": type(message.media).__name__ if message.media else None,
        }

        messages.append(msg_data)

    print(f"총 {len(messages)}개의 메시지를 수집했습니다.")

    # JSON 파일로 저장
    # ensure_ascii=False: 한글이 깨지지 않도록 설정
    # indent=2: 보기 좋게 들여쓰기
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)

    print(f"'{OUTPUT_FILE}' 파일로 저장 완료!")

    # 연결 종료
    await client.disconnect()


# 스크립트를 직접 실행할 때만 동작
if __name__ == "__main__":
    asyncio.run(collect_messages())

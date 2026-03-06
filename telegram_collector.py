"""
텔레그램 채널 메시지 수집기
==========================
텔레그램 채널의 메시지를 수집해서 JSON 파일로 저장하는 스크립트입니다.

사전 준비:
1. pip install telethon 으로 라이브러리 설치
2. https://my.telegram.org 에 접속하여 로그인
3. "API development tools" 메뉴에서 앱을 생성
4. 생성된 api_id와 api_hash를 아래 설정에 입력
"""

import json
import asyncio
from datetime import datetime
from telethon import TelegramClient

# ============================================================
# [설정] 여기에 본인의 정보를 입력하세요
# ============================================================

# my.telegram.org에서 발급받은 API 인증 정보
API_ID = 32148474
API_HASH = "63f288405cb66c3fb9997b251c7f0bb7"

# 수집할 채널의 username 또는 링크
# 예: "https://t.me/channel_name" 또는 "@channel_name" 또는 "channel_name"
CHANNEL = "https://t.me/HanaResearch"

# 수집할 메시지 개수 (None으로 설정하면 전체 메시지 수집)
MESSAGE_LIMIT = 100

# 저장할 JSON 파일 이름
OUTPUT_FILE = "telegram_messages.json"

# ============================================================


async def collect_messages():
    """텔레그램 채널에서 메시지를 수집하는 메인 함수"""

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

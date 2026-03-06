"""
텔레그램 채널 메시지 수집기
==========================

사전 준비:
1. pip install -r requirements.txt
2. https://my.telegram.org 에 접속하여 로그인
3. "API development tools" 메뉴에서 앱을 생성
4. .env 파일에 API_ID, API_HASH 등을 입력
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError


DEFAULT_OUTPUT_FILE = "data/telegram_messages.json"
DEFAULT_SESSION_FILE = "data/telegram_session"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="텔레그램 채널 메시지를 JSON 파일로 저장합니다."
    )
    parser.add_argument(
        "--channel",
        default=os.getenv("TELEGRAM_CHANNEL", "https://t.me/채널이름"),
        help="수집할 채널 username 또는 링크입니다.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=int(os.getenv("TELEGRAM_MESSAGE_LIMIT", "100")),
        help="가져올 메시지 개수입니다. 기본값은 100입니다.",
    )
    parser.add_argument(
        "--output",
        default=os.getenv("TELEGRAM_OUTPUT_FILE", DEFAULT_OUTPUT_FILE),
        help="메시지를 저장할 JSON 파일 경로입니다.",
    )
    parser.add_argument(
        "--session",
        default=os.getenv("TELEGRAM_SESSION_FILE", DEFAULT_SESSION_FILE),
        help="텔레그램 로그인 세션 파일 경로입니다.",
    )
    return parser.parse_args()


def load_dotenv_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def get_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"환경변수 {name} 값이 비어 있습니다.")
    return value


def normalize_channel(channel: str) -> str:
    cleaned = channel.strip()
    if cleaned.startswith("https://t.me/"):
        cleaned = cleaned.removeprefix("https://t.me/")
    if cleaned.startswith("http://t.me/"):
        cleaned = cleaned.removeprefix("http://t.me/")
    if not cleaned.startswith("@"):
        cleaned = f"@{cleaned}"
    return cleaned


async def login_if_needed(client: TelegramClient, phone: str) -> None:
    await client.connect()
    if await client.is_user_authorized():
        return

    await client.send_code_request(phone)
    code = input("텔레그램으로 받은 로그인 코드를 입력하세요: ").strip()

    try:
        await client.sign_in(phone=phone, code=code)
    except SessionPasswordNeededError:
        password = input("2단계 인증 비밀번호를 입력하세요: ").strip()
        await client.sign_in(password=password)


def convert_message(message: Any) -> dict[str, Any]:
    return {
        "id": message.id,
        "date": message.date.isoformat() if message.date else None,
        "text": message.text or "",
        "sender_id": message.sender_id,
        "views": message.views,
        "has_media": message.media is not None,
        "media_type": type(message.media).__name__ if message.media else None,
    }


async def collect_messages(args: argparse.Namespace) -> Path:
    load_dotenv_file(Path(".env"))

    api_id = int(get_env("TELEGRAM_API_ID"))
    api_hash = get_env("TELEGRAM_API_HASH")
    phone = get_env("TELEGRAM_PHONE")
    channel_name = normalize_channel(args.channel)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    session_path = Path(args.session)
    session_path.parent.mkdir(parents=True, exist_ok=True)

    client = TelegramClient(str(session_path), api_id, api_hash)
    await login_if_needed(client, phone)

    try:
        try:
            channel = await client.get_entity(channel_name)
        except ValueError as error:
            raise ValueError(
                f"채널을 찾지 못했습니다: {channel_name}. username 또는 링크를 다시 확인하세요."
            ) from error

        print(f"채널 '{channel.title}' 에서 메시지를 수집합니다...")

        messages: list[dict[str, Any]] = []
        async for message in client.iter_messages(channel, limit=args.limit):
            messages.append(convert_message(message))

        messages.reverse()
        payload = {
            "channel": channel_name,
            "channel_title": getattr(channel, "title", channel_name),
            "message_count": len(messages),
            "messages": messages,
        }

        output_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"총 {len(messages)}개의 메시지를 '{output_path}' 로 저장했습니다.")
        return output_path
    finally:
        await client.disconnect()


def main() -> None:
    args = parse_args()
    try:
        asyncio.run(collect_messages(args))
    except Exception as error:
        print(f"오류: {error}")


if __name__ == "__main__":
    main()

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
from telethon.errors import (
    InviteHashExpiredError,
    InviteHashInvalidError,
    SessionPasswordNeededError,
    UserAlreadyParticipantError,
)
from telethon.tl.functions.messages import CheckChatInviteRequest, ImportChatInviteRequest
from telethon.tl.types import ChatInviteAlready


DEFAULT_OUTPUT_FILE = "data/telegram_messages.json"
DEFAULT_SESSION_FILE = "data/telegram_session"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="텔레그램 채널 메시지를 JSON 파일로 저장합니다."
    )
    parser.add_argument(
        "--channel",
        default=os.getenv("TELEGRAM_CHANNEL", "https://t.me/채널이름"),
        help="수집할 채널 username, 공개 링크, 비공개 초대 링크입니다.",
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
    parser.add_argument(
        "--pick-dialog",
        action="store_true",
        default=os.getenv("TELEGRAM_PICK_DIALOG", "false").lower() == "true",
        help="현재 계정이 참여 중인 채널/그룹 목록을 보여주고 번호로 선택합니다.",
    )
    parser.add_argument(
        "--list-dialogs",
        action="store_true",
        help="현재 계정이 참여 중인 채널/그룹 목록만 출력하고 종료합니다.",
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
    cleaned = channel.strip().rstrip("/")
    if cleaned.startswith("https://t.me/"):
        cleaned = cleaned.removeprefix("https://t.me/")
    if cleaned.startswith("http://t.me/"):
        cleaned = cleaned.removeprefix("http://t.me/")
    if cleaned.startswith("t.me/"):
        cleaned = cleaned.removeprefix("t.me/")
    if not cleaned.startswith("@"):
        cleaned = f"@{cleaned}"
    return cleaned


def extract_invite_hash(channel: str) -> str | None:
    cleaned = channel.strip().rstrip("/")
    prefixes = (
        "https://t.me/+",
        "http://t.me/+",
        "t.me/+",
        "+",
        "https://t.me/joinchat/",
        "http://t.me/joinchat/",
        "t.me/joinchat/",
        "joinchat/",
    )
    for prefix in prefixes:
        if cleaned.startswith(prefix):
            return cleaned.removeprefix(prefix)
    return None


def describe_entity(entity: Any) -> tuple[str, str]:
    username = getattr(entity, "username", None)
    title = getattr(entity, "title", None) or getattr(entity, "first_name", None)
    label = f"@{username}" if username else title or str(getattr(entity, "id", "unknown"))
    return label, title or label


def describe_dialog(dialog: Any) -> tuple[Any, str, str, str, str]:
    entity = dialog.entity
    label, title = describe_entity(entity)
    kind = "channel" if dialog.is_channel and getattr(entity, "broadcast", False) else "group"
    visibility = "public" if getattr(entity, "username", None) else "private"
    return entity, label, dialog.name or title, kind, visibility


def print_dialog_options(dialogs: list[tuple[Any, str, str, str, str]]) -> None:
    print("현재 계정이 참여 중인 채널/그룹 목록입니다.")
    for index, dialog in enumerate(dialogs, start=1):
        _, label, title, kind, visibility = dialog
        print(f"{index:>3}. [{visibility}/{kind}] {title} ({label})")


def choose_dialog_option(dialogs: list[tuple[Any, str, str, str, str]]) -> tuple[Any, str, str]:
    while True:
        raw_value = input("수집할 번호를 입력하세요. 취소하려면 q를 입력하세요: ").strip()
        if raw_value.lower() == "q":
            raise ValueError("채널/그룹 선택이 취소되었습니다.")
        if not raw_value.isdigit():
            print("숫자 번호를 입력하세요.")
            continue

        index = int(raw_value)
        if 1 <= index <= len(dialogs):
            entity, label, title, _, _ = dialogs[index - 1]
            return entity, label, title
        print("목록 안의 번호를 입력하세요.")


async def find_joined_dialog(client: TelegramClient, value: str) -> Any | None:
    lookup = value.strip().lower().lstrip("@")
    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        candidates = {
            dialog.name.lower(),
            str(getattr(entity, "id", "")).lower(),
        }
        username = getattr(entity, "username", None)
        if username:
            candidates.add(username.lower())
            candidates.add(f"@{username.lower()}")
        if lookup in candidates:
            return entity
    return None


async def load_collectable_dialogs(client: TelegramClient) -> list[tuple[Any, str, str, str, str]]:
    dialogs: list[tuple[Any, str, str, str, str]] = []
    async for dialog in client.iter_dialogs():
        if not (dialog.is_channel or dialog.is_group):
            continue
        dialogs.append(describe_dialog(dialog))
    dialogs.sort(key=lambda dialog: (dialog[2].lower(), dialog[1].lower()))
    return dialogs


async def resolve_target(client: TelegramClient, raw_value: str) -> tuple[Any, str, str]:
    invite_hash = extract_invite_hash(raw_value)
    if invite_hash:
        try:
            invite_result = await client(ImportChatInviteRequest(invite_hash))
        except UserAlreadyParticipantError:
            invite_result = await client(CheckChatInviteRequest(invite_hash))
            if isinstance(invite_result, ChatInviteAlready):
                label, title = describe_entity(invite_result.chat)
                return invite_result.chat, label, title
            raise ValueError("이미 참여 중인 비공개 대화를 찾지 못했습니다.")
        except (InviteHashInvalidError, InviteHashExpiredError) as error:
            raise ValueError("비공개 초대 링크가 유효하지 않거나 만료되었습니다.") from error

        chats = getattr(invite_result, "chats", None) or []
        if chats:
            label, title = describe_entity(chats[0])
            return chats[0], label, title
        raise ValueError("비공개 초대 링크에서 대화 정보를 찾지 못했습니다.")

    normalized = normalize_channel(raw_value)
    try:
        entity = await client.get_entity(normalized)
    except ValueError:
        entity = await find_joined_dialog(client, raw_value)
        if entity is None:
            raise ValueError(
                "대화를 찾지 못했습니다. 공개 채널이면 @username을, 비공개 방이면 초대 링크 또는 이미 참여 중인 정확한 대화 이름을 사용하세요."
            ) from None

    label, title = describe_entity(entity)
    return entity, label, title


async def resolve_target_from_args(
    client: TelegramClient,
    channel_value: str | None,
    pick_dialog: bool,
    list_dialogs: bool,
) -> tuple[Any, str, str] | None:
    dialogs: list[tuple[Any, str, str, str, str]] = []
    if pick_dialog or list_dialogs:
        dialogs = await load_collectable_dialogs(client)
        if not dialogs:
            raise ValueError("현재 계정이 참여 중인 채널/그룹이 없습니다.")
        print_dialog_options(dialogs)
        if list_dialogs and not pick_dialog:
            return None
        if pick_dialog:
            return choose_dialog_option(dialogs)

    normalized_input = (channel_value or "").strip()
    if not normalized_input:
        raise ValueError(
            "--channel 값을 넣거나 TELEGRAM_PICK_DIALOG=true 또는 --pick-dialog 로 목록 선택을 사용하세요."
        )
    return await resolve_target(client, normalized_input)


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


async def collect_messages(args: argparse.Namespace) -> Path | None:
    load_dotenv_file(Path(".env"))

    api_id = int(get_env("TELEGRAM_API_ID"))
    api_hash = get_env("TELEGRAM_API_HASH")
    phone = get_env("TELEGRAM_PHONE")
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    session_path = Path(args.session)
    session_path.parent.mkdir(parents=True, exist_ok=True)

    client = TelegramClient(str(session_path), api_id, api_hash)
    await login_if_needed(client, phone)

    try:
        resolved_target = await resolve_target_from_args(
            client=client,
            channel_value=args.channel,
            pick_dialog=args.pick_dialog,
            list_dialogs=args.list_dialogs,
        )
        if resolved_target is None:
            return None
        channel, channel_label, channel_title = resolved_target
        print(f"채널 '{channel_title}' 에서 메시지를 수집합니다...")

        messages: list[dict[str, Any]] = []
        async for message in client.iter_messages(channel, limit=args.limit):
            messages.append(convert_message(message))

        messages.reverse()
        payload = {
            "channel": channel_label,
            "channel_title": channel_title,
            "channel_input": args.channel,
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
    load_dotenv_file(Path(".env"))
    args = parse_args()
    try:
        output_path = asyncio.run(collect_messages(args))
        if output_path is not None:
            print(f"저장 완료: {output_path}")
    except Exception as error:
        print(f"오류: {error}")


if __name__ == "__main__":
    main()

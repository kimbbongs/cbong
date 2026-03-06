# cbong

텔레그램 채널 메시지를 수집하고 웹 대시보드로 보는 간단한 프로젝트입니다.

## 준비

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

`.env`에 아래 값을 채웁니다.

```text
TELEGRAM_API_ID=
TELEGRAM_API_HASH=
TELEGRAM_PHONE=
```

## 메시지 수집

```bash
python telegram_collector.py
```

수집 결과는 기본적으로 `data/telegram_messages.json` 파일에 저장됩니다.
공개 채널 username뿐 아니라 `https://t.me/+초대코드` 같은 비공개 초대 링크도 사용할 수 있습니다.

## 대시보드 실행

```bash
python dashboard.py
```

브라우저에서 `http://localhost:8502` 로 접속합니다.

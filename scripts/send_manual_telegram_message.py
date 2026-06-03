import os
import re
import time
from pathlib import Path

import requests


MESSAGE_PATH = Path(os.getenv("MESSAGE_PATH", "manual_telegram_message.txt"))
MAX_LEN = 3800
PARSE_MODE = os.getenv("TELEGRAM_PARSE_MODE", "").strip()


def split_message(text: str, limit: int = MAX_LEN) -> list[str]:
    if PARSE_MODE.upper() == "HTML" and visible_len(text) <= limit:
        return [text.strip()]

    chunks: list[str] = []
    remaining = text.strip()

    while remaining:
        if len(remaining) <= limit:
            chunks.append(remaining)
            break

        cut = remaining.rfind("\n\n", 0, limit)
        if cut < limit // 2:
            cut = remaining.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = limit

        chunks.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()

    return chunks


def visible_len(text: str) -> int:
    return len(re.sub(r"<[^>]+>", "", text))


def main() -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"].strip()
    chat_id = os.environ["TELEGRAM_CHAT_ID"].strip()
    text = MESSAGE_PATH.read_text(encoding="utf-8")

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    chunks = split_message(text)

    for idx, chunk in enumerate(chunks, start=1):
        prefix = f"[{idx}/{len(chunks)}]\n" if len(chunks) > 1 else ""
        response = requests.post(
            url,
            json={
                "chat_id": chat_id,
                "text": prefix + chunk,
                **({"parse_mode": PARSE_MODE} if PARSE_MODE else {}),
                "disable_web_page_preview": False,
            },
            timeout=30,
        )
        if response.status_code >= 400:
            print(f"telegram send failed: HTTP {response.status_code} {response.text}")
        response.raise_for_status()
        data = response.json()
        if not data.get("ok"):
            raise RuntimeError(data)
        time.sleep(0.8)

    print(f"sent {len(chunks)} telegram message(s)")


if __name__ == "__main__":
    main()

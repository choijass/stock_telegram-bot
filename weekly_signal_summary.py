from __future__ import annotations

import os
import pathlib

import requests

from tools_render_signal_mobile_versions import THEMES, render


def send_telegram_photo(image_path: pathlib.Path) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    required = os.getenv("TELEGRAM_REQUIRED", "").lower() == "true"

    if not token or not chat_id:
        message = "TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID가 없어 텔레그램 발송을 건너뜁니다."
        if required:
            raise RuntimeError(message)
        print(message)
        return

    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    with image_path.open("rb") as image_file:
        response = requests.post(
            url,
            data={
                "chat_id": chat_id,
                "caption": "SIGNAL 주간요약 · 03 프리미엄 블랙",
            },
            files={"photo": image_file},
            timeout=60,
        )
    response.raise_for_status()
    print(f"텔레그램 발송 완료: {image_path}")


def main() -> None:
    premium_black = next(theme for theme in THEMES if theme["num"] == "03")
    image_path = render(premium_black)
    send_telegram_photo(image_path)


if __name__ == "__main__":
    main()

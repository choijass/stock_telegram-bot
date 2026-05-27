import asyncio
import os

from telethon import TelegramClient
from telethon.sessions import StringSession


async def main():
    api_id = int(os.environ["TELEGRAM_API_ID"])
    api_hash = os.environ["TELEGRAM_API_HASH"]

    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.start()
    try:
        me = await client.get_me()
        if getattr(me, "bot", False):
            raise RuntimeError("User account login is required, not a bot token.")

        print("\nTELEGRAM_SESSION_STRING:")
        print(client.session.save())
        print("\nAdd this value to GitHub Actions Secrets as TELEGRAM_SESSION_STRING.")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())

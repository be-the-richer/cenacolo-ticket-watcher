"""Run this once by hand (`python send_test_message.py`) after setting
TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID, to confirm the bot can message you
before relying on the scheduled workflow."""
import os
import sys

from notify import send_telegram_message


def main() -> int:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    send_telegram_message(token, chat_id, "Cenacolo ticket watcher is wired up correctly.")
    print("Sent. Check Telegram.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

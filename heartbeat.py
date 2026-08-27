"""Daily health report for the ticket watcher."""

import os

from check_tickets import TARGET_DATES
from notify import send_telegram_message
from scraper import check_dates

STATUS_LABELS = {"available": "예매 가능", "unavailable": "매진"}


def main() -> int:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    try:
        statuses = check_dates(TARGET_DATES)
    except Exception as exc:
        send_telegram_message(token, chat_id, f"⚠️ 최후의 만찬 감시기 오류: {exc}")
        return 1

    lines = [
        "✅ 최후의 만찬 감시기 작동 중 — 페이지와 달력 판독 정상",
        *(f"{date}: {STATUS_LABELS[status]}" for date, status in statuses.items()),
    ]
    send_telegram_message(
        token,
        chat_id,
        "\n".join(lines),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

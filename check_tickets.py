import os
import sys
from datetime import date

from decision import decide
from notify import send_telegram_message
from scraper import check_dates
from state import load_state, save_state

STATE_PATH = "state.json"
TARGET_DATES = [date(2026, 9, 2), date(2026, 9, 9)]
EVENT_URL = "https://cenacolovinciano.vivaticket.it/en/event/cenacolo-vinciano/151991?idt=2547"

MESSAGES = {
    "available": (
        "\U0001f39f️ Появились билеты в Тайную вечерю на {date}! "
        "Бронируй скорее: " + EVENT_URL
    ),
    "failure": (
        "⚠️ Не удалось проверить билеты на {date} 3 раза подряд — "
        "возможно, сайт изменился. Проверь вручную: " + EVENT_URL
    ),
}


def main() -> int:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]

    state = load_state(STATE_PATH)

    try:
        statuses = check_dates(TARGET_DATES)
    except Exception as exc:
        print(f"Scrape failed: {exc}", file=sys.stderr)
        statuses = {d.isoformat(): "error" for d in TARGET_DATES}

    notifications, new_state = decide(state, statuses)

    for note in notifications:
        text = MESSAGES[note["kind"]].format(date=note["date"])
        send_telegram_message(token, chat_id, text)
        print(f"Sent {note['kind']} notification for {note['date']}")

    save_state(STATE_PATH, new_state)
    return 0


if __name__ == "__main__":
    sys.exit(main())

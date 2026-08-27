import os
import sys
from datetime import date

from decision import decide
from notify import send_telegram_message
from scraper import check_dates
from state import load_state, save_state

STATE_PATH = "state.json"
TARGET_DATES = [date(2026, 10, 30), date(2026, 11, 6)]
AVAILABLE_ALERT_REPEATS = 10
EVENT_URL = "https://cenacolovinciano.vivaticket.it/en/event/cenacolo-vinciano/151991?idt=2547"

MESSAGES = {
    "available": (
        "\U0001f39f️ 최후의 만찬 {date} 티켓이 열렸습니다! "
        "성인 2장을 바로 확인하세요: " + EVENT_URL
    ),
    "failure": (
        "⚠️ {date} 티켓을 3회 연속 확인하지 못했습니다. "
        "사이트를 직접 확인하세요: " + EVENT_URL
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
        try:
            repeats = AVAILABLE_ALERT_REPEATS if note["kind"] == "available" else 1
            for _ in range(repeats):
                send_telegram_message(token, chat_id, text)
        except Exception as exc:
            print(
                f"Failed to send {note['kind']} notification for {note['date']}: {exc}",
                file=sys.stderr,
            )
            if note["kind"] == "available":
                new_state[note["date"]]["notified"] = False
            elif note["kind"] == "failure":
                new_state[note["date"]]["warned"] = False
        else:
            print(f"Sent {note['kind']} notification for {note['date']}")

    save_state(STATE_PATH, new_state)
    return 0


if __name__ == "__main__":
    sys.exit(main())

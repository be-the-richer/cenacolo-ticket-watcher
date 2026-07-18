import requests

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def send_telegram_message(token: str, chat_id: str, text: str) -> None:
    response = requests.post(
        TELEGRAM_API.format(token=token),
        json={"chat_id": chat_id, "text": text},
        timeout=10,
    )
    response.raise_for_status()

from unittest.mock import patch, MagicMock

import pytest
import requests

from notify import send_telegram_message


@patch("notify.requests.post")
def test_sends_post_to_correct_telegram_url_with_payload(mock_post):
    mock_post.return_value = MagicMock(status_code=200)

    send_telegram_message("TOKEN123", "12345", "hello")

    mock_post.assert_called_once_with(
        "https://api.telegram.org/botTOKEN123/sendMessage",
        json={"chat_id": "12345", "text": "hello"},
        timeout=10,
    )


@patch("notify.requests.post")
def test_raises_on_http_error(mock_post):
    response = MagicMock(status_code=400)
    response.raise_for_status.side_effect = requests.HTTPError("bad request")
    mock_post.return_value = response

    with pytest.raises(requests.HTTPError):
        send_telegram_message("TOKEN123", "12345", "hello")

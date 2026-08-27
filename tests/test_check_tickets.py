from datetime import date
from unittest.mock import patch

import requests

import check_tickets


def test_main_sends_notification_and_saves_state_when_date_becomes_available(tmp_path, monkeypatch):
    state_path = tmp_path / "state.json"
    monkeypatch.setattr(check_tickets, "STATE_PATH", str(state_path))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "TOKEN")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "CHATID")

    with patch("check_tickets.check_dates") as mock_check_dates, \
         patch("check_tickets.send_telegram_message") as mock_send:
        mock_check_dates.return_value = {
            "2026-10-30": "available",
            "2026-11-06": "unavailable",
        }

        exit_code = check_tickets.main()

    assert exit_code == 0
    assert mock_send.call_count == 10
    sent_args = mock_send.call_args_list[0].args
    assert sent_args[0] == "TOKEN"
    assert sent_args[1] == "CHATID"
    assert "2026-10-30" in sent_args[2]

    saved = check_tickets.load_state(str(state_path))
    assert saved["2026-10-30"]["notified"] is True
    assert saved["2026-11-06"]["notified"] is False


def test_main_treats_scraper_exception_as_error_status_for_all_dates(tmp_path, monkeypatch):
    state_path = tmp_path / "state.json"
    monkeypatch.setattr(check_tickets, "STATE_PATH", str(state_path))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "TOKEN")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "CHATID")

    with patch("check_tickets.check_dates", side_effect=RuntimeError("site changed")), \
         patch("check_tickets.send_telegram_message") as mock_send:
        exit_code = check_tickets.main()

    assert exit_code == 0
    mock_send.assert_not_called()  # first failure, below the 3-run threshold

    saved = check_tickets.load_state(str(state_path))
    assert saved["2026-10-30"]["consecutive_failures"] == 1
    assert saved["2026-11-06"]["consecutive_failures"] == 1


def test_main_persists_state_when_one_of_two_sends_fails_mid_run(tmp_path, monkeypatch):
    state_path = tmp_path / "state.json"
    monkeypatch.setattr(check_tickets, "STATE_PATH", str(state_path))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "TOKEN")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "CHATID")

    # 2026-11-06 is already at 2 consecutive failures, so a third "error"
    # this run crosses the FAILURE_THRESHOLD and fires a "failure"
    # notification in the same run that 2026-10-30 fires an "available"
    # notification.
    check_tickets.save_state(
        str(state_path),
        {
            "2026-10-30": {
                "notified": False,
                "consecutive_failures": 0,
                "warned": False,
            },
            "2026-11-06": {
                "notified": False,
                "consecutive_failures": 2,
                "warned": False,
            },
        },
    )

    with patch("check_tickets.check_dates") as mock_check_dates, \
         patch("check_tickets.send_telegram_message") as mock_send:
        mock_check_dates.return_value = {
            "2026-10-30": "available",
            "2026-11-06": "error",
        }
        mock_send.side_effect = [None] * 10 + [requests.HTTPError("boom")]

        exit_code = check_tickets.main()

    assert exit_code == 0
    assert mock_send.call_count == 11

    saved = check_tickets.load_state(str(state_path))
    # The available notification sent successfully, so it stays notified.
    assert saved["2026-10-30"]["notified"] is True
    # The failure notification for 2026-11-06 raised, so its
    # flag is reverted so it gets retried on the next run instead of being
    # silently swallowed.
    assert saved["2026-11-06"]["warned"] is False
    assert saved["2026-11-06"]["consecutive_failures"] == 3

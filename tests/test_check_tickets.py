from datetime import date
from unittest.mock import patch

import check_tickets


def test_main_sends_notification_and_saves_state_when_date_becomes_available(tmp_path, monkeypatch):
    state_path = tmp_path / "state.json"
    monkeypatch.setattr(check_tickets, "STATE_PATH", str(state_path))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "TOKEN")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "CHATID")

    with patch("check_tickets.check_dates") as mock_check_dates, \
         patch("check_tickets.send_telegram_message") as mock_send:
        mock_check_dates.return_value = {
            "2026-09-02": "available",
            "2026-09-09": "unavailable",
        }

        exit_code = check_tickets.main()

    assert exit_code == 0
    mock_send.assert_called_once()
    sent_args = mock_send.call_args.args
    assert sent_args[0] == "TOKEN"
    assert sent_args[1] == "CHATID"
    assert "2026-09-02" in sent_args[2]

    saved = check_tickets.load_state(str(state_path))
    assert saved["2026-09-02"]["notified"] is True
    assert saved["2026-09-09"]["notified"] is False


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
    assert saved["2026-09-02"]["consecutive_failures"] == 1
    assert saved["2026-09-09"]["consecutive_failures"] == 1

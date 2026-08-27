import importlib.util

import heartbeat


def test_heartbeat_module_exists():
    assert importlib.util.find_spec("heartbeat") is not None


def test_main_reports_both_target_statuses(monkeypatch):
    sent = []
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "TOKEN")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "CHATID")
    monkeypatch.setattr(
        heartbeat,
        "check_dates",
        lambda dates: {"2026-10-30": "unavailable", "2026-11-06": "available"},
        raising=False,
    )
    monkeypatch.setattr(
        heartbeat,
        "send_telegram_message",
        lambda token, chat_id, text: sent.append((token, chat_id, text)),
        raising=False,
    )

    assert heartbeat.main() == 0
    assert sent[0][0:2] == ("TOKEN", "CHATID")
    assert "2026-10-30: 매진" in sent[0][2]
    assert "2026-11-06: 예매 가능" in sent[0][2]
    assert "페이지와 달력 판독 정상" in sent[0][2]


def test_main_warns_when_calendar_check_fails(monkeypatch):
    sent = []
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "TOKEN")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "CHATID")
    monkeypatch.setattr(
        heartbeat,
        "check_dates",
        lambda dates: (_ for _ in ()).throw(RuntimeError("calendar changed")),
    )
    monkeypatch.setattr(
        heartbeat,
        "send_telegram_message",
        lambda token, chat_id, text: sent.append(text),
    )

    assert heartbeat.main() == 1
    assert "감시기 오류" in sent[0]
    assert "calendar changed" in sent[0]

import json

from state import load_state, save_state


def test_load_state_returns_empty_dict_when_file_missing(tmp_path):
    path = tmp_path / "state.json"
    assert load_state(str(path)) == {}


def test_save_then_load_round_trips(tmp_path):
    path = tmp_path / "state.json"
    data = {"2026-09-02": {"notified": False, "consecutive_failures": 0, "warned": False}}

    save_state(str(path), data)
    loaded = load_state(str(path))

    assert loaded == data


def test_save_state_writes_readable_json_with_trailing_newline(tmp_path):
    path = tmp_path / "state.json"
    save_state(str(path), {"a": 1})

    raw = path.read_text()

    assert raw.endswith("\n")
    assert json.loads(raw) == {"a": 1}

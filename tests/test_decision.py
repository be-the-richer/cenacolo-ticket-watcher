from decision import decide


def fresh_entry():
    return {"notified": False, "consecutive_failures": 0, "warned": False}


def test_available_and_not_notified_triggers_notification_and_marks_notified():
    state = {"2026-09-02": fresh_entry()}
    statuses = {"2026-09-02": "available"}

    notifications, new_state = decide(state, statuses)

    assert notifications == [{"date": "2026-09-02", "kind": "available"}]
    assert new_state["2026-09-02"]["notified"] is True


def test_already_notified_date_is_skipped_even_if_available():
    state = {"2026-09-02": {"notified": True, "consecutive_failures": 0, "warned": False}}
    statuses = {"2026-09-02": "available"}

    notifications, new_state = decide(state, statuses)

    assert notifications == []
    assert new_state["2026-09-02"]["notified"] is True


def test_unavailable_produces_no_notification():
    state = {"2026-09-02": fresh_entry()}
    statuses = {"2026-09-02": "unavailable"}

    notifications, new_state = decide(state, statuses)

    assert notifications == []
    assert new_state["2026-09-02"]["notified"] is False


def test_error_below_threshold_sends_no_warning():
    state = {"2026-09-02": {"notified": False, "consecutive_failures": 1, "warned": False}}
    statuses = {"2026-09-02": "error"}

    notifications, new_state = decide(state, statuses)

    assert notifications == []
    assert new_state["2026-09-02"]["consecutive_failures"] == 2


def test_error_reaching_threshold_sends_warning_once():
    state = {"2026-09-02": {"notified": False, "consecutive_failures": 2, "warned": False}}
    statuses = {"2026-09-02": "error"}

    notifications, new_state = decide(state, statuses)

    assert notifications == [{"date": "2026-09-02", "kind": "failure"}]
    assert new_state["2026-09-02"]["warned"] is True


def test_error_already_warned_does_not_repeat_warning():
    state = {"2026-09-02": {"notified": False, "consecutive_failures": 5, "warned": True}}
    statuses = {"2026-09-02": "error"}

    notifications, new_state = decide(state, statuses)

    assert notifications == []


def test_success_after_failures_resets_counter_and_warned_flag():
    state = {"2026-09-02": {"notified": False, "consecutive_failures": 3, "warned": True}}
    statuses = {"2026-09-02": "unavailable"}

    notifications, new_state = decide(state, statuses)

    assert new_state["2026-09-02"]["consecutive_failures"] == 0
    assert new_state["2026-09-02"]["warned"] is False


def test_unknown_date_gets_a_fresh_entry_created():
    notifications, new_state = decide({}, {"2026-09-09": "unavailable"})

    assert new_state["2026-09-09"] == fresh_entry()

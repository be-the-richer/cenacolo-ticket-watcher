import copy

FAILURE_THRESHOLD = 3


def _fresh_entry() -> dict:
    return {"notified": False, "consecutive_failures": 0, "warned": False}


def decide(state: dict, statuses: dict) -> tuple:
    new_state = copy.deepcopy(state)
    notifications = []

    for date_str, status in statuses.items():
        entry = new_state.setdefault(date_str, _fresh_entry())

        if entry["notified"]:
            continue

        if status == "available":
            notifications.append({"date": date_str, "kind": "available"})
            entry["notified"] = True
            entry["consecutive_failures"] = 0
            entry["warned"] = False
        elif status == "error":
            entry["consecutive_failures"] += 1
            if entry["consecutive_failures"] >= FAILURE_THRESHOLD and not entry["warned"]:
                notifications.append({"date": date_str, "kind": "failure"})
                entry["warned"] = True
        else:  # "unavailable"
            entry["consecutive_failures"] = 0
            entry["warned"] = False

    return notifications, new_state

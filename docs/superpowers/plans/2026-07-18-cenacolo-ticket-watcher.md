# Cenacolo Vinciano Ticket Watcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a script that runs on a schedule via GitHub Actions, checks the official Cenacolo Vinciano (Last Supper, Milan) ticket calendar for 2026-09-02 and 2026-09-09, and sends a Telegram message the moment either date shows availability.

**Architecture:** A small Python package with four pure/isolated modules (`state.py`, `decision.py`, `notify.py`, `scraper.py`) wired together by an orchestrator script (`check_tickets.py`), invoked every 15 minutes by a GitHub Actions workflow. State (which dates were already notified) is persisted in `state.json`, committed back to the repo by the workflow after each run.

**Tech Stack:** Python 3.12, Playwright (sync API, headless Chromium) for scraping, `requests` for the Telegram Bot API, `pytest` for tests. No web framework, no database — a stateless script plus one JSON file.

## Global Constraints

- Target dates, hardcoded: `2026-09-02` and `2026-09-09` only.
- Ticket type: admission tickets only, event page `https://cenacolovinciano.vivaticket.it/en/event/cenacolo-vinciano/151991?idt=2547`.
- Notification channel: Telegram only (Bot API `sendMessage`), via `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` env vars (GitHub Secrets in CI).
- Once a date is notified as available, it is never re-checked or re-notified.
- Schedule: GitHub Actions cron `*/15 * * * *` (every 15 min; GitHub enforces a 5-minute floor and may delay firing under load — acceptable).
- State persists in `state.json` at repo root, committed back by the workflow after every run (Actions runners are stateless VMs).
- Repo is public (no billing limits on Actions minutes); no secrets ever committed to code, only referenced via `os.environ`.
- Failure alerting: if scraping errors 3 consecutive runs for a given date, send one Telegram warning for that date; reset the failure counter (and the "already warned" flag) as soon as a run succeeds again.

---

## File Structure

```
cenacolo-ticket-watcher/
├── requirements.txt
├── requirements-dev.txt
├── .gitignore
├── state.json
├── state.py
├── decision.py
├── notify.py
├── scraper.py
├── check_tickets.py
├── send_test_message.py
├── README.md
├── tests/
│   ├── test_state.py
│   ├── test_decision.py
│   ├── test_notify.py
│   └── test_check_tickets.py
└── .github/
    └── workflows/
        └── check.yml
```

---

### Task 1: Repo scaffolding + state persistence module

**Files:**
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `.gitignore`
- Create: `state.py`
- Create: `tests/test_state.py`

**Interfaces:**
- Produces: `load_state(path: str) -> dict` — returns `{}` if the file doesn't exist, else the parsed JSON object.
- Produces: `save_state(path: str, state: dict) -> None` — writes pretty-printed, sorted JSON with a trailing newline.

- [ ] **Step 1: Create the project scaffolding files**

`requirements.txt`:
```
playwright>=1.45
requests>=2.31
```

`requirements-dev.txt`:
```
-r requirements.txt
pytest>=8.0
```

`.gitignore`:
```
__pycache__/
*.pyc
.venv/
.pytest_cache/
```

- [ ] **Step 2: Set up a virtualenv and install dev dependencies**

Run:
```bash
cd ~/cenacolo-ticket-watcher
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```
Expected: dependencies install without errors.

- [ ] **Step 3: Write the failing tests for `state.py`**

`tests/test_state.py`:
```python
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
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `pytest tests/test_state.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'state'` (file doesn't exist yet).

- [ ] **Step 5: Implement `state.py`**

```python
import json
from pathlib import Path


def load_state(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text())


def save_state(path: str, state: dict) -> None:
    Path(path).write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `pytest tests/test_state.py -v`
Expected: 3 passed.

- [ ] **Step 7: Commit**

```bash
git add requirements.txt requirements-dev.txt .gitignore state.py tests/test_state.py
git commit -m "Add project scaffolding and state persistence module"
```

---

### Task 2: Notification decision logic

**Files:**
- Create: `decision.py`
- Create: `tests/test_decision.py`

**Interfaces:**
- Consumes: nothing from other modules (pure function, no I/O).
- Produces: `decide(state: dict, statuses: dict[str, str]) -> tuple[list[dict], dict]`
  - `statuses`: `{date_str: "available" | "unavailable" | "error"}`
  - Returns `(notifications, new_state)` where `notifications` is a list of
    `{"date": date_str, "kind": "available" | "failure"}` dicts, and
    `new_state` is a fresh dict with each date's `notified`,
    `consecutive_failures`, and `warned` fields updated. `check_tickets.py`
    (Task 5) consumes this signature directly.

- [ ] **Step 1: Write the failing tests**

`tests/test_decision.py`:
```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_decision.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'decision'`.

- [ ] **Step 3: Implement `decision.py`**

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_decision.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add decision.py tests/test_decision.py
git commit -m "Add notification decision logic"
```

---

### Task 3: Telegram notifier + manual wiring check

**Files:**
- Create: `notify.py`
- Create: `tests/test_notify.py`
- Create: `send_test_message.py`

**Interfaces:**
- Produces: `send_telegram_message(token: str, chat_id: str, text: str) -> None` — raises `requests.HTTPError` on a non-2xx response. Consumed by `check_tickets.py` (Task 5) and `send_test_message.py`.

- [ ] **Step 1: Write the failing tests**

`tests/test_notify.py`:
```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_notify.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'notify'`.

- [ ] **Step 3: Implement `notify.py`**

```python
import requests

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def send_telegram_message(token: str, chat_id: str, text: str) -> None:
    response = requests.post(
        TELEGRAM_API.format(token=token),
        json={"chat_id": chat_id, "text": text},
        timeout=10,
    )
    response.raise_for_status()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_notify.py -v`
Expected: 2 passed.

- [ ] **Step 5: Add a manual Telegram wiring check**

`send_test_message.py`:
```python
"""Run this once by hand (`python send_test_message.py`) after setting
TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID, to confirm the bot can message you
before relying on the scheduled workflow."""
import os
import sys

from notify import send_telegram_message


def main() -> int:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    send_telegram_message(token, chat_id, "Cenacolo ticket watcher is wired up correctly.")
    print("Sent. Check Telegram.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6: Commit**

```bash
git add notify.py tests/test_notify.py send_test_message.py
git commit -m "Add Telegram notifier and manual wiring check script"
```

---

### Task 4: Calendar scraper (Playwright)

**Files:**
- Create: `scraper.py`

**Interfaces:**
- Produces: `check_dates(target_dates: list[datetime.date]) -> dict[str, str]` — maps each date's ISO string to `"available"` or `"unavailable"`. Raises on unrecoverable scraping failure (caught by `check_tickets.py` in Task 5, which converts that into `"error"` status for every requested date). Consumed by `check_tickets.py`.

**Design notes (from live site research, 2026-07-18):**
The booking calendar on the event page is rendered inside a same-page but
cross-origin `<iframe>` (a third-party "Bestunion/Qub" booking widget) — it
does not appear in `document.querySelector` from the top page, but Chrome's
accessibility tree (and therefore Playwright, which drives the browser via
CDP rather than in-page JS) sees it fine. On the real page, day cells expose
an accessible name of `"Seats not available"` for scheduled-but-sold-out
days, and no accessible name at all for not-yet-scheduled days or calendar
padding cells; both cases are treated as `"unavailable"` here. No day with
real availability existed anywhere in the check quarter at research time, so
the exact wording of an "available" label could not be observed directly —
the implementation below matches on the presence of the word `"available"`
without `"not available"`, which is guaranteed to cover the current negative
label and is the most conservative reasonable guess for a positive one.
**Flag this to the user for extra scrutiny the first time a real available
date is expected**, since it's the one piece of this plan validated by
inference rather than direct observation.

- [ ] **Step 1: Implement `scraper.py`**

```python
import calendar
from datetime import date

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

EVENT_URL = "https://cenacolovinciano.vivaticket.it/en/event/cenacolo-vinciano/151991?idt=2547"


def _dismiss_cookies(page) -> None:
    try:
        page.get_by_role("button", name="I agree").click(timeout=5000)
    except PlaywrightTimeoutError:
        pass


def _find_calendar_frame(page):
    for frame in page.frames:
        if frame.get_by_role("heading", name="CALENDAR").count() > 0:
            return frame
    raise RuntimeError("Could not find the calendar frame on the ticket page")


def _goto_month(frame, year: int, month: int) -> None:
    target_label = f"{calendar.month_name[month].upper()} {year}"
    for _ in range(24):
        if frame.get_by_text(target_label, exact=True).count() > 0:
            return
        frame.get_by_role("link", name="›").click()  # "›" next month
        frame.wait_for_timeout(700)
    raise RuntimeError(f"Could not navigate calendar to {target_label}")


def _day_grid(frame):
    lists = frame.get_by_role("list").all()
    candidates = [lst for lst in lists if 28 <= lst.get_by_role("listitem").count() <= 42]
    if not candidates:
        raise RuntimeError("Could not find the day-of-month grid in the calendar")
    return candidates[0]


def _day_status(frame, year: int, month: int, day: int) -> str:
    first_weekday, _ = calendar.monthrange(year, month)  # Monday=0 .. Sunday=6
    grid = _day_grid(frame)
    cell = grid.get_by_role("listitem").nth(first_weekday + day - 1)
    label = (cell.get_attribute("aria-label") or cell.get_attribute("title") or "").strip().lower()
    if not label:
        return "unavailable"
    if "not available" in label:
        return "unavailable"
    if "available" in label:
        return "available"
    return "unavailable"


def check_dates(target_dates: list) -> dict:
    statuses = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        try:
            page.goto(EVENT_URL, wait_until="networkidle", timeout=30000)
            _dismiss_cookies(page)
            frame = _find_calendar_frame(page)
            months_checked = set()
            for d in target_dates:
                key = (d.year, d.month)
                if key not in months_checked:
                    _goto_month(frame, d.year, d.month)
                    months_checked.add(key)
                statuses[d.isoformat()] = _day_status(frame, d.year, d.month, d.day)
        finally:
            browser.close()
    return statuses
```

- [ ] **Step 2: Install the Playwright browser binary locally**

Run:
```bash
source .venv/bin/activate
playwright install chromium
```
Expected: Chromium downloads successfully.

- [ ] **Step 3: Live-verify against the real site**

This module talks to a real third-party site, so it's verified by running it
live rather than by a mocked unit test.

Run:
```bash
source .venv/bin/activate
python -c "
from datetime import date
from scraper import check_dates
print(check_dates([date(2026, 9, 2), date(2026, 9, 9)]))
"
```
Expected: prints a dict like
`{'2026-09-02': 'unavailable', '2026-09-09': 'unavailable'}` (matching the
live site state observed during design research — both dates sold out /
not yet released as of 2026-07-18). If it raises instead, read the exception
message; it names which step (frame lookup, month navigation, or grid
lookup) failed, which tells you what on the live site changed.

- [ ] **Step 4: Commit**

```bash
git add scraper.py
git commit -m "Add Playwright-based calendar scraper"
```

---

### Task 5: Orchestrator script

**Files:**
- Create: `check_tickets.py`
- Create: `tests/test_check_tickets.py`
- Create: `state.json` (initial committed state)

**Interfaces:**
- Consumes: `load_state`/`save_state` from `state.py` (Task 1), `decide` from
  `decision.py` (Task 2), `send_telegram_message` from `notify.py` (Task 3),
  `check_dates` from `scraper.py` (Task 4).
- Produces: `main() -> int`, the CLI entry point run by the GitHub Actions
  workflow (Task 6).

- [ ] **Step 1: Create the initial committed state file**

`state.json`:
```json
{
  "2026-09-02": {
    "consecutive_failures": 0,
    "notified": false,
    "warned": false
  },
  "2026-09-09": {
    "consecutive_failures": 0,
    "notified": false,
    "warned": false
  }
}
```

- [ ] **Step 2: Write the failing test**

`tests/test_check_tickets.py`:
```python
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
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `pytest tests/test_check_tickets.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'check_tickets'`.

- [ ] **Step 4: Implement `check_tickets.py`**

```python
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
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/test_check_tickets.py -v`
Expected: 2 passed.

- [ ] **Step 6: Run the full test suite**

Run: `pytest -v`
Expected: all tests across `test_state.py`, `test_decision.py`,
`test_notify.py`, `test_check_tickets.py` pass (13 tests total).

- [ ] **Step 7: Commit**

```bash
git add check_tickets.py tests/test_check_tickets.py state.json
git commit -m "Add orchestrator script wiring scraper, decision logic, and notifier"
```

---

### Task 6: GitHub Actions workflow + setup README

**Files:**
- Create: `.github/workflows/check.yml`
- Create: `README.md`

**Interfaces:**
- Consumes: `check_tickets.py` (Task 5) as the command the workflow runs.
- Produces: nothing consumed by other tasks — this is the deployment surface.

- [ ] **Step 1: Write the workflow**

`.github/workflows/check.yml`:
```yaml
name: Check Cenacolo Vinciano tickets

on:
  schedule:
    - cron: '*/15 * * * *'
  workflow_dispatch: {}

permissions:
  contents: write

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          playwright install --with-deps chromium

      - name: Run ticket check
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
        run: python check_tickets.py

      - name: Commit updated state
        run: |
          git config user.name "ticket-watcher-bot"
          git config user.email "actions@users.noreply.github.com"
          git add state.json
          git diff --staged --quiet || git commit -m "Update ticket watcher state"
          git diff --staged --quiet || git push
```

- [ ] **Step 2: Write the setup README**

`README.md`:
```markdown
# Cenacolo Vinciano Ticket Watcher

Checks the official Last Supper (Cenacolo Vinciano, Milan) ticket calendar
every 15 minutes for availability on 2026-09-02 and 2026-09-09, and sends a
Telegram message the moment either date opens up.

## One-time setup

1. **Create a GitHub repo** and push this code to it (public repo, so
   Actions minutes are free and unlimited for this use case).

2. **Create a Telegram bot**: message [@BotFather](https://t.me/BotFather)
   on Telegram, send `/newbot`, follow the prompts. It gives you a bot
   token — save it.

3. **Get your chat ID**: send any message to your new bot, then open
   `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser and
   read the `chat.id` field from the JSON response. (Or message
   [@userinfobot](https://t.me/userinfobot) to get your own numeric user ID,
   which works as the chat ID for a DM.)

4. **Add repo secrets**: in your GitHub repo, go to Settings → Secrets and
   variables → Actions → New repository secret, and add:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`

5. **Allow the workflow to push commits**: Settings → Actions → General →
   Workflow permissions → select "Read and write permissions". (The
   `permissions: contents: write` block in the workflow file requests this,
   but some repos/orgs also need the setting enabled here.)

6. **Verify Telegram wiring** (optional but recommended), locally:
   ```bash
   export TELEGRAM_BOT_TOKEN=...
   export TELEGRAM_CHAT_ID=...
   python send_test_message.py
   ```
   You should get a Telegram message immediately.

7. **Trigger the workflow manually once**: GitHub repo → Actions tab →
   "Check Cenacolo Vinciano tickets" → Run workflow. Confirm it finishes
   green. It won't send a Telegram message on this run unless a date is
   genuinely available yet — that's expected.

From here it runs itself every 15 minutes. You'll get a Telegram DM the
first time either date shows real availability, and never again for that
date afterward.

## Local development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
playwright install chromium
pytest -v
```
```

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/check.yml README.md
git commit -m "Add GitHub Actions schedule and setup README"
```

---

### Task 7: End-to-end verification

**Files:** none (verification only).

- [ ] **Step 1: Run the full local test suite one more time**

Run: `pytest -v`
Expected: all tests pass.

- [ ] **Step 2: Push to GitHub and confirm the workflow runs**

After the user has created the GitHub repo and pushed this code (Task 6,
step 1) and completed the README setup steps:

Run (from the repo, after `git remote add origin <url>`):
```bash
git push -u origin main
```
Then in the GitHub UI: Actions tab → "Check Cenacolo Vinciano tickets" →
Run workflow (manual trigger). Confirm the run turns green and, in its log,
prints the current status for both target dates (e.g. `unavailable`).

- [ ] **Step 3: Confirm state persistence works across runs**

Trigger the workflow a second time via `workflow_dispatch`. Confirm in the
Actions log / git history that `state.json` either stayed identical (no
diff, no new commit) if nothing changed, or was committed with an updated
`consecutive_failures`/`notified` value if something did. This proves state
survives between runs rather than resetting every time.

- [ ] **Step 4: Hand off to the live schedule**

No further action needed — the cron trigger takes over from here. Tell the
user: watch for a Telegram message; when a date is available it arrives
within 15 minutes of the calendar updating, and that date then stops being
checked. If either date's window closes without ever finding tickets, the
user can just leave the workflow running (it will safely find nothing) or
disable it via the Actions tab.

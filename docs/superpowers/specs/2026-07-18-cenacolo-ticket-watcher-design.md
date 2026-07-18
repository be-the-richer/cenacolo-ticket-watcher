# Cenacolo Vinciano Ticket Watcher — Design

## Purpose

Watch the official Cenacolo Vinciano ("The Last Supper", Milan) ticketing site
for the appearance of available tickets on **2026-09-02** or **2026-09-09**,
and send an instant Telegram notification the moment either date opens up.

## Background / research findings

- Official ticket sales happen on `https://cenacolovinciano.vivaticket.it`,
  reached via the museum's site (`cenacolovinciano.org` → `lastsupper.shop` →
  Vivaticket). The admission-ticket event page for the Sept–Dec 2026 quarter is:
  `https://cenacolovinciano.vivaticket.it/en/event/cenacolo-vinciano/151991?idt=2547`
- The booking calendar on that page is rendered **inside an iframe** belonging
  to a third-party booking widget with session-token query parameters
  (`qubsq`, `qubsts`, etc.). This is a real, JS-rendered, session-aware
  widget — plain `requests` + HTML parsing will not reliably see it. A
  headless browser is required.
- The calendar shows one visible month at a time with a "next month" (`›`)
  control and color-coded day cells:
  - grey / no box = **not scheduled**
  - white box, black text = **scheduled, no availability** (sold out)
  - green box = **scheduled, with availability** ← the state we're watching for
- The site itself states: *"each Wednesday at 12 noon [[CET/CEST]] extra
  tickets go on sale for the following week"*. As of 2026-07-18, both Sept 2
  and Sept 9 (both Wednesdays) show as unavailable.
- As of today, tickets for the Sept 1 – Dec 31 2026 quarter are already on
  general sale (opened June 23, 2026), so the event/page IDs above should
  remain stable through the end of that quarter — no need to re-discover them
  each run.

## Approach

**GitHub Actions (scheduled) + Playwright (Python, headless Chromium) +
Telegram Bot notification.** Chosen over running locally on the user's Mac
because it needs to run unattended 24/7 for ~7 weeks regardless of whether
the laptop is on, and over a lightweight HTTP scraper because the calendar
requires real browser rendering (iframe + session tokens).

## Architecture

```
GitHub Actions (cron: */15 * * * *, plus workflow_dispatch)
  └─ checkout repo
  └─ run check_tickets.py
       ├─ Playwright launches headless Chromium
       ├─ navigate to the admission-tickets event page
       ├─ dismiss cookie consent banner if present
       ├─ inside the booking iframe: click "next month" until the calendar
       │  shows September 2026
       ├─ read the CSS class of the day-9-Sep and day-2-Sep cells
       ├─ for each target date not yet marked "notified" in state.json:
       │     if cell class indicates availability (green) →
       │         send Telegram message via Bot API
       │         mark date as notified in state.json
       └─ commit state.json back to the repo if it changed
```

### Components

- `check_tickets.py` — single script, does one check-and-notify pass, then
  exits. No long-running process; the schedule is GitHub's, not the script's.
- `state.json` — `{"2026-09-02": {"notified": false}, "2026-09-09": {"notified": false}}`.
  Committed back to the repo by the workflow after each run so state survives
  across runs (Actions runners are stateless VMs).
- `.github/workflows/check.yml` — cron trigger (`*/15 * * * *`, GitHub's
  minimum granularity is 5 min; actual fire time can slip under load —
  acceptable per user) + manual `workflow_dispatch` trigger for testing.
- GitHub Secrets: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.

### Detection logic

For each of the two target dates:
1. If already `notified: true` in `state.json`, skip it entirely (no further
   checks, no re-notification — per user's choice).
2. Otherwise, read the day cell's status in the rendered calendar.
   - Available (green) → send Telegram alert, set `notified: true`.
   - Not scheduled / sold out (grey or white) → do nothing this run.
3. Once both dates are `notified: true`, the script has nothing left to do
   and effectively becomes a no-op each run (still fine to leave the
   schedule running, or the user can disable/delete the workflow).

### Notification

Single Telegram message per date via `https://api.telegram.org/bot<token>/sendMessage`,
e.g.:
> 🎟️ Появились билеты в Тайную вечерю на 9 сентября 2026! Бронируй скорее:
> https://cenacolovinciano.vivaticket.it/en/event/cenacolo-vinciano/151991?idt=2547

### Error handling

- If the page structure doesn't match expectations (iframe not found, month
  navigation fails, cell not found) — log the error clearly in the Actions
  run log and **do not** treat it as "no availability" silently forever. To
  avoid spamming Telegram on transient failures, only send a Telegram
  warning if the same failure happens on **3 consecutive runs** (~45 min),
  tracked via a small failure counter in `state.json`.
- Network/timeout errors from Playwright: retry once within the same run
  before giving up for that run.

### Testing / validation

- Manually trigger the workflow once via `workflow_dispatch` after setup and
  confirm: (a) it runs green in Actions, (b) `state.json` is unchanged if no
  tickets are available (dates stay unavailable in current testing), (c) a
  temporary intentional miss-selector test proves the failure-alert path
  works.
- Because we cannot force the real site to show "available" on demand, final
  end-to-end proof of the happy path (green cell → Telegram message) will
  happen naturally the first time a real slot opens — the user should watch
  for the first Telegram message and confirm it arrived and the link works.

## Out of scope

- No email notification path (Telegram was chosen as the sole channel).
- No support for other ticket types (guided tours, workshops) — admission
  tickets only, per the user's stated interest.
- No UI/dashboard — Actions run logs are the only visibility into history.

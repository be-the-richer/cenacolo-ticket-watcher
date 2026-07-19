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


def _classify_label(label: str) -> str:
    label = label.strip().lower()
    if not label:
        return "unavailable"
    if "not available" in label:
        return "unavailable"
    if "available" in label:
        return "available"
    raise RuntimeError(f"Unrecognized calendar cell label: {label!r}")


def _day_status(frame, year: int, month: int, day: int) -> str:
    first_weekday, _ = calendar.monthrange(year, month)  # Monday=0 .. Sunday=6
    grid = _day_grid(frame)
    cell = grid.get_by_role("listitem").nth(first_weekday + day - 1)
    label = cell.get_attribute("aria-label") or cell.get_attribute("title") or ""
    return _classify_label(label)


def _check_dates_once(target_dates: list) -> dict:
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


def check_dates(target_dates: list) -> dict:
    try:
        return _check_dates_once(target_dates)
    except Exception:
        return _check_dates_once(target_dates)

"""Time / trading-calendar helpers (IST)."""

from __future__ import annotations

import datetime as dt

# Minimal NSE holiday list for 2026 (extend or fetch later). Weekends handled
# separately. Used by the scheduler and to resolve the "latest trading day".
NSE_HOLIDAYS_2026 = {
    dt.date(2026, 1, 26),   # Republic Day
    dt.date(2026, 3, 6),    # Holi
    dt.date(2026, 3, 21),   # Eid (indicative)
    dt.date(2026, 4, 3),    # Good Friday
    dt.date(2026, 4, 14),   # Ambedkar Jayanti
    dt.date(2026, 5, 1),    # Maharashtra Day
    dt.date(2026, 8, 15),   # Independence Day
    dt.date(2026, 10, 2),   # Gandhi Jayanti
    dt.date(2026, 11, 9),   # Diwali (indicative)
    dt.date(2026, 12, 25),  # Christmas
}


def is_trading_day(day: dt.date) -> bool:
    """True if the date is a weekday and not an NSE holiday."""
    return day.weekday() < 5 and day not in NSE_HOLIDAYS_2026


def latest_trading_day(reference: dt.date | None = None) -> dt.date:
    """Return the most recent trading day on or before the reference date."""
    day = reference or dt.date.today()
    while not is_trading_day(day):
        day -= dt.timedelta(days=1)
    return day

"""
Rule-based corporate-action event classifier.

Maps free-text announcement text to (event_type, impact_tag, priority) using the
transparent keyword rules in config. First-match wins. No scoring, no ML.
Returns event_type=None when nothing matches (caller drops it from the watchlist).
"""

from __future__ import annotations

from core.config import EVENT_IMPACT, EVENT_PRIORITY, EVENT_TYPE_RULES


def classify_event(text: str) -> tuple[str | None, str | None, str | None]:
    """Return (event_type, impact_tag, priority) for an announcement text."""
    if not text:
        return None, None, None
    t = text.lower()
    for event_type, keywords in EVENT_TYPE_RULES:
        if any(kw in t for kw in keywords):
            return (event_type,
                    EVENT_IMPACT.get(event_type, "Neutral"),
                    EVENT_PRIORITY.get(event_type, "Low"))
    return None, None, None

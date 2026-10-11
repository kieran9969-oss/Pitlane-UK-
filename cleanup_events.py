
#!/usr/bin/env python3
"""Remove expired manual events from PITLANE UK."""

import json
from datetime import datetime, date
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
EVENTS_FILE = ROOT / "data/manual-events.json"


def parse_date(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def main():
    today = datetime.now(
        ZoneInfo("Europe/London")
    ).date()

    print("PITLANE UK - EVENT CLEANUP")
    print(f"Today's UK date: {today}")

    events = json.loads(
        EVENTS_FILE.read_text(encoding="utf-8")
    )

    if not isinstance(events, list):
        raise ValueError(
            "manual-events.json must contain a list."
        )

    kept = []
    removed = 0

    for event in events:
        start = parse_date(event.get("date"))
        end = parse_date(event.get("end_date"))

        # Use the last day for multi-day events.
        # Missing or invalid dates are kept for review.
        last_day = end or start

        if last_day is None:
            print(
                "REVIEW INVALID DATE: "
                + str(event.get("name", "Unknown"))
            )
            kept.append(event)
            continue

        if last_day < today:
            print(
                "REMOVED PAST EVENT: "
                + str(event.get("name", "Unknown"))
                + f" ({last_day})"
            )
            removed += 1
            continue

        kept.append(event)

    if removed:
        EVENTS_FILE.write_text(
            json.dumps(
                kept,
                indent=2,
                ensure_ascii=False,
            ) + "\n",
            encoding="utf-8",
        )

    print("\n--- CLEANUP SUMMARY ---")
    print(f"Past events removed: {removed}")
    print(f"Events kept: {len(kept)}")
    print("Cleanup complete.")


if __name__ == "__main__":
    main()

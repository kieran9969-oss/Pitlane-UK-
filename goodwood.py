
#!/usr/bin/env python3
"""Update confirmed Goodwood 2027 event dates."""

import json
import re
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FILE = ROOT / "data" / "manual-events.json"

PAGES = {
    "Festival of Speed": (
        "https://www.goodwood.com/motorsport/festival-of-speed/",
        "Festival of Speed 2027"
    ),
    "Goodwood Revival": (
        "https://www.goodwood.com/motorsport/goodwood-revival/",
        "Goodwood Revival 2027"
    ),
    "Members' Meeting": (
        "https://www.goodwood.com/motorsport/members-meeting/",
        "Members' Meeting 2027"
    ),
}

events = json.loads(FILE.read_text(encoding="utf-8"))
changes = 0

for name, (url, event_name) in PAGES.items():
    print(f"\nChecking {name}...")

    try:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 PITLANE-UK/1.0"}
        )

        with urllib.request.urlopen(request, timeout=20) as response:
            html = response.read(2_000_000).decode(
                "utf-8", errors="replace"
            )

        dates = sorted(set(re.findall(
            r"2027-\d{2}-\d{2}", html
        )))

        if len(dates) != 2:
            print("Unclear dates. Skipping update.")
            continue

        start = date.fromisoformat(dates[0])
        end = date.fromisoformat(dates[1])

        if not (0 <= (end - start).days <= 7):
            print("Unexpected event duration. Skipping.")
            continue

        matches = [
            event for event in events
            if event.get("organiser") == "Goodwood"
            and event_name.lower() in event.get("name", "").lower()
        ]

        if len(matches) != 1:
            print("Could not identify one event. Skipping.")
            continue

        event = matches[0]

        if (
            event["date"] == dates[0]
            and event.get("end_date") == dates[1]
        ):
            print("Dates match. No update needed.")
            continue

        # Do not automatically accept unexpected date changes.
        print(f"Possible date change: {event['name']}")
        print(f"Current: {event['date']} to {event.get('end_date')}")
        print(f"Website: {dates[0]} to {dates[1]}")
        print("Manual confirmation required. No changes saved.")

    except Exception as error:
        print(f"Check failed: {error}")

print("\nGoodwood check complete.")




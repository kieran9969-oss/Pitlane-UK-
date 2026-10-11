
#!/usr/bin/env python3
"""Check Goodwood event dates and report possible changes."""

import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PAGES = {
    "Festival of Speed": "https://www.goodwood.com/motorsport/festival-of-speed/",
    "Goodwood Revival": "https://www.goodwood.com/motorsport/goodwood-revival/",
    "Members' Meeting": "https://www.goodwood.com/motorsport/members-meeting/",
}

manual_file = ROOT / "data" / "manual-events.json"
events = json.loads(manual_file.read_text())

for name, url in PAGES.items():
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
            print("Dates unclear. No changes made.")
            continue

        matches = [
            event for event in events
            if event.get("organiser") == "Goodwood"
            and "2027" in event.get("name", "")
            and name.lower().replace("goodwood ", "")
            in event.get("name", "").lower()
        ]

        if len(matches) != 1:
            print("Could not identify one matching event.")
            continue

        event = matches[0]

        if event["date"] == dates[0] and event.get("end_date") == dates[1]:
            print("Dates match. No update needed.")
        else:
            print(f"Possible date change for {event['name']}")
            print(f"Current: {event['date']} to {event.get('end_date')}")
            print(f"Website: {dates[0]} to {dates[1]}")
            print("Review required. No automatic changes made.")

    except Exception as error:
        print(f"Check failed: {error}")

print("\nGoodwood date checks complete.")



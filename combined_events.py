
#!/usr/bin/env python3
"""Import four confirmed 2027 events into PITLANE UK."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EVENTS_FILE = ROOT / "data/manual-events.json"

EVENTS = [
    {
        "name": "The Reunion Show 2027",
        "date": "2027-07-11",
        "end_date": "2027-07-11",
        "venue": "Staffordshire Showground",
        "region": "West Midlands",
        "category": "Modified Car Show",
        "organiser": "The Reunion Show",
        "official_url": "https://www.thereunionshow.co.uk/",
        "status": "confirmed",
    },
    {
        "name": "Ultimate Street Car 2027",
        "date": "2027-07-30",
        "end_date": "2027-08-01",
        "venue": "Santa Pod Raceway",
        "region": "East of England",
        "category": "Modified Car Show",
        "organiser": "Ultimate Street Car",
        "official_url": "https://ultimatestreetcar.co.uk/",
        "status": "confirmed",
    },
    {
        "name": "Rollhard Bicester 2027",
        "date": "2027-08-01",
        "end_date": "2027-08-01",
        "venue": "Bicester Heritage",
        "region": "South East",
        "category": "Modified Car Show",
        "organiser": "Rollhard",
        "official_url": "https://www.rollhard.co.uk/pages/bicester",
        "status": "confirmed",
    },
    {
        "name": "Isle of Wight Takeover 2027",
        "date": "2027-05-15",
        "end_date": "2027-05-16",
        "venue": "Royal Isle of Wight County Showground",
        "region": "South East",
        "category": "Modified Car Show",
        "organiser": "Isle of Wight Takeover",
        "official_url": "https://www.iowtakeover.co.uk/",
        "status": "confirmed",
    },
]


def main():
    events = json.loads(
        EVENTS_FILE.read_text(encoding="utf-8")
    )

    if not isinstance(events, list):
        raise ValueError(
            "manual-events.json must contain a list."
        )

    added = 0
    existing = 0
    review = 0

    for new_event in EVENTS:
        matches = [
            event for event in events
            if event.get("name", "").strip().casefold()
            == new_event["name"].casefold()
        ]

        if matches:
            event = matches[0]

            if (
                event.get("date") != new_event["date"]
                or event.get("end_date", event.get("date"))
                != new_event["end_date"]
                or event.get("venue") != new_event["venue"]
            ):
                print(
                    "REVIEW EXISTING EVENT: "
                    + new_event["name"]
                )
                review += 1
            else:
                print(
                    "ALREADY LISTED: "
                    + new_event["name"]
                )
                existing += 1

            continue

        events.append(new_event)
        added += 1
        print("ADDED: " + new_event["name"])

    if added:
        EVENTS_FILE.write_text(
            json.dumps(
                events,
                indent=2,
                ensure_ascii=False,
            ) + "\n",
            encoding="utf-8",
        )

    print("\n--- COMBINED IMPORT SUMMARY ---")
    print(f"Events added: {added}")
    print(f"Already listed: {existing}")
    print(f"Events needing review: {review}")
    print(f"Total manual events: {len(events)}")


if __name__ == "__main__":
    main()

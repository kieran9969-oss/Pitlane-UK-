
#!/usr/bin/env python3
"""Discover and safely update Goodwood motorsport events."""

import json
import re
import urllib.request
from datetime import date
from html import unescape
from pathlib import Path

FILE = Path(__file__).resolve().parent / "data/manual-events.json"

SOURCES = [
    {
        "name": "Festival of Speed",
        "url": "https://www.goodwood.com/motorsport/festival-of-speed/",
        "venue": "Goodwood House",
        "category": "Motorsport",
        "duration": 4,
        "months": [6, 7],
    },
    {
        "name": "Goodwood Revival",
        "url": "https://www.goodwood.com/motorsport/goodwood-revival/",
        "venue": "Goodwood Motor Circuit",
        "category": "Classic cars",
        "duration": 3,
        "months": [8, 9],
    },
    {
        "name": "Members' Meeting",
        "url": "https://www.goodwood.com/motorsport/members-meeting/",
        "venue": "Goodwood Motor Circuit",
        "category": "Motorsport",
        "duration": 2,
        "months": [3, 4],
    },
]

MONTHS = {
    month.lower(): number
    for number, month in enumerate(
        [
            "January", "February", "March", "April",
            "May", "June", "July", "August",
            "September", "October", "November", "December",
        ],
        1,
    )
}

PATTERN = re.compile(
    r"\b(\d{1,2})\s*[-–]\s*(\d{1,2})\s+"
    r"(January|February|March|April|May|June|July|"
    r"August|September|October|November|December)"
    r"\s+(20\d{2})\b",
    re.IGNORECASE,
)


def find_dates(source):
    request = urllib.request.Request(
        source["url"],
        headers={"User-Agent": "Mozilla/5.0 PITLANE-UK/1.0"},
    )

    with urllib.request.urlopen(request, timeout=25) as response:
        html = response.read(2_000_000).decode(
            "utf-8", errors="replace"
        )

    # Remove script and style content before reading visible text.
    html = re.sub(
        r"<(script|style)\b[^>]*>.*?</\1>",
        " ", html, flags=re.I | re.S,
    )

    text = unescape(re.sub(r"<[^>]+>", " ", html))
    text = re.sub(r"\s+", " ", text)

    found = {}

    for match in PATTERN.finditer(text):
        first, last, month, year = match.groups()

        # Only accept dates close to the event name.
        nearby = text[
            max(0, match.start() - 150):match.end() + 150
        ]

        if source["name"].lower() not in nearby.lower():
            print("Date not near event name. Skipping.")
            continue

        year = int(year)

        if year < 2027:
            continue

        if MONTHS[month.lower()] not in source["months"]:
            continue

        try:
            start = date(
                year,
                MONTHS[month.lower()],
                int(first),
            )
            end = date(
                year,
                MONTHS[month.lower()],
                int(last),
            )
        except ValueError:
            continue

        if (end - start).days + 1 != source["duration"]:
            continue

        found.setdefault(year, set()).add(
            (start.isoformat(), end.isoformat())
        )

    return found


def main():
    events = json.loads(FILE.read_text(encoding="utf-8"))
    changed = False

    for source in SOURCES:
        print(f"\nChecking {source['name']}")

        try:
            results = find_dates(source)
        except Exception as error:
            print(f"Page check failed: {error}")
            continue

        for year, candidates in sorted(results.items()):
            if len(candidates) != 1:
                print(f"{year}: Conflicting dates. Skipping.")
                continue

            start, end = next(iter(candidates))

            # Identify an event by organiser, type and year.
            matches = [
                event
                for event in events
                if event.get("organiser") == "Goodwood"
                and event.get("date", "").startswith(str(year))
                and source["name"].lower()
                in event.get("name", "").lower()
            ]

            if len(matches) > 1:
                print(f"{year}: Duplicate listings. Skipping.")
                continue

            if len(matches) == 1:
                event = matches[0]

                if (
                    event["date"] == start
                    and event.get("end_date") == end
                ):
                    print(f"{year}: Dates match.")
                    continue

                print(
                    f"{year}: Possible date change for "
                    f"{event['name']}: {start} to {end}"
                )
                print("Existing event kept for manual review.")
                continue

            # Add a newly discovered future event.
            new_event = {
                "name": f"Goodwood {source['name']} {year}",
                "date": start,
                "end_date": end,
                "venue": source["venue"],
                "region": "West Sussex",
                "category": source["category"],
                "organiser": "Goodwood",
                "official_url": source["url"],
                "status": "Unverified",
            }

            events.append(new_event)
            changed = True

            print(f"{year}: Added {new_event['name']}")

    # Save changes after checking all three Goodwood events.
    if changed:
        FILE.write_text(
            json.dumps(
                events,
                indent=2,
                ensure_ascii=False,
            ) + "\n",
            encoding="utf-8",
        )
        print("Goodwood event data updated.")
    else:
        print("No Goodwood event changes needed.")

    print("\nGoodwood discovery and comparison complete.")


if __name__ == "__main__":
    main()

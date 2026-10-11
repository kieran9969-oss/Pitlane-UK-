
#!/usr/bin/env python3
"""Import official Tunerfest events into PITLANE UK."""

import json
import re
import urllib.request
from datetime import date
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

BASE = Path(__file__).resolve().parent
EVENTS_FILE = BASE / "data/manual-events.json"

SOURCES = [
    {
        "name": "Tunerfest South",
        "venue": "Brands Hatch",
        "url": "https://south.tunerfest.co.uk/",
    },
    {
        "name": "Tunerfest North",
        "venue": "Oulton Park",
        "url": "https://north.tunerfest.co.uk/",
    },
]

MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

DATE_PATTERN = re.compile(
    r"\b(\d{1,2})(?:st|nd|rd|th)?\s+"
    r"(" + "|".join(MONTHS) + r")\s+"
    r"(20\d{2})\b",
    re.IGNORECASE,
)


class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def download(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 PITLANE-UK/1.0"
        },
    )

    with urllib.request.urlopen(
        request, timeout=30
    ) as response:
        return response.read(2_000_000).decode(
            "utf-8", errors="replace"
        )


def normalise(value):
    value = unescape(str(value or "")).lower()
    return " ".join(
        re.sub(r"[^a-z0-9]+", " ", value).split()
    )


def extract_dates(html):
    parser = TextParser()
    parser.feed(html)

    text = unescape(" ".join(parser.parts))
    text = " ".join(text.split())

    dates = set()

    for match in DATE_PATTERN.finditer(text):
        day = int(match.group(1))
        month = MONTHS[match.group(2).lower()]
        year = int(match.group(3))

        try:
            event_date = date(year, month, day)
        except ValueError:
            continue

        if event_date >= date.today():
            dates.add(event_date)

    return sorted(dates)


def discover_events():
    discovered = []

    for source in SOURCES:
        print(f"\nChecking: {source['name']}")
        print(f"URL: {source['url']}")

        try:
            html = download(source["url"])
            dates = extract_dates(html)
        except Exception as error:
            print(f"Website check failed: {error}")
            continue

        if not dates:
            print("No upcoming dates detected.")
            continue

        # Do not guess if a page contains multiple dates.
        if len(dates) != 1:
            print(
                "REVIEW NEEDED: "
                f"{len(dates)} dates found."
            )
            continue

        event_date = dates[0]

        event = {
            "name": source["name"],
            "date": event_date.isoformat(),
            "end_date": event_date.isoformat(),
            "venue": source["venue"],
            "region": "",
            "category": "Car show",
            "organiser": "Tunerfest",
            "official_url": source["url"],
            "status": "Unverified",
        }

        discovered.append(event)

        print(
            f"DETECTED: {event['name']} "
            f"({event['date']})"
        )

    return discovered


def find_existing(event, existing):
    new_name = normalise(event["name"])

    for old in existing:
        old_name = normalise(old.get("name", ""))

        if old_name != new_name:
            continue

        old_date = str(old.get("date", ""))

        if old_date == event["date"]:
            return old, "duplicate"

        # The same annual event in a different year
        # is a separate event.
        if old_date[:4] == event["date"][:4]:
            return old, "date change"

    return None, ""


def main():
    print("PITLANE UK - TUNERFEST IMPORT")

    existing = json.loads(
        EVENTS_FILE.read_text(encoding="utf-8")
    )

    if not isinstance(existing, list):
        raise ValueError(
            "manual-events.json must contain a list."
        )

    discovered = discover_events()

    added = 0
    skipped = 0
    changes = 0

    for event in discovered:
        old, reason = find_existing(
            event, existing
        )

        if reason == "duplicate":
            print(
                f"Already listed: {event['name']}"
            )
            skipped += 1
            continue

        if reason == "date change":
            print(
                "DATE CHANGE - REVIEW: "
                + event["name"]
            )
            print(
                "  Listed: "
                + str(old.get("date"))
            )
            print(
                "  Website: "
                + event["date"]
            )
            changes += 1
            skipped += 1
            continue

        existing.append(event)
        added += 1

        print(
            f"ADDED: {event['name']} "
            f"({event['date']})"
        )

    if added:
        EVENTS_FILE.write_text(
            json.dumps(
                existing,
                indent=2,
                ensure_ascii=False,
            ) + "\n",
            encoding="utf-8",
        )

    print("\n--- IMPORT SUMMARY ---")
    print(f"Events detected: {len(discovered)}")
    print(f"New events added: {added}")
    print(f"Already listed or skipped: {skipped}")
    print(f"Date changes needing review: {changes}")
    print("Tunerfest import complete.")


if __name__ == "__main__":
    main()

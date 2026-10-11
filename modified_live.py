
#!/usr/bin/env python3
"""Import official Modified Live events into PITLANE UK."""

import json
import re
import urllib.request
from datetime import date
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

BASE = Path(__file__).resolve().parent
EVENTS_FILE = BASE / "data/manual-events.json"

SOURCE_URL = "https://modifiedlive.co.uk/"

EVENTS = [
    {
        "name": "Modified Live Castle Combe",
        "venue": "Castle Combe Circuit",
        "pattern": r"Modified Live Castle Combe",
    },
    {
        "name": "Modified Live Cadwell Park",
        "venue": "Cadwell Park",
        "pattern": r"Modified Live Cadwell Park",
    },
    {
        "name": "Modified Live Snetterton",
        "venue": "Snetterton Circuit",
        "pattern": r"Modified Live Snetterton(?: Circuit)?",
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

DATE_PATTERN = (
    r"(\d{1,2})(?:st|nd|rd|th)?\s+"
    r"(" + "|".join(MONTHS) + r")\s+"
    r"(20\d{2})"
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


def download():
    request = urllib.request.Request(
        SOURCE_URL,
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
    value = unescape(str(value)).lower()
    return " ".join(
        re.sub(r"[^a-z0-9]+", " ", value).split()
    )


def clean_url(value):
    parsed = urlparse(str(value or ""))
    return (
        parsed.netloc.lower().removeprefix("www.")
        + parsed.path.rstrip("/")
    )


def extract_events(html):
    parser = TextParser()
    parser.feed(html)

    text = unescape(" ".join(parser.parts))
    text = " ".join(text.split())

    results = []

    for source in EVENTS:
        pattern = (
            r"\b"
            + source["pattern"]
            + r"\b"
            + r"(?:(?!Modified Live).){0,120}?"
            + DATE_PATTERN
        )

        matches = list(
            re.finditer(
                pattern,
                text,
                flags=re.IGNORECASE,
            )
        )

        if not matches:
            print(
                "NOT FOUND: " + source["name"]
            )
            continue

        for match in matches:
            day = int(match.group(1))
            month = MONTHS[match.group(2).lower()]
            year = int(match.group(3))

            try:
                event_date = date(year, month, day)
            except ValueError:
                continue

            if event_date < date.today():
                continue

            results.append({
                "name": source["name"],
                "date": event_date.isoformat(),
                "end_date": event_date.isoformat(),
                "venue": source["venue"],
                "region": "",
                "category": "Car show",
                "organiser": "Modified Live",
                "official_url": SOURCE_URL,
                "status": "Unverified",
            })

    return results


def is_duplicate(event, existing):
    new_name = normalise(event["name"])

    for old in existing:
        if old.get("date") != event["date"]:
            continue

        if normalise(old.get("name", "")) == new_name:
            return True

        if (
            normalise(old.get("venue", ""))
            == normalise(event["venue"])
            and "modified live"
            in normalise(old.get("name", ""))
        ):
            return True

    return False


def check_date_change(event, existing):
    for old in existing:
        if (
            normalise(old.get("name", ""))
            == normalise(event["name"])
            and old.get("organiser") == "Modified Live"
            and str(old.get("date", ""))[:4]
            == event["date"][:4]
        ):
            if old.get("date") != event["date"]:
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
            return True

    return False


def main():
    print("PITLANE UK - MODIFIED LIVE IMPORT")
    print(f"Checking: {SOURCE_URL}")

    try:
        html = download()
        discovered = extract_events(html)
    except Exception as error:
        print(f"Website check failed: {error}")
        print("Existing calendar left unchanged.")
        return

    print(
        f"Upcoming events detected: {len(discovered)}"
    )

    if not discovered:
        print("No events found. Nothing changed.")
        return

    existing = json.loads(
        EVENTS_FILE.read_text(encoding="utf-8")
    )

    if not isinstance(existing, list):
        raise ValueError(
            "manual-events.json must contain a list."
        )

    added = 0
    skipped = 0

    for event in discovered:
        if is_duplicate(event, existing):
            print(
                f"Already listed: {event['name']}"
            )
            skipped += 1
            continue

        if check_date_change(event, existing):
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
    print("Modified Live import complete.")


if __name__ == "__main__":
    main()

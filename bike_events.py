
#!/usr/bin/env python3
"""PITLANE UK - cautious motorcycle event importer.

Reads structured event information published by organisers.
Only imports future events with an explicit date and venue.
Existing car events and member data are not changed.
"""

import json
import re
import urllib.request
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
EVENTS_FILE = ROOT / "data" / "manual-events.json"

TODAY = datetime.now(
    ZoneInfo("Europe/London")
).date()

# Official organiser pages to check.
# More sources can be added after testing.
SOURCES = [
    {
        "name": "Motorcycle Live",
        "url": "https://www.motorcyclelive.co.uk/",
        "category": "Motorcycle Show",
    },
]

BIKE_WORDS = re.compile(
    r"\b("
    r"motorcycle|motorbike|motorcycles|"
    r"motorbikes|superbike|superbikes|"
    r"motocross|bike show|bike racing|"
    r"motorcycle live|moto ?gp"
    r")\b",
    re.IGNORECASE,
)


class StructuredDataParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts = []
        self.collecting = False
        self.current = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "script":
            return

        attributes = dict(attrs)
        script_type = attributes.get(
            "type", ""
        ).lower().strip()

        if script_type == "application/ld+json":
            self.collecting = True
            self.current = []

    def handle_data(self, data):
        if self.collecting:
            self.current.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "script" and self.collecting:
            self.scripts.append(
                "".join(self.current)
            )
            self.collecting = False
            self.current = []


def fetch(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 "
                "(compatible; PITLANE-UK/1.0)"
            )
        },
    )

    with urllib.request.urlopen(
        request, timeout=25
    ) as response:
        raw = response.read(2_000_000)
        encoding = (
            response.headers.get_content_charset()
            or "utf-8"
        )

    return raw.decode(
        encoding, errors="replace"
    )


def structured_items(value):
    """Recursively find schema.org Event objects."""
    if isinstance(value, list):
        for item in value:
            yield from structured_items(item)

    elif isinstance(value, dict):
        event_type = value.get("@type", "")

        if isinstance(event_type, list):
            types = event_type
        else:
            types = [event_type]

        if any(
            str(item).split("/")[-1] == "Event"
            or str(item).endswith("Event")
            for item in types
        ):
            yield value

        for key, item in value.items():
            if key != "@type":
                yield from structured_items(item)


def parse_date(value):
    if not isinstance(value, str):
        return None

    try:
        return date.fromisoformat(
            value[:10]
        )
    except ValueError:
        return None


def get_venue(location):
    if isinstance(location, list):
        for item in location:
            venue = get_venue(item)
            if venue:
                return venue
        return ""

    if isinstance(location, str):
        return location.strip()

    if not isinstance(location, dict):
        return ""

    name = location.get("name", "")

    if isinstance(name, str):
        return name.strip()

    return ""


def is_bike_event(name, source):
    return bool(
        BIKE_WORDS.search(name)
        or BIKE_WORDS.search(source["name"])
    )


def read_source(source):
    html = fetch(source["url"])

    parser = StructuredDataParser()
    parser.feed(html)

    found = []

    for script in parser.scripts:
        try:
            structured = json.loads(script)
        except json.JSONDecodeError:
            continue

        for item in structured_items(structured):
            name = item.get("name", "")
            if not isinstance(name, str):
                continue

            name = name.strip()
            if not name:
                continue

            if not is_bike_event(name, source):
                continue

            start = parse_date(
                item.get("startDate")
            )

            end = parse_date(
                item.get("endDate")
            ) or start

            if not start or end < TODAY:
                continue

            if end < start:
                continue

            venue = get_venue(
                item.get("location")
            )

            if not venue:
                print(
                    "SKIPPED: no confirmed venue:",
                    name
                )
                continue

            # Avoid importing virtual events.
            location = item.get("location")

            if (
                isinstance(location, dict)
                and location.get("@type")
                == "VirtualLocation"
            ):
                continue

            # Use the organiser's known official page.
            official_url = source["url"]

            found.append({
                "name": name,
                "date": start.isoformat(),
                "end_date": end.isoformat(),
                "venue": venue,
                "region": "",
                "category": source["category"],
                "organiser": source["name"],
                "official_url": official_url,
                "status": "Listed by organiser",
            })

    return found


def event_key(event):
    return (
        str(event.get("name", "")).strip().casefold(),
        str(event.get("date", "")).strip(),
        str(event.get("venue", "")).strip().casefold(),
    )


def main():
    print("PITLANE UK - BIKE EVENT IMPORTER")
    print("UK date:", TODAY)

    if not EVENTS_FILE.exists():
        raise FileNotFoundError(
            "Missing data/manual-events.json"
        )

    events = json.loads(
        EVENTS_FILE.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(events, list):
        raise ValueError(
            "manual-events.json must be a list"
        )

    existing = {
        event_key(event)
        for event in events
        if isinstance(event, dict)
    }

    added = 0
    checked = 0
    failures = 0

    for source in SOURCES:
        print()
        print("Checking:", source["name"])

        try:
            imported = read_source(source)
            checked += 1

        except Exception as error:
            failures += 1
            print(
                "SOURCE ERROR:",
                str(error)[:200]
            )
            continue

        if not imported:
            print(
                "No qualifying upcoming events "
                "found in structured data."
            )

        for event in imported:
            key = event_key(event)

            if key in existing:
                print(
                    "ALREADY LISTED:",
                    event["name"]
                )
                continue

            events.append(event)
            existing.add(key)
            added += 1

            print(
                "ADDED:",
                event["name"],
                event["date"],
                event["venue"]
            )

    if added:
        EVENTS_FILE.write_text(
            json.dumps(
                events,
                indent=2,
                ensure_ascii=False
            ) + "\n",
            encoding="utf-8"
        )

    print()
    print("BIKE IMPORT SUMMARY")
    print("Sources checked:", checked)
    print("Source failures:", failures)
    print("Events added:", added)
    print("Total manual events:", len(events))


if __name__ == "__main__":
    main()


#!/usr/bin/env python3
"""Import upcoming Carmeets UK events without Goodwood duplicates."""

import json
import re
import urllib.request
from datetime import date
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

BASE = Path(__file__).resolve().parent
EVENTS_FILE = BASE / "data/manual-events.json"
SOURCES_FILE = BASE / "modified-sources.json"

CALENDAR_URL = "https://carmeetsuk.com/events/list/"
MAX_PAGES = 15
MAX_EVENTS = 200


def download(url):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 PITLANE-UK/1.0"},
    )
    with urllib.request.urlopen(
        request, timeout=25
    ) as response:
        return response.read(2_000_000).decode(
            "utf-8", errors="replace"
        )


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.scripts = []
        self.in_json = False
        self.script_text = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)

        if tag == "a":
            href = attrs.get("href")
            if href:
                self.links.append(href)

        if tag == "script":
            if "application/ld+json" in attrs.get(
                "type", ""
            ).lower():
                self.in_json = True
                self.script_text = ""

    def handle_data(self, data):
        if self.in_json:
            self.script_text += data

    def handle_endtag(self, tag):
        if tag == "script" and self.in_json:
            self.scripts.append(self.script_text)
            self.in_json = False


def parse_page(html):
    parser = PageParser()
    parser.feed(html)
    return parser


def normalise(value):
    value = unescape(str(value)).lower()
    return " ".join(
        re.sub(r"[^a-z0-9]+", " ", value).split()
    )


def is_carmeets(url):
    return urlparse(url).netloc.lower() in (
        "carmeetsuk.com",
        "www.carmeetsuk.com",
    )


def clean_url(url):
    parsed = urlparse(url)
    return (
        parsed.scheme
        + "://"
        + parsed.netloc
        + parsed.path
    )


def find_event_links():
    pending = [CALENDAR_URL]
    visited = set()
    found = set()

    while pending and len(visited) < MAX_PAGES:
        url = pending.pop(0)

        if url in visited:
            continue

        visited.add(url)
        print(f"Checking calendar: {url}")

        try:
            parser = parse_page(download(url))
        except Exception as error:
            print(f"Calendar failed: {error}")
            continue

        for href in parser.links:
            link = urljoin(url, href)
            parsed = urlparse(link)

            if not is_carmeets(link):
                continue

            if parsed.path.startswith("/event/"):
                found.add(clean_url(link))
                continue

            # Follow only future/upcoming calendar pages.
            # Never follow past views or iCalendar links.
            if (
                "eventDisplay=past" in link
                or "ical=" in link.lower()
                or "outlook-ical=" in link.lower()
            ):
                continue

            if (
                parsed.path.startswith("/events/list/page/")
                and link not in visited
                and link not in pending
            ):
                pending.append(link)

        print(f"Event links found: {len(found)}")

    return sorted(found)


def find_events(data):
    result = []

    if isinstance(data, list):
        for item in data:
            result.extend(find_events(item))

    elif isinstance(data, dict):
        types = data.get("@type", [])
        if isinstance(types, str):
            types = [types]

        if "Event" in types:
            result.append(data)

        for value in data.values():
            if isinstance(value, (list, dict)):
                result.extend(find_events(value))

    return result


def get_venue(event):
    location = event.get("location", "")

    if isinstance(location, list):
        location = location[0] if location else ""

    if isinstance(location, str):
        return unescape(location).strip()

    if isinstance(location, dict):
        name = location.get("name", "")
        address = location.get("address", "")

        if isinstance(address, dict):
            address = ", ".join(
                str(address.get(key, ""))
                for key in (
                    "streetAddress",
                    "addressLocality",
                    "addressRegion",
                )
                if address.get(key)
            )

        return unescape(str(name or address)).strip()

    return ""


def read_event(url):
    parser = parse_page(download(url))

    for script in parser.scripts:
        try:
            objects = find_events(json.loads(script))
        except (ValueError, TypeError):
            continue

        for item in objects:
            name = unescape(
                str(item.get("name", ""))
            ).strip()

            start_text = str(item.get("startDate", ""))
            end_text = str(item.get("endDate", ""))
            venue = get_venue(item)

            if not name or not venue:
                continue

            try:
                start = date.fromisoformat(
                    start_text[:10]
                )
                end = (
                    date.fromisoformat(end_text[:10])
                    if end_text
                    else start
                )
            except ValueError:
                continue

            if end < start or end < date.today():
                continue

            return {
                "name": name,
                "date": start.isoformat(),
                "end_date": end.isoformat(),
                "venue": venue,
                "region": "",
                "category": "Car show",
                "organiser": "Carmeets UK",
                "official_url": url,
                "status": "Unverified",
            }

    return None


def is_festival_of_speed(event):
    name = normalise(event.get("name", ""))
    return "festival of speed" in name


def is_goodwood_duplicate(event, existing):
    if not is_festival_of_speed(event):
        return False

    for other in existing:
        if other.get("organiser") != "Goodwood":
            continue

        if not is_festival_of_speed(other):
            continue

        if other.get("date") == event.get("date"):
            return True

    return False


def is_duplicate(event, existing):
    new_url = event["official_url"].rstrip("/")
    new_name = normalise(event["name"])

    for other in existing:
        old_url = str(
            other.get("official_url", "")
        ).rstrip("/")

        if old_url == new_url:
            return True

        if other.get("date") != event["date"]:
            continue

        old_name = normalise(other.get("name", ""))

        if old_name == new_name:
            return True

        if is_goodwood_duplicate(event, [other]):
            return True

    return False


def remove_goodwood_duplicates(events):
    cleaned = []
    removed = 0

    for event in events:
        if (
            event.get("organiser") == "Carmeets UK"
            and is_goodwood_duplicate(event, events)
        ):
            print(
                "REMOVED DUPLICATE: "
                + event.get("name", "")
            )
            removed += 1
            continue

        cleaned.append(event)

    return cleaned, removed


def main():
    sources = json.loads(
        SOURCES_FILE.read_text(encoding="utf-8")
    )
    print(
        f"Loaded {len(sources.get('sources', []))} sources."
    )

    existing = json.loads(
        EVENTS_FILE.read_text(encoding="utf-8")
    )

    if not isinstance(existing, list):
        raise ValueError(
            "manual-events.json must contain a list."
        )

    existing, removed = remove_goodwood_duplicates(
        existing
    )

    links = find_event_links()
    print(f"\nFound {len(links)} event links.")

    added = 0
    skipped = 0

    for url in links[:MAX_EVENTS]:
        try:
            event = read_event(url)
        except Exception as error:
            print(f"Could not read {url}: {error}")
            skipped += 1
            continue

        if event is None:
            skipped += 1
            continue

        if is_duplicate(event, existing):
            print(f"Already listed: {event['name']}")
            skipped += 1
            continue

        existing.append(event)
        added += 1
        print(
            f"ADDED: {event['name']} "
            f"({event['date']})"
        )

    if added or removed:
        EVENTS_FILE.write_text(
            json.dumps(
                existing,
                indent=2,
                ensure_ascii=False,
            ) + "\n",
            encoding="utf-8",
        )

    print("\n--- IMPORT SUMMARY ---")
    print(f"Event links found: {len(links)}")
    print(f"New events added: {added}")
    print(f"Goodwood duplicates removed: {removed}")
    print(f"Skipped or already listed: {skipped}")
    print("Carmeets UK import complete.")


if __name__ == "__main__":
    main()

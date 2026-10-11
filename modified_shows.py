
#!/usr/bin/env python3
"""Discover and import Carmeets UK events for PITLANE UK."""

import json
import re
import urllib.request
from datetime import date
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag

BASE = Path(__file__).resolve().parent
SOURCES_FILE = BASE / "modified-sources.json"
EVENTS_FILE = BASE / "data/manual-events.json"

CALENDAR_URL = "https://carmeetsuk.com/events/list/"
MAX_PAGES = 15
MAX_EVENTS = 200


def download(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 PITLANE-UK/1.0"
        },
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
        self.next_links = []
        self.json_scripts = []
        self.in_json = False
        self.script_text = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)

        if tag == "a":
            href = attrs.get("href", "")
            if href:
                self.links.append(href)

            rel = attrs.get("rel", "")
            if "next" in rel.lower().split():
                self.next_links.append(href)

        if tag == "link":
            rel = attrs.get("rel", "")
            if "next" in rel.lower().split():
                href = attrs.get("href", "")
                if href:
                    self.next_links.append(href)

        if tag == "script":
            script_type = attrs.get("type", "").lower()
            if "application/ld+json" in script_type:
                self.in_json = True
                self.script_text = ""

    def handle_data(self, data):
        if self.in_json:
            self.script_text += data

    def handle_endtag(self, tag):
        if tag == "script" and self.in_json:
            self.json_scripts.append(self.script_text)
            self.in_json = False


def parse_page(html):
    parser = PageParser()
    parser.feed(html)
    return parser


def clean_url(url):
    return urldefrag(url)[0]


def is_carmeets(url):
    return urlparse(url).netloc.lower() in (
        "carmeetsuk.com",
        "www.carmeetsuk.com",
    )


def is_event_link(url):
    path = urlparse(url).path

    return (
        is_carmeets(url)
        and path.startswith("/event/")
        and path.rstrip("/") != "/event"
    )


def is_calendar_page(url):
    parsed = urlparse(url)

    return (
        is_carmeets(url)
        and parsed.path.startswith("/events/")
        and (
            "/list" in parsed.path
            or "/page/" in parsed.path
            or "page=" in parsed.query
        )
    )


def find_event_links():
    pending = [CALENDAR_URL]
    visited = set()
    event_links = set()

    while pending and len(visited) < MAX_PAGES:
        url = pending.pop(0)

        if url in visited:
            continue

        visited.add(url)
        print(f"Checking calendar: {url}")

        try:
            html = download(url)
            parser = parse_page(html)
        except Exception as error:
            print(f"Calendar check failed: {error}")
            continue

        for href in parser.links:
            link = clean_url(urljoin(url, href))

            if is_event_link(link):
                event_links.add(link)

        for href in parser.links + parser.next_links:
            link = clean_url(urljoin(url, href))

            if (
                is_calendar_page(link)
                and link not in visited
                and link not in pending
            ):
                pending.append(link)

        print(
            f"Events discovered: {len(event_links)}"
        )

    if pending:
        print("Calendar page limit reached.")

    return sorted(event_links)


def find_event_objects(data):
    found = []

    if isinstance(data, list):
        for item in data:
            found.extend(find_event_objects(item))

    elif isinstance(data, dict):
        event_type = data.get("@type", [])
        types = (
            event_type
            if isinstance(event_type, list)
            else [event_type]
        )

        if "Event" in types:
            found.append(data)

        for key, value in data.items():
            if key != "@context" and isinstance(
                value, (dict, list)
            ):
                found.extend(find_event_objects(value))

    return found


def get_location(event):
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
                str(value)
                for key, value in address.items()
                if key in (
                    "streetAddress",
                    "addressLocality",
                    "addressRegion",
                )
                and value
            )

        return unescape(
            str(name or address)
        ).strip()

    return ""


def read_event(url):
    html = download(url)
    parser = parse_page(html)

    for script in parser.json_scripts:
        try:
            data = json.loads(script)
        except (ValueError, TypeError):
            continue

        for event in find_event_objects(data):
            name = unescape(
                str(event.get("name", ""))
            ).strip()

            start_value = str(
                event.get("startDate", "")
            )

            end_value = str(
                event.get("endDate", "")
            )

            venue = get_location(event)

            if not (
                name
                and venue
                and re.match(
                    r"^\d{4}-\d{2}-\d{2}",
                    start_value,
                )
            ):
                continue

            try:
                start = date.fromisoformat(
                    start_value[:10]
                )

                end = (
                    date.fromisoformat(end_value[:10])
                    if end_value
                    else start
                )
            except ValueError:
                continue

            if end < start:
                continue

            if start < date.today():
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


def normalise(value):
    value = unescape(str(value)).lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def duplicate_event(new_event, existing):
    new_url = new_event["official_url"].rstrip("/")

    for event in existing:
        old_url = str(
            event.get("official_url", "")
        ).rstrip("/")

        if old_url and old_url == new_url:
            return True

        if event.get("date") != new_event["date"]:
            continue

        new_name = normalise(new_event["name"])
        old_name = normalise(event.get("name", ""))

        new_venue = normalise(new_event["venue"])
        old_venue = normalise(event.get("venue", ""))

        if new_name == old_name:
            return True

        if (
            new_venue
            and new_venue == old_venue
            and (
                new_name in old_name
                or old_name in new_name
            )
        ):
            return True

    return False


def main():
    source_data = json.loads(
        SOURCES_FILE.read_text(encoding="utf-8")
    )

    print(
        f"Loaded {len(source_data['sources'])} sources."
    )

    existing = json.loads(
        EVENTS_FILE.read_text(encoding="utf-8")
    )

    if not isinstance(existing, list):
        raise ValueError(
            "Expected manual-events.json to contain a list."
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
            print(f"No usable event details: {url}")
            skipped += 1
            continue

        if duplicate_event(event, existing):
            print(
                f"Already listed: {event['name']}"
            )
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
    print(f"Event links found: {len(links)}")
    print(f"New events added: {added}")
    print(f"Skipped or already listed: {skipped}")
    print("Carmeets UK import complete.")


if __name__ == "__main__":
    main()

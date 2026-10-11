
#!/usr/bin/env python3
"""Discover UK car shows and test Carmeets UK event extraction."""

import json
import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

BASE = Path(__file__).resolve().parent
SOURCES_FILE = BASE / "modified-sources.json"

CALENDAR_URL = "https://carmeetsuk.com/events/list/"
MAX_PAGES = 5
MAX_EVENTS = 30


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
        self.json_scripts = []
        self.in_json = False
        self.script_text = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)

        if tag == "a":
            href = attrs.get("href", "")
            if href:
                self.links.append(href)

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


def is_event_link(url):
    parsed = urlparse(url)

    return (
        parsed.netloc.lower()
        in ("carmeetsuk.com", "www.carmeetsuk.com")
        and parsed.path.startswith("/event/")
        and parsed.path.rstrip("/") != "/event"
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
        print(f"Checking calendar page: {url}")

        try:
            html = download(url)
        except Exception as error:
            print(f"Calendar page failed: {error}")
            continue

        parser = parse_page(html)

        for href in parser.links:
            link = urljoin(url, href)
            parsed = urlparse(link)

            if is_event_link(link):
                clean_link = (
                    f"{parsed.scheme}://{parsed.netloc}"
                    f"{parsed.path}"
                )
                event_links.add(clean_link)

            # Follow recognised calendar pagination links.
            if (
                parsed.netloc.lower()
                in ("carmeetsuk.com", "www.carmeetsuk.com")
                and (
                    "/events/list/page/" in parsed.path
                    or (
                        parsed.path.rstrip("/")
                        == "/events/list"
                        and "page=" in parsed.query
                    )
                )
                and link not in visited
                and link not in pending
            ):
                pending.append(link)

        print(
            f"Event links discovered so far: "
            f"{len(event_links)}"
        )

    return sorted(event_links)


def find_event_objects(data):
    found = []

    if isinstance(data, list):
        for item in data:
            found.extend(find_event_objects(item))

    elif isinstance(data, dict):
        event_type = data.get("@type", "")
        types = (
            event_type if isinstance(event_type, list)
            else [event_type]
        )

        if "Event" in types:
            found.append(data)

        for key, value in data.items():
            if key != "@context":
                if isinstance(value, (dict, list)):
                    found.extend(find_event_objects(value))

    return found


def event_location(event):
    location = event.get("location", "")

    if isinstance(location, str):
        return location

    if isinstance(location, list):
        location = location[0] if location else {}

    if isinstance(location, dict):
        name = location.get("name", "")

        address = location.get("address", "")
        if isinstance(address, dict):
            parts = [
                address.get("streetAddress", ""),
                address.get("addressLocality", ""),
                address.get("addressRegion", ""),
            ]
            address = ", ".join(
                str(part) for part in parts if part
            )

        return name or address

    return ""


def check_event(url):
    try:
        html = download(url)
        parser = parse_page(html)

        events = []

        for script in parser.json_scripts:
            try:
                data = json.loads(script)
                events.extend(find_event_objects(data))
            except (ValueError, TypeError):
                continue

        if not events:
            print(f"DETAILS NOT FOUND: {url}")
            return

        for event in events:
            name = event.get("name", "Unknown event")
            start = event.get("startDate", "Unknown date")
            end = event.get("endDate", "")
            venue = event_location(event)

            print(f"EVENT: {name}")
            print(f"  Start: {start}")
            print(f"  End: {end or 'Not provided'}")
            print(f"  Location: {venue or 'Not provided'}")
            print(f"  Source: {url}")

    except Exception as error:
        print(f"Could not read event: {url}")
        print(f"  Error: {error}")


def main():
    data = json.loads(
        SOURCES_FILE.read_text(encoding="utf-8")
    )

    sources = data.get("sources", [])

    print(
        f"Loaded {len(sources)} modified car show sources."
    )

    # Keep checking the existing source websites.
    for source in sources:
        name = source.get("name", "Unknown")
        url = source.get("url", "").strip()

        if not url:
            print(f"Skipping {name}: no website.")
            continue

        try:
            html = download(url)
            print(
                f"Checked {name}: "
                f"received {len(html)} characters"
            )
        except Exception as error:
            print(f"Could not check {name}: {error}")

    print("\n--- CARMEETS UK DISCOVERY ---")

    links = find_event_links()

    print(f"\nFound {len(links)} event links.")

    # Limit testing so the workflow stays manageable.
    for url in links[:MAX_EVENTS]:
        check_event(url)

    print("\nDiscovery test complete.")
    print("No events were added or changed.")


if __name__ == "__main__":
    main()

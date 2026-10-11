
#!/usr/bin/env python3
"""Import Carmeets UK events using its public events API."""

import json
import re
import urllib.request
from datetime import date
from html import unescape
from pathlib import Path
from urllib.parse import urlparse

BASE = Path(__file__).resolve().parent
EVENTS_FILE = BASE / "data/manual-events.json"
SOURCES_FILE = BASE / "modified-sources.json"

API_URL = (
    "https://carmeetsuk.com/"
    "wp-json/tribe/events/v1/events"
)

MAX_PAGES = 20


def clean_text(value):
    text = str(value or "")
    for _ in range(3):
        cleaned = unescape(text)
        if cleaned == text:
            break
        text = cleaned
    return " ".join(text.split())


def normalise(value):
    return " ".join(
        re.sub(
            r"[^a-z0-9]+",
            " ",
            clean_text(value).lower(),
        ).split()
    )


def clean_url(value):
    parsed = urlparse(str(value or ""))
    return (
        parsed.netloc.lower().removeprefix("www.")
        + parsed.path.rstrip("/")
    )


def fetch_api():
    all_events = []
    seen_urls = set()

    for page in range(1, MAX_PAGES + 1):
        url = (
            f"{API_URL}?per_page=50&page={page}"
        )

        print(f"Checking API page {page}")

        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 PITLANE-UK/1.0",
                "Accept": "application/json",
            },
        )

        with urllib.request.urlopen(
            request, timeout=30
        ) as response:
            data = json.load(response)

        if not isinstance(data, dict):
            raise ValueError("Unexpected API response.")

        events = data.get("events")

        if not isinstance(events, list):
            raise ValueError("API event list missing.")

        print(f"Events returned: {len(events)}")

        for event in events:
            if not isinstance(event, dict):
                continue

            event_url = clean_url(event.get("url", ""))

            if event_url and event_url in seen_urls:
                continue

            if event_url:
                seen_urls.add(event_url)

            all_events.append(event)

        total_pages = data.get("total_pages", 1)

        try:
            total_pages = int(total_pages)
        except (ValueError, TypeError):
            raise ValueError("Invalid API page count.")

        if page >= total_pages or not events:
            break

    else:
        print("Warning: API page limit reached.")

    return all_events


def get_venue(event):
    venue = event.get("venue", {})

    if isinstance(venue, str):
        return clean_text(venue)

    if not isinstance(venue, dict):
        return ""

    name = venue.get("venue", "") or venue.get(
        "name", ""
    )

    if name:
        return clean_text(name)

    return clean_text(
        venue.get("address", "")
        or venue.get("city", "")
    )


def convert_event(item):
    name = clean_text(item.get("title", ""))
    url = str(item.get("url", "")).strip()
    venue = get_venue(item)

    start_text = str(item.get("start_date", ""))
    end_text = str(item.get("end_date", ""))

    if not name or not venue or not url:
        return None

    if urlparse(url).netloc.lower() not in (
        "carmeetsuk.com",
        "www.carmeetsuk.com",
    ):
        return None

    try:
        start = date.fromisoformat(start_text[:10])
        end = (
            date.fromisoformat(end_text[:10])
            if end_text
            else start
        )
    except ValueError:
        return None

    if end < start or end < date.today():
        return None

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


def is_festival_of_speed(event):
    return (
        "festival of speed"
        in normalise(event.get("name", ""))
    )


def goodwood_duplicate(event, existing):
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


def find_existing(event, existing):
    new_url = clean_url(event["official_url"])
    new_name = normalise(event["name"])

    for other in existing:
        old_url = clean_url(
            other.get("official_url", "")
        )

        if old_url and old_url == new_url:
            return other, "same URL"

        if other.get("date") != event["date"]:
            continue

        if normalise(other.get("name", "")) == new_name:
            return other, "same name and date"

        if goodwood_duplicate(event, [other]):
            return other, "Goodwood duplicate"

    return None, ""


def remove_goodwood_duplicates(events):
    cleaned = []
    removed = 0

    for event in events:
        if (
            event.get("organiser") == "Carmeets UK"
            and goodwood_duplicate(event, events)
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

    # Retrieve everything before changing local data.
    try:
        raw_events = fetch_api()
    except Exception as error:
        print(f"API failed: {error}")
        print("Existing calendar left unchanged.")
        return

    print(
        f"\nAPI returned {len(raw_events)} events."
    )

    existing, removed = remove_goodwood_duplicates(
        existing
    )

    added = 0
    skipped = 0
    changed_dates = 0

    for item in raw_events:
        event = convert_event(item)

        if event is None:
            skipped += 1
            continue

        if goodwood_duplicate(event, existing):
            print(
                f"GOODWOOD DUPLICATE: {event['name']}"
            )
            skipped += 1
            continue

        match, reason = find_existing(
            event, existing
        )

        if match:
            if (
                reason == "same URL"
                and match.get("date") != event["date"]
            ):
                print(
                    "DATE CHANGE - REVIEW: "
                    + event["name"]
                )
                print(
                    "  Listed: "
                    + str(match.get("date"))
                )
                print(
                    "  API: "
                    + event["date"]
                )
                changed_dates += 1
            else:
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
    print(f"API events returned: {len(raw_events)}")
    print(f"New events added: {added}")
    print(f"Goodwood duplicates removed: {removed}")
    print(f"Skipped or already listed: {skipped}")
    print(f"Date changes needing review: {changed_dates}")
    print("Carmeets UK API import complete.")


if __name__ == "__main__":
    main()


#!/usr/bin/env python3
"""PITLANE UK: combined event importer and future-date checker."""

import json
import re
import urllib.request
from datetime import date, datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
EVENTS_FILE = ROOT / "data/manual-events.json"

SHOWS = [
    {
        "name": "The Reunion Show",
        "url": "https://www.thereunionshow.co.uk/",
        "venue": "Staffordshire Showground",
        "region": "West Midlands",
        "confirmed": ("2027-07-11", "2027-07-11"),
    },
    {
        "name": "Ultimate Street Car",
        "url": "https://ultimatestreetcar.co.uk/",
        "venue": "Santa Pod Raceway",
        "region": "East of England",
        "confirmed": ("2027-07-30", "2027-08-01"),
    },
    {
        "name": "Rollhard Bicester",
        "url": "https://www.rollhard.co.uk/pages/bicester",
        "venue": "Bicester Heritage",
        "region": "South East",
        "confirmed": ("2027-08-01", "2027-08-01"),
    },
    {
        "name": "Isle of Wight Takeover",
        "url": "https://www.iowtakeover.co.uk/",
        "venue": "Royal Isle of Wight County Showground",
        "region": "South East",
        "confirmed": ("2027-05-15", "2027-05-16"),
    },
]

MONTHS = (
    "January February March April May June July August "
    "September October November December"
).split()

MONTH_RE = "|".join(MONTHS)

DATE_RE = re.compile(
    rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+"
    rf"(?:{MONTH_RE})\s+20\d{{2}}\b"
    rf"|\b(?:{MONTH_RE})\s+"
    rf"\d{{1,2}}(?:st|nd|rd|th)?,?\s+20\d{{2}}\b"
    r"|\b20\d{2}-\d{2}-\d{2}\b",
    re.IGNORECASE,
)


class PageText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.hidden:
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)

    def text(self):
        return unescape(" ".join(self.parts))


def fetch_page(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 PITLANE-UK",
        },
    )
    with urllib.request.urlopen(
        request, timeout=20
    ) as response:
        raw = response.read(2_000_000)
        encoding = response.headers.get_content_charset()
    parser = PageText()
    parser.feed(
        raw.decode(encoding or "utf-8", errors="replace")
    )
    return parser.text()


def parse_date(value):
    value = re.sub(
        r"(\d+)(st|nd|rd|th)\b",
        r"\1",
        value,
        flags=re.IGNORECASE,
    )
    value = value.replace(",", "")

    try:
        return date.fromisoformat(value)
    except ValueError:
        pass

    for fmt in ("%d %B %Y", "%B %d %Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass

    return None


def discovered_dates(text, today):
    found = set()

    for match in DATE_RE.finditer(text):
        parsed = parse_date(match.group(0))
        if parsed and parsed >= today:
            found.add(parsed)

    return sorted(found)


def make_event(show):
    start, end = show["confirmed"]
    year = start[:4]

    return {
        "name": f"{show['name']} {year}",
        "date": start,
        "end_date": end,
        "venue": show["venue"],
        "region": show["region"],
        "category": "Modified Car Show",
        "organiser": show["name"],
        "official_url": show["url"],
        "status": "confirmed",
    }


def main():
    today = datetime.now(
        ZoneInfo("Europe/London")
    ).date()

    events = json.loads(
        EVENTS_FILE.read_text(encoding="utf-8")
    )

    if not isinstance(events, list):
        raise ValueError(
            "manual-events.json must contain a list."
        )

    print("PITLANE UK - COMBINED EVENT IMPORTER")
    print(f"Today's UK date: {today}")

    added = 0
    existing = 0
    reviews = 0
    failures = 0

    for show in SHOWS:
        print(f"\n--- {show['name']} ---")

        confirmed = make_event(show)

        # Preserve the four confirmed 2027 editions.
        if date.fromisoformat(confirmed["end_date"]) >= today:
            matches = [
                item for item in events
                if item.get("name", "").strip().casefold()
                == confirmed["name"].casefold()
            ]

            if matches:
                old = matches[0]
                if any(
                    old.get(key) != confirmed[key]
                    for key in ("date", "end_date", "venue")
                ):
                    print(
                        "REVIEW EXISTING EVENT: "
                        + confirmed["name"]
                    )
                    reviews += 1
                else:
                    print("ALREADY LISTED: " + confirmed["name"])
                    existing += 1
            else:
                events.append(confirmed)
                added += 1
                print("ADDED: " + confirmed["name"])

        # Check the organiser's website for future editions.
        try:
            page = fetch_page(show["url"])
            dates = discovered_dates(page, today)
        except Exception as error:
            failures += 1
            print(f"WEBSITE CHECK FAILED: {error}")
            continue

        future_years = {}

        for event_date in dates:
            if event_date.year > 2027:
                future_years.setdefault(
                    event_date.year, []
                ).append(event_date)

        for year, candidates in sorted(future_years.items()):
            event_name = f"{show['name']} {year}"

            already_listed = any(
                item.get("name", "").strip().casefold()
                == event_name.casefold()
                for item in events
            )

            if already_listed:
                print(
                    "FUTURE EDITION ALREADY LISTED: "
                    + event_name
                )
                continue

            # A date alone cannot establish the full
            # event duration or confirm the venue.
            print("NEW EDITION NEEDS REVIEW: " + event_name)
            print(
                "  Possible dates: "
                + ", ".join(str(d) for d in candidates)
            )
            print("  Verify start date, end date and venue.")
            reviews += 1

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
    print(f"Events needing review: {reviews}")
    print(f"Website checks failed: {failures}")
    print(f"Total manual events: {len(events)}")
    print("Future editions require verification before import.")


if __name__ == "__main__":
    main()

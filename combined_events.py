
#!/usr/bin/env python3
"""PITLANE UK - Combined automatic event importer."""

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

MONTHS = {
    month.lower(): number
    for number, month in enumerate(
        [
            "January", "February", "March", "April",
            "May", "June", "July", "August",
            "September", "October", "November",
            "December",
        ],
        start=1,
    )
}

MONTH_RE = "|".join(MONTHS)

DAY = r"\d{1,2}(?:st|nd|rd|th)?"
WEEKDAY = r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)(?:day)?"

SHOWS = [
    {
        "name": "The Reunion Show",
        "url": "https://www.thereunionshow.co.uk/",
        "venue": "Staffordshire Showground",
        "region": "West Midlands",
        "type": "reunion",
    },
    {
        "name": "Ultimate Street Car",
        "url": "https://ultimatestreetcar.co.uk/",
        "venue": "Santa Pod Raceway",
        "region": "East of England",
        "type": "usc",
    },
    {
        "name": "Rollhard Bicester",
        "url": "https://www.rollhard.co.uk/pages/bicester",
        "venue": "Bicester Heritage",
        "region": "South East",
        "type": "rollhard",
    },
    {
        "name": "Isle of Wight Takeover",
        "url": "https://www.iowtakeover.co.uk/",
        "venue": "Royal Isle of Wight County Showground",
        "region": "Isle of Wight",
        "type": "takeover",
    },
]


class TextExtractor(HTMLParser):
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
        return re.sub(
            r"\s+",
            " ",
            unescape(" ".join(self.parts)),
        ).strip()


def fetch_page(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 PITLANE-UK"
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=20,
    ) as response:
        raw = response.read(2_000_000)
        charset = response.headers.get_content_charset()

    parser = TextExtractor()

    parser.feed(
        raw.decode(
            charset or "utf-8",
            errors="replace",
        )
    )

    return parser.text()


def make_date(day, month, year):
    day = int(
        re.match(r"\d+", day).group()
    )

    month = MONTHS[month.lower()]

    return date(
        int(year),
        month,
        day,
    )


def extract_reunion(text):
    pattern = (
        rf"\b({DAY})\s+"
        rf"({MONTH_RE})\s+"
        rf"(20\d{{2}})\b"
    )

    results = []

    for match in re.finditer(
        pattern,
        text,
        re.IGNORECASE,
    ):
        try:
            d = make_date(*match.groups())
            results.append((d, d))
        except ValueError:
            continue

    return results


def extract_usc(text):
    pattern = (
        rf"(?:{WEEKDAY}\s+)?"
        rf"({DAY})\s+({MONTH_RE})\s+"
        rf"(?:to|-|–)\s+"
        rf"(?:{WEEKDAY}\s+)?"
        rf"({DAY})\s+({MONTH_RE})\s+"
        rf"(20\d{{2}})"
    )

    results = []

    for match in re.finditer(
        pattern,
        text,
        re.IGNORECASE,
    ):
        (
            first_day,
            first_month,
            last_day,
            last_month,
            year,
        ) = match.groups()

        try:
            start = make_date(
                first_day,
                first_month,
                year,
            )

            end = make_date(
                last_day,
                last_month,
                year,
            )

            if (
                end >= start
                and (end - start).days <= 7
            ):
                results.append((start, end))

        except ValueError:
            continue

    return results


def extract_rollhard(text):
    pattern = (
        r"\b(\d{2})\.(\d{2})\."
        r"(20\d{2})\b"
    )

    results = []

    for match in re.finditer(
        pattern,
        text,
    ):
        day, month, year = map(
            int,
            match.groups(),
        )

        try:
            d = date(year, month, day)
            results.append((d, d))
        except ValueError:
            continue

    return results


def extract_takeover(text):
    pattern = (
        rf"PARTY\s*[-–:]\s*"
        rf"({DAY})\s+({MONTH_RE})"
        rf".{{0,100}}?"
        rf"SHOW\s*DAY\s*[-–:]\s*"
        rf"({DAY})\s+({MONTH_RE})\s+"
        rf"(20\d{{2}})"
    )

    results = []

    for match in re.finditer(
        pattern,
        text,
        re.IGNORECASE,
    ):
        (
            first_day,
            first_month,
            last_day,
            last_month,
            year,
        ) = match.groups()

        try:
            start = make_date(
                first_day,
                first_month,
                year,
            )

            end = make_date(
                last_day,
                last_month,
                year,
            )

            if (
                end >= start
                and (end - start).days <= 7
            ):
                results.append((start, end))

        except ValueError:
            continue

    return results


EXTRACTORS = {
    "reunion": extract_reunion,
    "usc": extract_usc,
    "rollhard": extract_rollhard,
    "takeover": extract_takeover,
}


def venue_confirmed(text, show):
    """Check whether the expected venue is on the page."""

    return (
        show["venue"].casefold()
        in text.casefold()
    )


def venue_verified(text, show, start, end):
    """Verify the venue, including the confirmed 2027 exception."""

    if venue_confirmed(text, show):
        return True

    # The 2027 Isle of Wight Takeover venue was
    # confirmed separately by the organiser's details.
    # This exception applies only to that edition.
    if (
        show["type"] == "takeover"
        and start.isoformat() == "2027-05-15"
        and end.isoformat() == "2027-05-16"
    ):
        return True

    return False


def make_event(show, start, end):
    return {
        "name": (
            f"{show['name']} {start.year}"
        ),
        "date": start.isoformat(),
        "end_date": end.isoformat(),
        "venue": show["venue"],
        "region": show["region"],
        "category": "Modified Car Show",
        "organiser": show["name"],
        "official_url": show["url"],
        "status": "Listed by organiser",
    }


def main():
    today = datetime.now(
        ZoneInfo("Europe/London")
    ).date()

    events = json.loads(
        EVENTS_FILE.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(events, list):
        raise ValueError(
            "manual-events.json must contain a list."
        )

    added = 0
    updated = 0
    existing = 0
    review = 0
    failed = 0

    print(
        "PITLANE UK - AUTOMATIC COMBINED IMPORTER"
    )
    print(f"Today's UK date: {today}")

    for show in SHOWS:
        print(f"\n--- {show['name']} ---")

        try:
            page = fetch_page(show["url"])

        except Exception as error:
            failed += 1
            print(
                f"WEBSITE CHECK FAILED: {error}"
            )
            continue

        extractor = EXTRACTORS[
            show["type"]
        ]

        candidates = extractor(page)

        # Ignore editions that have finished.
        candidates = [
            (start, end)
            for start, end in candidates
            if end >= today
        ]

        if not candidates:
            print(
                "No complete upcoming date found."
            )
            continue

        # Group dates by event year.
        by_year = {}

        for start, end in candidates:
            by_year.setdefault(
                start.year,
                set(),
            ).add((start, end))

        for year, ranges in sorted(
            by_year.items()
        ):
            name = (
                f"{show['name']} {year}"
            )

            # Do not guess between different
            # dates for the same edition.
            if len(ranges) != 1:
                print(
                    "REVIEW CONFLICTING DATES: "
                    + name
                )
                review += 1
                continue

            start, end = next(
                iter(ranges)
            )

            # Only use verified venues.
            if not venue_verified(
                page,
                show,
                start,
                end,
            ):
                print(
                    "REVIEW VENUE NOT VERIFIED: "
                    + name
                )
                print(
                    f"  Dates found: "
                    f"{start} to {end}"
                )
                review += 1
                continue

            proposed = make_event(
                show,
                start,
                end,
            )

            # Find an existing edition.
            matches = [
                event
                for event in events
                if (
                    event.get(
                        "name", ""
                    ).strip().casefold()
                    == name.casefold()
                )
            ]

            if len(matches) > 1:
                print(
                    "REVIEW DUPLICATE EXISTING EVENTS: "
                    + name
                )
                review += 1
                continue

            # Add a new confirmed edition.
            if not matches:
                events.append(proposed)
                added += 1

                print(
                    f"ADDED: {name} "
                    f"({start} to {end})"
                )
                continue

            current = matches[0]

            old_start = current.get(
                "date"
            )

            old_end = current.get(
                "end_date",
                old_start,
            )

            old_venue = current.get(
                "venue"
            )

            # Never silently overwrite a
            # different existing venue.
            if old_venue != proposed["venue"]:
                print(
                    "REVIEW VENUE CHANGE: "
                    + name
                )
                print(
                    f"  Current: {old_venue}"
                )
                print(
                    "  Expected venue: "
                    + proposed["venue"]
                )
                review += 1
                continue

            # No changes required.
            if (
                old_start == proposed["date"]
                and old_end == proposed["end_date"]
            ):
                existing += 1
                print(
                    "ALREADY LISTED: "
                    + name
                )
                continue

            # Update a clearly identified
            # date change.
            print(
                "DATE CHANGE DETECTED: "
                + name
            )

            print(
                f"  Old: "
                f"{old_start} to {old_end}"
            )

            print(
                f"  New: "
                f"{proposed['date']} "
                f"to {proposed['end_date']}"
            )

            current["date"] = proposed[
                "date"
            ]

            current["end_date"] = proposed[
                "end_date"
            ]

            updated += 1

            print(
                "UPDATED: " + name
            )

    # Save only when events have changed.
    if added or updated:
        EVENTS_FILE.write_text(
            json.dumps(
                events,
                indent=2,
                ensure_ascii=False,
            ) + "\n",
            encoding="utf-8",
        )

    print(
        "\n--- COMBINED IMPORT SUMMARY ---"
    )

    print(
        f"Events added: {added}"
    )

    print(
        f"Events updated: {updated}"
    )

    print(
        f"Already listed: {existing}"
    )

    print(
        f"Events needing review: {review}"
    )

    print(
        f"Website checks failed: {failed}"
    )

    print(
        f"Total manual events: {len(events)}"
    )

    print(
        "Automatic import check complete."
    )


if __name__ == "__main__":
    main()



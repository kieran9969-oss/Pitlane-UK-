
#!/usr/bin/env python3
"""PITLANE UK - Automatic dates and venue checking."""

import json
import re
import urllib.request
from datetime import date, datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

FILE = Path(__file__).resolve().parent / "data/manual-events.json"

MONTHS = {
    m.lower(): i for i, m in enumerate(
        "January February March April May June July August "
        "September October November December".split(), 1
    )
}
MONTH = "|".join(MONTHS)
DAY = r"\d{1,2}(?:st|nd|rd|th)?"
WD = r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)(?:day)?"

SHOWS = [
    {
        "name": "The Reunion Show",
        "url": "https://www.thereunionshow.co.uk/",
        "venue": "Staffordshire Showground",
        "region": "West Midlands",
        "kind": "reunion",
    },
    {
        "name": "Ultimate Street Car",
        "url": "https://ultimatestreetcar.co.uk/",
        "venue": "Santa Pod Raceway",
        "region": "East of England",
        "kind": "usc",
    },
    {
        "name": "Rollhard Bicester",
        "url": "https://www.rollhard.co.uk/pages/bicester",
        "venue": "Bicester Heritage",
        "region": "South East",
        "kind": "rollhard",
    },
    {
        "name": "Isle of Wight Takeover",
        "url": "https://www.iowtakeover.co.uk/",
        "venue": "Royal Isle of Wight County Showground",
        "region": "Isle of Wight",
        "kind": "takeover",
    },
]

VENUE_ALIASES = {
    "Royal Isle of Wight County Showground": [
        "Royal Isle of Wight County Showground",
        "Royal Isle of Wight Agricultural Society County Show Ground",
    ],
    "Bicester Heritage": [
        "Bicester Heritage",
        "Bicester Motion",
    ],
    "Santa Pod Raceway": [
        "Santa Pod Raceway",
        "Santa Pod",
    ],
    "Staffordshire Showground": [
        "Staffordshire Showground",
    ],
}


class PageParser(HTMLParser):
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
            value = data.strip()
            if value:
                self.parts.append(value)

    def text(self):
        return unescape(" ".join(self.parts))


def fetch(url):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 PITLANE-UK"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read(2_000_000)
        encoding = response.headers.get_content_charset()

    parser = PageParser()
    parser.feed(raw.decode(encoding or "utf-8", errors="replace"))
    return re.sub(r"\s+", " ", parser.text()).strip()


def make_date(day, month, year):
    number = int(re.match(r"\d+", day).group())
    return date(int(year), MONTHS[month.lower()], number)


def dates_for(show, text):
    kind = show["kind"]
    found = []

    if kind == "reunion":
        pattern = rf"\b({DAY})\s+({MONTH})\s+(20\d{{2}})\b"
        for match in re.finditer(pattern, text, re.I):
            try:
                d = make_date(*match.groups())
                found.append((d, d))
            except ValueError:
                pass

    elif kind == "usc":
        pattern = (
            rf"(?:{WD}\s+)?({DAY})\s+({MONTH})\s+"
            rf"(?:to|-|–)\s+(?:{WD}\s+)?"
            rf"({DAY})\s+({MONTH})\s+(20\d{{2}})"
        )
        for match in re.finditer(pattern, text, re.I):
            a, am, b, bm, year = match.groups()
            try:
                start = make_date(a, am, year)
                end = make_date(b, bm, year)
                if 0 <= (end - start).days <= 7:
                    found.append((start, end))
            except ValueError:
                pass

    elif kind == "rollhard":
        pattern = r"\b(\d{2})\.(\d{2})\.(20\d{2})\b"
        for match in re.finditer(pattern, text):
            day, month, year = map(int, match.groups())
            try:
                d = date(year, month, day)
                found.append((d, d))
            except ValueError:
                pass

        # Also recognise written dates.
        pattern = rf"\b({DAY})\s+({MONTH})\s+(20\d{{2}})\b"
        for match in re.finditer(pattern, text, re.I):
            try:
                d = make_date(*match.groups())
                found.append((d, d))
            except ValueError:
                pass

    elif kind == "takeover":
        pattern = (
            rf"PARTY\s*[-–:]\s*({DAY})\s+({MONTH})"
            rf".{{0,100}}?SHOW\s*DAY\s*[-–:]\s*"
            rf"({DAY})\s+({MONTH})\s+(20\d{{2}})"
        )
        for match in re.finditer(pattern, text, re.I):
            a, am, b, bm, year = match.groups()
            try:
                start = make_date(a, am, year)
                end = make_date(b, bm, year)
                if 0 <= (end - start).days <= 7:
                    found.append((start, end))
            except ValueError:
                pass

    return sorted(set(found))


def canonical_venue(name):
    """Treat known alternative venue names as equivalent."""
    cleaned = re.sub(r"\s+", " ", name).strip().casefold()

    for canonical, aliases in VENUE_ALIASES.items():
        if cleaned in [alias.casefold() for alias in aliases]:
            return canonical

    return name.strip()


def expected_venue_present(show, text):
    aliases = VENUE_ALIASES.get(
        show["venue"], [show["venue"]]
    )
    lowered = text.casefold()
    return any(alias.casefold() in lowered for alias in aliases)


def extract_labeled_venue(show, text):
    """
    Identify a venue only from a clear organiser location label.
    Do not guess a venue from a town, map pin or general text.
    """
    kind = show["kind"]

    if kind == "reunion":
        pattern = (
            r"\bLOCATION\s+"
            r"(.{3,100}?)\s+"
            r"(?:Weston Road|Stafford|ST18\b)"
        )
        match = re.search(pattern, text, re.I)
        if match:
            return match.group(1).strip(" :-,")

    elif kind == "rollhard":
        pattern = (
            r"Where is Bicester Motion\?\s+"
            r"(.{3,100}?)\s*,\s*Buckingham Road"
        )
        match = re.search(pattern, text, re.I)
        if match:
            return match.group(1).strip(" :-,")

    return None


def verify_venue(show, text, start, end):
    """
    Return (venue, confidence).

    'known': expected venue appears on the page.
    'labeled': a clearly labeled venue was extracted.
    'confirmed-2027': previously confirmed Takeover edition.
    'unknown': no reliable venue evidence.
    """
    if expected_venue_present(show, text):
        return show["venue"], "known"

    extracted = extract_labeled_venue(show, text)
    if extracted:
        return canonical_venue(extracted), "labeled"

    if (
        show["kind"] == "takeover"
        and start == date(2027, 5, 15)
        and end == date(2027, 5, 16)
    ):
        return show["venue"], "confirmed-2027"

    return None, "unknown"


def make_event(show, start, end, venue):
    return {
        "name": f"{show['name']} {start.year}",
        "date": start.isoformat(),
        "end_date": end.isoformat(),
        "venue": venue,
        "region": show["region"],
        "category": "Modified Car Show",
        "organiser": show["name"],
        "official_url": show["url"],
        "status": "Listed by organiser",
    }


def main():
    today = datetime.now(ZoneInfo("Europe/London")).date()
    events = json.loads(FILE.read_text(encoding="utf-8"))

    if not isinstance(events, list):
        raise ValueError("manual-events.json must contain a list.")

    added = updated = existing = review = failed = 0

    print("PITLANE UK - AUTOMATIC DATE AND VENUE CHECKER")
    print(f"Today's UK date: {today}")

    for show in SHOWS:
        print(f"\n--- {show['name']} ---")

        try:
            page = fetch(show["url"])
        except Exception as error:
            failed += 1
            print(f"WEBSITE CHECK FAILED: {error}")
            continue

        candidates = [
            (start, end)
            for start, end in dates_for(show, page)
            if end >= today
        ]

        if not candidates:
            print("No complete upcoming date found.")
            continue

        by_year = {}
        for start, end in candidates:
            by_year.setdefault(start.year, set()).add((start, end))

        for year, ranges in sorted(by_year.items()):
            name = f"{show['name']} {year}"

            if len(ranges) != 1:
                review += 1
                print(f"REVIEW CONFLICTING DATES: {name}")
                continue

            start, end = next(iter(ranges))

            venue, confidence = verify_venue(
                show, page, start, end
            )

            if venue is None:
                review += 1
                print(f"REVIEW VENUE NOT VERIFIED: {name}")
                print(f"  Dates: {start} to {end}")
                continue

            matches = [
                event for event in events
                if event.get("name", "").strip().casefold()
                == name.casefold()
            ]

            if len(matches) > 1:
                review += 1
                print(f"REVIEW DUPLICATE EVENTS: {name}")
                continue

            # A newly extracted venue name is not automatically
            # trusted if it differs from the established venue.
            # It may be an address fragment or unrelated text.
            if canonical_venue(venue) != canonical_venue(show["venue"]):
                review += 1
                print(f"REVIEW POSSIBLE VENUE MOVE: {name}")
                print(f"  Previous venue: {show['venue']}")
                print(f"  Website suggests: {venue}")
                continue

            proposed = make_event(show, start, end, venue)

            if not matches:
                events.append(proposed)
                added += 1
                print(f"ADDED: {name} ({start} to {end})")
                continue

            current = matches[0]

            old_start = current.get("date")
            old_end = current.get("end_date") or old_start
            old_venue = current.get("venue", "")

            # Standardise known venue aliases automatically.
            # This is a naming correction, not a venue move.
            venue_changed = (
                canonical_venue(old_venue)
                != canonical_venue(proposed["venue"])
            )

            if venue_changed:
                review += 1
                print(f"REVIEW EXISTING VENUE: {name}")
                print(f"  Saved: {old_venue}")
                print(f"  Website: {proposed['venue']}")
                continue

            changed = False

            if (
                old_start != proposed["date"]
                or old_end != proposed["end_date"]
            ):
                print(f"DATE CHANGE DETECTED: {name}")
                print(f"  Old: {old_start} to {old_end}")
                print(
                    f"  New: {proposed['date']} "
                    f"to {proposed['end_date']}"
                )
                current["date"] = proposed["date"]
                current["end_date"] = proposed["end_date"]
                changed = True

            if old_venue != proposed["venue"]:
                current["venue"] = proposed["venue"]
                print(f"STANDARDISED VENUE: {name}")
                changed = True

            if changed:
                updated += 1
                print(f"UPDATED: {name}")
            else:
                existing += 1
                print(f"ALREADY LISTED: {name}")

    if added or updated:
        FILE.write_text(
            json.dumps(events, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    print("\n--- COMBINED IMPORT SUMMARY ---")
    print(f"Events added: {added}")
    print(f"Events updated: {updated}")
    print(f"Already listed: {existing}")
    print(f"Events needing review: {review}")
    print(f"Website checks failed: {failed}")
    print(f"Total manual events: {len(events)}")
    print("Automatic import check complete.")


if __name__ == "__main__":
    main()

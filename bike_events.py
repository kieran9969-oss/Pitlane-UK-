
#!/usr/bin/env python3
"""PITLANE UK - Automatic motorcycle event importer."""

import json
import re
import urllib.request
from datetime import date, datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
FILE = ROOT / "data/manual-events.json"

TODAY = datetime.now(
    ZoneInfo("Europe/London")
).date()

MONTHS = {
    name.lower(): number
    for number, name in enumerate(
        "Jan Feb Mar Apr May Jun Jul Aug "
        "Sep Oct Nov Dec".split(), 1
    )
}

MONTH = (
    r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|"
    r"Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
    r"Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|"
    r"Nov(?:ember)?|Dec(?:ember)?"
)

SOURCES = {
    "bsb": "https://www.britishsuperbike.com/calendar",
    "crmc": "https://www.crmc.co.uk/",
    "mcl": "https://www.motorcyclelive.co.uk/",
    "bemsee": (
        "https://www.bemsee.net/info-centre/"
        "bmcrc-provisional-dates-2027"
    ),
}

CIRCUITS = {
    "brands hatch": "Brands Hatch",
    "donington park": "Donington Park",
    "oulton park": "Oulton Park",
    "snetterton": "Snetterton",
    "knockhill": "Knockhill",
    "thruxton": "Thruxton",
    "cadwell park": "Cadwell Park",
    "anglesey": "Anglesey Circuit",
    "pembrey": "Pembrey Circuit",
    "mallory park": "Mallory Park",
    "croft": "Croft Circuit",
    "silverstone": "Silverstone",
    "lydden hill": "Lydden Hill",
    "darley moor": "Darley Moor",
}


class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.hidden += 1
        elif tag in (
            "p", "div", "li", "br",
            "h1", "h2", "h3", "h4", "tr"
        ):
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.hidden = max(0, self.hidden - 1)
        elif tag in (
            "p", "div", "li", "h1",
            "h2", "h3", "h4", "tr"
        ):
            self.parts.append(" ")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)

    def text(self):
        return re.sub(
            r"\s+", " ",
            unescape(" ".join(self.parts))
        ).strip()


def fetch(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 PITLANE-UK"
        }
    )

    with urllib.request.urlopen(
        request, timeout=25
    ) as response:
        raw = response.read(3_000_000)
        encoding = (
            response.headers.get_content_charset()
            or "utf-8"
        )

    parser = TextParser()
    parser.feed(
        raw.decode(encoding, errors="replace")
    )
    return parser.text()


def month_number(value):
    return MONTHS[value[:3].lower()]


def make_date(day, month, year):
    return date(
        int(year),
        month_number(month),
        int(day)
    )


def venue_from_text(text):
    lowered = text.lower()

    for key, venue in CIRCUITS.items():
        if key in lowered:
            return venue

    return None


def add_candidate(
    results, name, start, end,
    venue, category, organiser, url,
    status="Listed by organiser"
):
    if not start or not venue:
        return

    end = end or start

    if end < TODAY or end < start:
        return

    results.append({
        "name": name,
        "date": start.isoformat(),
        "end_date": end.isoformat(),
        "venue": venue,
        "region": "",
        "category": category,
        "organiser": organiser,
        "official_url": url,
        "status": status,
    })


# ---------------------------------------
# BRITISH SUPERBIKES
# ---------------------------------------

def import_bsb(text):
    results = []

    heading = re.search(
        r"\b(20\d{2})\s+Calendar\b",
        text, re.I
    )

    if not heading:
        print("BSB: calendar year not found")
        return results

    year = int(heading.group(1))

    pattern = (
        rf"\bRound\s+(\d{{1,2}})\s+"
        rf"(\d{{1,2}})\s*[-–]\s*"
        rf"(\d{{1,2}})\s+({MONTH})\b"
        rf"(.{{0,100}}?)"
        rf"(?=\b(?:Round\s+\d+|"
        rf"R&G Official Test|Event Details|"
        rf"Book Tickets)\b|$)"
    )

    for match in re.finditer(
        pattern, text, re.I
    ):
        round_no, first, last, month, area = (
            match.groups()
        )

        venue = venue_from_text(area)

        if not venue:
            continue

        try:
            start = make_date(first, month, year)
            end = make_date(last, month, year)
        except ValueError:
            continue

        add_candidate(
            results,
            f"British Superbikes Round {round_no} "
            f"{year} - {venue}",
            start, end, venue,
            "Bike racing",
            "British Superbike Championship",
            SOURCES["bsb"]
        )

    return results


# ---------------------------------------
# CLASSIC RACING MOTORCYCLE CLUB
# ---------------------------------------

def import_crmc(text):
    results = []

    pattern = (
        rf"\bRound\s+(\d{{1,2}})\s*:\s*"
        rf"(\d{{1,2}})\s*[-–]\s*"
        rf"(\d{{1,2}})\s+({MONTH})"
        rf"\s+(20\d{{2}})\s*[-–]\s*"
        rf"(.{{1,75}}?)"
        rf"(?=\bRound\s+\d+\s*:|$)"
    )

    for match in re.finditer(
        pattern, text, re.I
    ):
        (
            round_no, first, last,
            month, year, area
        ) = match.groups()

        venue = venue_from_text(area)

        if not venue:
            continue

        try:
            start = make_date(first, month, year)
            end = make_date(last, month, year)
        except ValueError:
            continue

        add_candidate(
            results,
            f"CRMC Classic Motorcycle Racing "
            f"Round {round_no} {year} - {venue}",
            start, end, venue,
            "Bike racing",
            "Classic Racing Motorcycle Club",
            SOURCES["crmc"]
        )

    return results


# ---------------------------------------
# MOTORCYCLE LIVE
# ---------------------------------------

def import_motorcycle_live(text):
    results = []

    pattern = (
        rf"\b(\d{{1,2}})\s*[-–]\s*"
        rf"(\d{{1,2}})\s+({MONTH})"
        rf"\s+(20\d{{2}})\b"
    )

    if not re.search(
        r"\b(?:NEC|National Exhibition Centre)\b",
        text, re.I
    ):
        return results

    for match in re.finditer(
        pattern, text, re.I
    ):
        first, last, month, year = (
            match.groups()
        )

        nearby = text[
            max(0, match.start() - 160):
            min(len(text), match.end() + 160)
        ]

        if not re.search(
            r"\b(?:MCL|Motorcycle Live)\b",
            nearby, re.I
        ):
            continue

        try:
            start = make_date(first, month, year)
            end = make_date(last, month, year)
        except ValueError:
            continue

        add_candidate(
            results,
            f"Motorcycle Live {year}",
            start, end,
            "NEC Birmingham",
            "Motorcycle Show",
            "Motorcycle Live",
            SOURCES["mcl"]
        )

    return results


# ---------------------------------------
# BEMSEE / BMCRC 2027
# ---------------------------------------

def import_bemsee(text):
    results = []
    year = 2027

    if not re.search(
        r"\b(?:BMCRC|Bemsee)\b",
        text, re.I
    ):
        print("Bemsee: organiser not found")
        return results

    circuit_pattern = (
        r"Oulton Park|Brands Hatch(?: Indy)?|"
        r"Donington Park(?: GP)?|"
        r"Snetterton(?: 300)?|Cadwell Park|"
        r"Anglesey|Mallory Park"
    )

    day_range = (
        r"(\d{1,2})(?:st|nd|rd|th)?"
        r"\s*[/–-]\s*"
        r"(\d{1,2})(?:st|nd|rd|th)?"
    )

    patterns = [
        (
            rf"\b({circuit_pattern})\s+"
            rf"{day_range}\s+({MONTH})\b",
            "venue_first"
        ),
        (
            rf"\b{day_range}\s+({MONTH})"
            rf"\s+({circuit_pattern})\b",
            "date_first"
        ),
    ]

    for pattern, order in patterns:
        for match in re.finditer(
            pattern, text, re.I
        ):
            if order == "venue_first":
                circuit, first, last, month = (
                    match.groups()
                )
            else:
                first, last, month, circuit = (
                    match.groups()
                )

            venue = venue_from_text(circuit)

            if not venue:
                continue

            try:
                start = make_date(
                    first, month, year
                )
                end = make_date(
                    last, month, year
                )
            except ValueError:
                continue

            add_candidate(
                results,
                f"Bemsee BMCRC {year} - {circuit}",
                start, end, venue,
                "Bike racing",
                "British Motorcycle Racing Club",
                SOURCES["bemsee"],
                "Provisional dates"
            )

    unique = []
    seen = set()

    for event in results:
        key = (
            event["date"],
            event["venue"].casefold()
        )

        if key not in seen:
            seen.add(key)
            unique.append(event)

    return unique


# ---------------------------------------
# DUPLICATE PROTECTION
# ---------------------------------------

def event_key(event):
    return (
        str(event.get("name", ""))
        .strip().casefold(),
        str(event.get("date", "")),
        str(event.get("venue", ""))
        .strip().casefold(),
    )


# ---------------------------------------
# MAIN IMPORTER
# ---------------------------------------

def main():
    print("PITLANE UK - MOTORCYCLE IMPORT")
    print("UK date:", TODAY)

    events = json.loads(
        FILE.read_text(encoding="utf-8")
    )

    if not isinstance(events, list):
        raise ValueError(
            "manual-events.json must be a list"
        )

    existing = {
        event_key(item)
        for item in events
        if isinstance(item, dict)
    }

    importers = [
        (
            "British Superbikes",
            "bsb",
            import_bsb
        ),
        (
            "Classic Racing",
            "crmc",
            import_crmc
        ),
        (
            "Motorcycle Live",
            "mcl",
            import_motorcycle_live
        ),
        (
            "Bemsee BMCRC",
            "bemsee",
            import_bemsee
        ),
    ]

    added = 0
    failures = 0

    for label, source, importer in importers:
        print()
        print("Checking:", label)

        try:
            text = fetch(SOURCES[source])

            # Diagnostic: show what GitHub receives
            # from Bemsee's website.
            if source == "bemsee":
                print(
                    "Bemsee page preview:",
                    repr(text[:500])
                )

            candidates = importer(text)

        except Exception as error:
            failures += 1
            print(
                "SOURCE ERROR:",
                str(error)[:200]
            )
            continue

        print(
            "Qualifying events:",
            len(candidates)
        )

        for event in candidates:
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
                event["date"]
            )

    if added:
        FILE.write_text(
            json.dumps(
                events,
                indent=2,
                ensure_ascii=False
            ) + "\n",
            encoding="utf-8"
        )

    print()
    print("BIKE IMPORT SUMMARY")
    print("Sources checked:", len(importers))
    print("Source failures:", failures)
    print("Events added:", added)
    print("Total manual events:", len(events))


if __name__ == "__main__":
    main()




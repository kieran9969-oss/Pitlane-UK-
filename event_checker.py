
#!/usr/bin/env python3
"""Check PITLANE UK event sources for possible announcements."""

import json
import re
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from html import unescape
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parent
SOURCES_FILE = ROOT / "modified-sources.json"

MONTHS = (
    "January February March April May June July August "
    "September October November December"
).split()

MONTH_PATTERN = "|".join(MONTHS)

DATE_PATTERNS = [
    re.compile(
        rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+"
        rf"(?:{MONTH_PATTERN})\s+20\d{{2}}\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\b(?:{MONTH_PATTERN})\s+"
        rf"\d{{1,2}}(?:st|nd|rd|th)?,?\s+20\d{{2}}\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b20\d{2}-\d{2}-\d{2}\b"
    ),
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

    def get_text(self):
        return " ".join(self.parts)


def fetch_text(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 PITLANE-UK-EventChecker"
        },
    )

    with urllib.request.urlopen(
        request, timeout=20
    ) as response:
        content = response.read(2_000_000)
        charset = response.headers.get_content_charset()
        html = content.decode(
            charset or "utf-8",
            errors="replace",
        )

    parser = TextExtractor()
    parser.feed(html)

    return unescape(parser.get_text())


def find_dates(text, current_year):
    matches = set()

    for pattern in DATE_PATTERNS:
        for match in pattern.finditer(text):
            value = match.group(0)
            years = re.findall(r"\b20\d{2}\b", value)

            if years and int(years[-1]) >= current_year:
                matches.add(value)

    return sorted(matches)


def main():
    today = datetime.now(
        ZoneInfo("Europe/London")
    ).date()

    data = json.loads(
        SOURCES_FILE.read_text(encoding="utf-8")
    )
    sources = data["sources"]

    print("PITLANE UK - EVENT ANNOUNCEMENT CHECKER")
    print(f"Today's UK date: {today}")
    print(f"Sources configured: {len(sources)}")

    checked = 0
    failed = 0
    possible_dates = 0

    for source in sources:
        name = source["name"]
        url = source["url"]

        print(f"\n--- {name} ---")
        print(f"Website: {url}")

        try:
            text = fetch_text(url)
            dates = find_dates(text, today.year)
            checked += 1

            if dates:
                print("POSSIBLE DATE ANNOUNCEMENTS:")
                for value in dates[:20]:
                    print(f"  REVIEW: {value}")
                possible_dates += len(dates)
            else:
                print("No future date patterns detected.")

        except Exception as error:
            failed += 1
            print(f"CHECK FAILED: {error}")

    print("\n--- CHECKER SUMMARY ---")
    print(f"Sources checked successfully: {checked}")
    print(f"Sources failed: {failed}")
    print(f"Possible dates found: {possible_dates}")
    print("Review dates against official event announcements.")
    print("No calendar events were changed.")


if __name__ == "__main__":
    main()

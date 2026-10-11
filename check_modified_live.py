

#!/usr/bin/env python3
"""Test official Modified Live event pages without changing data."""

import re
import urllib.request
from html import unescape
from html.parser import HTMLParser

SOURCES = [
    (
        "Modified Live",
        "https://modifiedlive.co.uk/",
    ),
    (
        "Modified Live Cadwell Park",
        "https://cadwell.modifiedlive.co.uk/",
    ),
    (
        "Modified Live Snetterton",
        "https://snetterton.modifiedlive.co.uk/",
    ),
    (
        "Modified Live Castle Combe",
        "https://castlecombe.modifiedlive.co.uk/",
    ),
]

MONTHS = (
    "January|February|March|April|May|June|"
    "July|August|September|October|November|December"
)

DATE_PATTERN = re.compile(
    rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+"
    rf"(?:{MONTHS})\s+20\d{{2}}\b",
    re.IGNORECASE,
)


class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def download(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 PITLANE-UK/1.0"
        },
    )

    with urllib.request.urlopen(
        request, timeout=30
    ) as response:
        return response.read(2_000_000).decode(
            "utf-8", errors="replace"
        )


def check_source(name, url):
    print(f"\nChecking: {name}")
    print(f"URL: {url}")

    try:
        html = download(url)
    except Exception as error:
        print(f"FAILED: {error}")
        return

    parser = TextParser()
    parser.feed(html)

    text = unescape(" ".join(parser.parts))
    text = " ".join(text.split())

    dates = sorted(set(
        match.group(0)
        for match in DATE_PATTERN.finditer(text)
    ))

    if not dates:
        print("No full dates detected.")
        return

    print(f"Full dates detected: {len(dates)}")

    for event_date in dates[:20]:
        print(f"DATE: {event_date}")


def main():
    print("PITLANE UK - MODIFIED LIVE TEST")

    for name, url in SOURCES:
        check_source(name, url)

    print("\n--- TEST COMPLETE ---")
    print("No calendar files were changed.")


if __name__ == "__main__":
    main()

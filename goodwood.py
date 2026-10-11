
#!/usr/bin/env python3
"""Discover future Goodwood dates without changing events."""

import re
import urllib.request
from datetime import date

PAGES = {
    "Festival of Speed": "https://www.goodwood.com/motorsport/festival-of-speed/",
    "Goodwood Revival": "https://www.goodwood.com/motorsport/goodwood-revival/",
    "Members' Meeting": "https://www.goodwood.com/motorsport/members-meeting/",
}

MONTHS = (
    "January|February|March|April|May|June|July|"
    "August|September|October|November|December"
)

PATTERN = re.compile(
    rf"\b(\d{{1,2}})\s*[-–]\s*(\d{{1,2}})"
    rf"\s+({MONTHS})\s+(20\d{{2}})\b",
    re.IGNORECASE,
)

for name, url in PAGES.items():
    print(f"\nChecking {name}")

    try:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 PITLANE-UK/1.0"},
        )

        with urllib.request.urlopen(request, timeout=25) as response:
            html = response.read(2_000_000).decode(
                "utf-8", errors="replace"
            )

        # Look for future-year date ranges.
        found = set()

        for first, last, month, year in PATTERN.findall(html):
            if int(year) < 2027:
                continue

            found.add(
                f"{first}-{last} {month} {year}"
            )

        if found:
            for result in sorted(found):
                print("Possible future event dates:", result)
        else:
            print("No future dates found in this format.")

    except Exception as error:
        print("Check failed:", error)

print("\nFuture-year discovery test complete.")
print("No event files were changed.")


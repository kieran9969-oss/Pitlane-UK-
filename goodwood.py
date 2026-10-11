
#!/usr/bin/env python3
"""Test access to Goodwood's official motorsport event pages."""

import urllib.request
import re

PAGES = {
    "Festival of Speed": "https://www.goodwood.com/motorsport/festival-of-speed/",
    "Goodwood Revival": "https://www.goodwood.com/motorsport/goodwood-revival/",
    "Members' Meeting": "https://www.goodwood.com/motorsport/members-meeting/",
}

for name, url in PAGES.items():
    print(f"\nChecking {name}...")

    try:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 PITLANE-UK/1.0"}
        )

        with urllib.request.urlopen(request, timeout=20) as response:
            html = response.read(2_000_000).decode(
                "utf-8", errors="replace"
            )

        print("Page downloaded successfully")
        print(f"Page size: {len(html)} characters")

        dates = sorted(set(re.findall(
            r"20(?:26|27|28)-\d{2}-\d{2}",
            html
        )))

        if dates:
            print("Possible dates found:", ", ".join(dates[:20]))
        else:
            print("No ISO-format dates found")

    except Exception as error:
        print(f"Could not check page: {error}")

print("\nGoodwood test finished.")


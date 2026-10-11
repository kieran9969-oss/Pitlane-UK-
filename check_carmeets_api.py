
#!/usr/bin/env python3
"""Test Carmeets UK calendar API without changing events."""

import json
import urllib.request

BASE_URL = (
    "https://carmeetsuk.com/"
    "wp-json/tribe/events/v1/events"
)


def main():
    total = 0

    for page in range(1, 6):
        url = (
            f"{BASE_URL}?per_page=50&page={page}"
        )

        print(f"\nChecking API page {page}")

        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 PITLANE-UK/1.0",
                "Accept": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(
                request, timeout=25
            ) as response:
                data = json.load(response)

        except Exception as error:
            print(f"API request failed: {error}")
            break

        events = data.get("events", [])

        print(f"Events on page: {len(events)}")
        print(
            f"Total pages reported: "
            f"{data.get('total_pages', 'Unknown')}"
        )

        for event in events[:5]:
            print(
                f"EVENT: {event.get('title', 'Unknown')}"
            )
            print(
                f"DATE: {event.get('start_date', 'Unknown')}"
            )

        total += len(events)

        if not events:
            break

        total_pages = data.get("total_pages")

        if total_pages is not None:
            try:
                if page >= int(total_pages):
                    break
            except (ValueError, TypeError):
                pass

    print("\n--- API TEST SUMMARY ---")
    print(f"Total events retrieved: {total}")
    print("No calendar files were changed.")


if __name__ == "__main__":
    main()


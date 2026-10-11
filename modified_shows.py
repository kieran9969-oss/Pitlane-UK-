
#!/usr/bin/env python3
"""Check PITLANE UK modified car show websites."""

import json
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
SOURCES_FILE = BASE / "modified-sources.json"


def main():
    data = json.loads(SOURCES_FILE.read_text(encoding="utf-8"))
    sources = data["sources"]

    print(f"Loaded {len(sources)} modified car show sources.")

    for source in sources:
        name = source["name"]
        url = source.get("url", "").strip()

        if not url:
            print(f"Skipping {name}: no website configured.")
            continue

        try:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 PITLANE-UK/1.0"},
            )

            with urllib.request.urlopen(
                request, timeout=20
            ) as response:
                html = response.read(1_000_000)

            print(
                f"Checked {name}: received {len(html)} bytes"
            )

        except Exception as error:
            print(f"Could not check {name}: {error}")

    print("Modified car show website check complete.")


if __name__ == "__main__":
    main()



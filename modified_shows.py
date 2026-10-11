
#!/usr/bin/env python3
"""Check PITLANE UK modified car show sources."""

import json
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

        print(f"Ready to check: {name} — {url}")

    print("Modified car show source check complete.")


if __name__ == "__main__":
    main()


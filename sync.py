
#!/usr/bin/env python3
"""PITLANE UK event feed aggregator."""

import hashlib
import json
import re
import urllib.request

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parent
CONFIG = json.loads(
    (ROOT / "sources.json").read_text(
        encoding="utf-8"
    )
)

TODAY = datetime.now(
    ZoneInfo("Europe/London")
).date()


def unfold(text):
    return re.sub(r"\r?\n[ \t]", "", text)


def unescape(text):
    return (
        text.replace("\\n", " ")
        .replace("\\,", ",")
        .replace("\\;", ";")
        .replace("\\\\", "\\")
    )


def parse_ics_date(value):
    value = str(value or "").strip()

    if re.match(r"^\d{8}", value):
        try:
            return date(
                int(value[:4]),
                int(value[4:6]),
                int(value[6:8]),
            )
        except ValueError:
            return None

    return None


def parse_json_date(value):
    try:
        return date.fromisoformat(
            str(value)[:10]
        )
    except (ValueError, TypeError):
        return None


def format_date(value):
    return value.isoformat() if value else ""


def read_ics(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "PITLANE-UK/1.0 "
                "(event calendar sync)"
            )
        },
    )

    with urllib.request.urlopen(
        request, timeout=25
    ) as response:
        raw = response.read(5_000_000).decode(
            "utf-8-sig", "replace"
        )

    if "BEGIN:VCALENDAR" not in raw:
        raise ValueError("Not an iCalendar feed")

    blocks = unfold(raw).split(
        "BEGIN:VEVENT"
    )[1:]

    for block in blocks:
        content = block.split(
            "END:VEVENT", 1
        )[0]

        fields = {}

        for line in content.splitlines():
            if ":" not in line:
                continue

            key, value = line.split(":", 1)

            fields[
                key.split(";")[0].upper()
            ] = unescape(value.strip())

        yield fields


def clean(text):
    return re.sub(
        r"[^a-z0-9]+",
        " ",
        str(text).lower(),
    ).strip()


def category(text):
    text = text.lower()

    rules = [
        (
            "Bike racing",
            [
                "motorcycle",
                "superbike",
                "motocross",
                "bike race",
                "bike racing",
            ],
        ),
        ("Drifting", ["drift"]),
        (
            "Drag racing",
            ["drag racing", "drag strip"],
        ),
        (
            "Rallying",
            [
                "rally",
                "hillclimb",
                "hill climb",
                "sprint",
            ],
        ),
        (
            "Modified show",
            [
                "modified",
                "tuner",
                "stance",
                "jdm",
                "custom car",
            ],
        ),
        (
            "Classic cars",
            [
                "classic",
                "vintage",
                "historic show",
            ],
        ),
        (
            "Car meet",
            [
                "car meet",
                "cars and coffee",
                "car show",
            ],
        ),
        (
            "Circuit racing",
            [
                "race",
                "racing",
                "circuit",
                "touring",
                "gt championship",
            ],
        ),
    ]

    for name, words in rules:
        if any(word in text for word in words):
            return name

    return "Other motorsport"


def event_key(name, start, venue):
    return "|".join(
        (
            clean(name),
            start,
            clean(venue),
        )
    )


def is_upcoming(start, end=None):
    if start is None:
        return False

    last_day = end or start
    return last_day >= TODAY


def sync():
    checked = datetime.now(
        timezone.utc
    ).isoformat(timespec="seconds")

    output = []
    errors = []
    seen = {}

    print("PITLANE UK - EVENT SYNC")
    print(f"Today's UK date: {TODAY}")

    for source in CONFIG["sources"]:
        if not source.get("enabled", False):
            continue

        try:
            if source["type"] != "ics":
                raise ValueError(
                    "Unsupported source type"
                )

            for item in read_ics(source["url"]):
                name = item.get(
                    "SUMMARY", ""
                ).strip()

                start = parse_ics_date(
                    item.get("DTSTART", "")
                )

                end = parse_ics_date(
                    item.get("DTEND", "")
                )

                # iCalendar DTEND is exclusive.
                # An event ending at midnight on
                # the next day finishes the day before.
                if end and start and end > start:
                    end = end - timedelta(days=1)

                if not name or not is_upcoming(
                    start, end
                ):
                    continue

                start_text = format_date(start)
                end_text = format_date(end)

                venue = item.get(
                    "LOCATION", ""
                ).strip()

                link = (
                    item.get("URL", "").strip()
                    or source.get("website", "")
                )

                key = event_key(
                    name,
                    start_text,
                    venue,
                )

                record = {
                    "id": hashlib.sha256(
                        key.encode()
                    ).hexdigest()[:16],
                    "name": name,
                    "date": start_text,
                    "end_date": end_text,
                    "venue": venue,
                    "region": "",
                    "category": category(
                        name
                        + " "
                        + item.get(
                            "DESCRIPTION", ""
                        )
                    ),
                    "organiser": source["name"],
                    "status": "Unverified",
                    "official_url": link,
                    "ticket_url": "",
                    "source_names": [
                        source["name"]
                    ],
                    "source_urls": [
                        source["url"]
                    ],
                    "last_checked": checked,
                    "description": item.get(
                        "DESCRIPTION", ""
                    )[:400],
                }

                if key in seen:
                    old = seen[key]
                    old["source_names"].append(
                        source["name"]
                    )
                    old["source_urls"].append(
                        source["url"]
                    )

                    if (
                        not old["official_url"]
                        and link
                    ):
                        old["official_url"] = link

                else:
                    seen[key] = record
                    output.append(record)

        except Exception as error:
            errors.append({
                "source": source["name"],
                "error": str(error)[:200],
            })

    # Include manually maintained and
    # automatically imported events.
    manual_file = (
        ROOT / "data/manual-events.json"
    )

    if manual_file.exists():
        manual_events = json.loads(
            manual_file.read_text(
                encoding="utf-8"
            )
        )

        if not isinstance(manual_events, list):
            raise ValueError(
                "manual-events.json must be a list"
            )

        for event in manual_events:
            if not all(
                event.get(key)
                for key in (
                    "name",
                    "date",
                    "venue",
                    "official_url",
                )
            ):
                continue

            start = parse_json_date(
                event.get("date")
            )

            end = parse_json_date(
                event.get("end_date")
            )

            if not is_upcoming(start, end):
                continue

            key = event_key(
                event["name"],
                event["date"],
                event["venue"],
            )

            if key in seen:
                continue

            event.setdefault(
                "id",
                hashlib.sha256(
                    key.encode()
                ).hexdigest()[:16],
            )

            event.setdefault(
                "last_checked", checked
            )

            event.setdefault(
                "status", "Unverified"
            )

            event.setdefault(
                "source_names",
                ["Manual review"],
            )

            output.append(event)
            seen[key] = event

    # Preserve events during temporary feed
    # failures, but never preserve past events.
    target = ROOT / "data/events.json"

    if errors and target.exists():
        previous = json.loads(
            target.read_text(
                encoding="utf-8"
            )
        ).get("events", [])

        existing_ids = {
            event["id"]
            for event in output
        }

        for event in previous:
            start = parse_json_date(
                event.get("date")
            )

            end = parse_json_date(
                event.get("end_date")
            )

            if not is_upcoming(start, end):
                continue

            if event.get("id") in existing_ids:
                continue

            event["status"] = (
                "Stale — recheck source"
            )

            output.append(event)
            existing_ids.add(
                event.get("id")
            )

    output.sort(
        key=lambda event: (
            event.get("date", ""),
            event.get("name", ""),
        )
    )

    target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    target.write_text(
        json.dumps(
            {
                "generated_at": checked,
                "event_count": len(output),
                "source_errors": errors,
                "events": output,
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    print(
        f"Published {len(output)} upcoming events"
    )

    print(
        f"Feed errors: {len(errors)}"
    )

    for error in errors:
        print(
            "ERROR",
            error["source"],
            error["error"],
        )

    print("Expired events excluded.")


if __name__ == "__main__":
    sync()

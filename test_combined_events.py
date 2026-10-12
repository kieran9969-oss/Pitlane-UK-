
#!/usr/bin/env python3
"""Safe tests for PITLANE UK's combined event importer."""

from datetime import date

from combined_events import (
    canonical_venue,
    dates_for,
    verify_venue,
)


def check(description, actual, expected):
    if actual != expected:
        raise AssertionError(
            f"FAIL: {description}\n"
            f"Expected: {expected!r}\n"
            f"Actual: {actual!r}"
        )
    print(f"PASS: {description}")


def main():
    print("PITLANE UK - SAFE IMPORTER TESTS")
    print("No live calendar files will be changed.\n")

    reunion = {
        "name": "The Reunion Show",
        "kind": "reunion",
        "venue": "Staffordshire Showground",
    }

    # TEST 1: An organiser announces a different date.
    # This tests date extraction, not a real announcement.
    page = (
        "The Reunion Show "
        "18th July 2027 "
        "LOCATION Staffordshire Showground "
        "Weston Road Stafford ST18 0BD"
    )

    dates = dates_for(reunion, page)

    check(
        "Recognises a changed event date",
        dates,
        [(date(2027, 7, 18), date(2027, 7, 18))],
    )

    venue, confidence = verify_venue(
        reunion,
        page,
        date(2027, 7, 18),
        date(2027, 7, 18),
    )

    check(
        "Recognises the established venue",
        venue,
        "Staffordshire Showground",
    )

    # TEST 2: Two names refer to the same venue.
    check(
        "Recognises Isle of Wight venue aliases",
        canonical_venue(
            "Royal Isle of Wight Agricultural Society "
            "County Show Ground"
        ),
        "Royal Isle of Wight County Showground",
    )

    check(
        "Recognises Bicester venue aliases",
        canonical_venue("Bicester Motion"),
        "Bicester Heritage",
    )

    # TEST 3: A completely different venue is announced.
    # This is invented test data, NOT a real venue move.
    moved_page = (
        "The Reunion Show "
        "18th July 2027 "
        "LOCATION Example Events Park "
        "Weston Road Stafford ST18 0BD"
    )

    moved_venue, moved_confidence = verify_venue(
        reunion,
        moved_page,
        date(2027, 7, 18),
        date(2027, 7, 18),
    )

    check(
        "Extracts a possible new venue",
        moved_venue,
        "Example Events Park",
    )

    check(
        "Marks the possible move for review",
        moved_confidence,
        "labeled",
    )

    check(
        "Does not confuse a new venue with the old one",
        canonical_venue(moved_venue)
        != canonical_venue(reunion["venue"]),
        True,
    )

    print("\nALL TESTS PASSED")
    print("The real event calendar was not modified.")


if __name__ == "__main__":
    main()

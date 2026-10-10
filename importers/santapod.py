
"""Santa Pod event importer for PITLANE UK."""

from urllib.request import Request, urlopen


def check_website():
    url = "https://santapod.co.uk/events/"

    request = Request(
        url,
        headers={"User-Agent": "PITLANE-UK/1.0"}
    )

    with urlopen(request, timeout=20) as response:
        html = response.read().decode(
            "utf-8", errors="replace"
        )

    print("Santa Pod website accessible")
    print("Downloaded characters:", len(html))
    print("Response preview:", repr(html[:500]))


if __name__ == "__main__":
    check_website()


"""Santa Pod event importer for PITLANE UK."""

from urllib.request import Request, urlopen
import re


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

    print("Security challenge detected:", "/.well-known/sgcaptcha/" in html)

    print("Santa Pod website accessible")
    print("Downloaded characters:", len(html))
    print("Response preview:", repr(html[:500]))
    print("Event structured data present:", "application/ld+json" in html)
    print("HTML date tags found:", html.count("<time"))
    print("Event schema found:", '"@type":"Event"' in html or '"@type": "Event"' in html)
    types = re.findall(r'"@type"\s*:\s*"([^"]+)"', html)
    print("Structured data types:", sorted(set(types))[:20])

if __name__ == "__main__":
    check_website()

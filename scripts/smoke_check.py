import http.cookiejar
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def get(url: str) -> None:
    try:
        with urllib.request.urlopen(url, timeout=8) as r:
            body = r.read().decode().replace("\n", " ")[:240]
            print(r.status, url, body)
    except Exception as exc:
        print("FAIL", url, exc)


def main() -> None:
    get("http://127.0.0.1:5000/health")
    get("http://127.0.0.1:8000/health/")
    get("http://127.0.0.1:5678/healthz")

    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    login_page = opener.open("http://127.0.0.1:8000/login/").read().decode()
    token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', login_page).group(1)
    password = os.environ.get("DJANGO_ADMIN_PASSWORD", "DemoAdmin123!")
    data = urllib.parse.urlencode(
        {"username": "admin", "password": password, "csrfmiddlewaretoken": token}
    ).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:8000/login/",
        data=data,
        headers={"Referer": "http://127.0.0.1:8000/login/"},
    )
    opener.open(req)
    dash = opener.open("http://127.0.0.1:8000/dashboard/").read().decode()
    inbox = opener.open("http://127.0.0.1:8000/inbox/").read().decode()
    spam = opener.open("http://127.0.0.1:8000/spam/").read().decode()
    human = opener.open("http://127.0.0.1:8000/human-queue/").read().decode()
    print("northline", "northline" in (dash + inbox).lower())
    print("harbor", "harbor" in human.lower())
    print("spam", "prize" in spam.lower() or "crypto" in spam.lower())
    print("peak", "peak" in inbox.lower())


if __name__ == "__main__":
    main()

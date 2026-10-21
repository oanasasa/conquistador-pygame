"""Questions from the Open Trivia Database (opentdb.com), fetched live.

The host downloads questions for the category and difficulty chosen when the
room is created: one category, or all of them mixed. They are kept in memory
only, never written to disk. Questions are licensed CC BY-SA 4.0 (credit:
Open Trivia Database).
"""
import base64
import json
import os
import ssl
import time
import urllib.parse
import urllib.request

API = "https://opentdb.com/api.php"
ALL = "All categories"
# OpenTDB category ids, with their "Entertainment:" / "Science:" prefixes dropped.
CATEGORIES = {
    "General Knowledge": 9, "Books": 10, "Film": 11, "Music": 12,
    "Musicals & Theatres": 13, "Television": 14, "Video Games": 15, "Board Games": 16,
    "Science & Nature": 17, "Computers": 18, "Mathematics": 19, "Mythology": 20,
    "Sports": 21, "Geography": 22, "History": 23, "Politics": 24, "Art": 25,
    "Celebrities": 26, "Animals": 27, "Vehicles": 28, "Comics": 29, "Gadgets": 30,
    "Anime & Manga": 31, "Cartoons & Animations": 32,
}
CHOICES = [ALL] + sorted(CATEGORIES)
DIFFICULTIES = ["any", "easy", "medium", "hard"]
REQUEST_GAP = 5.2          # OpenTDB allows one request per 5 seconds per IP
AMOUNT = 50                # the API's maximum per request
MAX_REQUESTS = 8           # give up after this many, whatever the replies


def _decode(s):
    return base64.b64decode(s).decode("utf-8").strip()


def clean_category(name):
    """'Entertainment: Video Games' -> 'Video Games'."""
    name = name.removeprefix("Entertainment: ").removeprefix("Science: ")
    return {"Japanese Anime & Manga": "Anime & Manga",
            "Cartoon & Animations": "Cartoons & Animations"}.get(name, name)


def convert(item, rng):
    """One base64-encoded OpenTDB result -> our question format, or None.
    Only multiple-choice questions are used; all four answers are kept."""
    if _decode(item["type"]) != "multiple":
        return None
    correct = _decode(item["correct_answer"])
    choices = [_decode(w) for w in item["incorrect_answers"]] + [correct]
    if len(choices) != 4 or len(set(choices)) != 4:
        return None
    rng.shuffle(choices)
    return {"q": _decode(item["question"]), "choices": choices, "answer": choices.index(correct),
            "category": clean_category(_decode(item["category"])),
            "difficulty": _decode(item["difficulty"]), "source": "opentdb"}


def _ssl_context():
    """Verified HTTPS. python.org's macOS Python has no CA bundle until its
    'Install Certificates' step is run, so fall back to the system bundle."""
    paths = ssl.get_default_verify_paths()
    if paths.cafile and os.path.exists(paths.cafile):
        return ssl.create_default_context()
    for cafile in ("/etc/ssl/cert.pem", "/etc/ssl/certs/ca-certificates.crt"):
        if os.path.exists(cafile):
            return ssl.create_default_context(cafile=cafile)
    return ssl.create_default_context()


def http_get(params):
    url = f"{API}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "conquistador-game"})
    with urllib.request.urlopen(req, timeout=15, context=_ssl_context()) as resp:
        return json.load(resp)


def fetch(category, difficulty, rng, on_batch, get=http_get, sleep=time.sleep,
          should_stop=lambda: False):
    """Download one batch of questions for `category` (a name from CATEGORIES,
    or ALL for every category mixed) and pass it to `on_batch(questions)`.
    If the category has fewer questions than asked for, asks for fewer.
    Returns the number fetched. Raises OSError if offline."""
    params = {"amount": AMOUNT, "type": "multiple", "encode": "base64"}
    if category != ALL:
        params["category"] = CATEGORIES[category]
    if difficulty != "any":
        params["difficulty"] = difficulty
    for attempt in range(MAX_REQUESTS):
        if attempt:
            sleep(REQUEST_GAP)              # the API's rate limit, retries included
        if should_stop() or params["amount"] < 1:
            return 0
        data = get(params)
        code = data.get("response_code")
        if code == 0:
            batch = [q for q in (convert(item, rng) for item in data["results"]) if q]
            on_batch(batch)
            return len(batch)
        if code == 1:                      # fewer questions exist than asked for
            params["amount"] //= 2
        elif code != 5:                    # 5 = rate limited: wait and retry
            return 0
    return 0

"""Questions from the Open Trivia Database (opentdb.com), fetched live.

The host downloads questions for the categories and difficulty chosen when the
room is created. They are kept in memory only, never written to disk.
Questions are licensed CC BY-SA 4.0 (credit: Open Trivia Database).
"""
import base64
import json
import os
import ssl
import time
import urllib.parse
import urllib.request

API = "https://opentdb.com/api.php"
CATEGORIES = {"History": 23, "Art": 25, "Mythology": 20}
DIFFICULTIES = ["any", "easy", "medium", "hard"]
REQUEST_GAP = 5.2          # OpenTDB allows one request per 5 seconds per IP
PER_CATEGORY = 50          # the API's maximum per request
MAX_REQUESTS = 20          # give up after this many, whatever the replies


def _decode(s):
    return base64.b64decode(s).decode("utf-8").strip()


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
            "category": _decode(item["category"]), "difficulty": _decode(item["difficulty"]),
            "source": "opentdb"}


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


def fetch(categories, difficulty, rng, on_batch, get=http_get, sleep=time.sleep,
          should_stop=lambda: False):
    """Download questions category by category, calling `on_batch(category,
    questions)` as each arrives so the game can start before all are in.
    Returns the number of questions fetched. Raises OSError if offline."""
    total, requests = 0, 0
    for name in categories:
        params = {"amount": PER_CATEGORY, "category": CATEGORIES[name], "type": "multiple",
                  "encode": "base64"}
        if difficulty != "any":
            params["difficulty"] = difficulty
        while params["amount"] > 0:
            if requests:
                sleep(REQUEST_GAP)          # wait between all requests, retries included
            if should_stop() or requests >= MAX_REQUESTS:
                return total
            requests += 1
            data = get(params)
            code = data.get("response_code")
            if code == 0:
                batch = [q for q in (convert(item, rng) for item in data["results"]) if q]
                total += len(batch)
                on_batch(name, batch)
                break
            if code == 1:              # fewer questions exist than asked for: ask for fewer
                params["amount"] //= 2
            elif code == 5:            # rate limited: wait and retry
                continue
            else:
                break
    return total

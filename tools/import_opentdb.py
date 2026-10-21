"""Import trivia questions from the Open Trivia Database into data/questions.json.

Run by a developer (the game itself never goes online):

    python tools/import_opentdb.py              # History, Art and Mythology
    python tools/import_opentdb.py --per-category 60

Questions come from https://opentdb.com and are licensed CC BY-SA 4.0
(credit: Open Trivia Database). Only multiple-choice questions are imported.
Each is stored with all four answers shuffled, "source": "opentdb", and
"reviewed": true (the owner treats OpenTDB as a trusted, human-curated
source; set "reviewed": false on any question to keep it out of games).

Questions already in the file are kept; previously imported OpenTDB
questions are replaced by the fresh download. The script prints only
counts, never questions or answers.
"""
import argparse
import base64
import json
import os
import random
import ssl
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

QUESTIONS_PATH = Path(__file__).resolve().parent.parent / "data" / "questions.json"
API = "https://opentdb.com"
CATEGORIES = {"History": 23, "Art": 25, "Mythology": 20}
REQUEST_GAP = 5.5          # OpenTDB allows one request per 5 seconds per IP
BATCH = 50                 # the API's maximum per request


def _decode(s):
    return base64.b64decode(s).decode("utf-8").strip()


def convert(item, rng):
    """One base64-encoded OpenTDB result -> our question format, or None."""
    if _decode(item["type"]) != "multiple":
        return None
    correct = _decode(item["correct_answer"])
    wrong = [_decode(w) for w in item["incorrect_answers"]]
    choices = wrong + [correct]
    if len(choices) != 4 or len(set(choices)) != 4:
        return None
    rng.shuffle(choices)
    return {
        "q": _decode(item["question"]),
        "choices": choices,
        "answer": choices.index(correct),
        "category": _decode(item["category"]),
        "difficulty": _decode(item["difficulty"]),
        "source": "opentdb",
        "reviewed": True,
    }


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


def _get(path, params):
    url = f"{API}/{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "conquistador-question-import"})
    with urllib.request.urlopen(req, timeout=20, context=_ssl_context()) as resp:
        return json.load(resp)


def fetch_category(category_id, wanted, token):
    """Download up to `wanted` multiple-choice questions from one category."""
    results, amount = [], min(BATCH, wanted)
    while len(results) < wanted and amount > 0:
        time.sleep(REQUEST_GAP)
        data = _get("api.php", {"amount": amount, "category": category_id, "type": "multiple",
                                "encode": "base64", "token": token})
        code = data.get("response_code")
        if code == 0:
            results += data["results"]
            amount = min(BATCH, wanted - len(results))
        elif code == 1:            # fewer questions left than asked for: ask for fewer
            amount //= 2
        elif code == 5:            # rate limited: wait and retry
            time.sleep(REQUEST_GAP)
        else:                      # 4: this session has seen every question
            break
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--per-category", type=int, default=50,
                        help="questions to fetch per category (default 50)")
    parser.add_argument("--seed", type=int, default=None, help="shuffle seed, for repeatable files")
    args = parser.parse_args()
    rng = random.Random(args.seed)

    token = _get("api_token.php", {"command": "request"})["token"]
    imported = []
    for name, cid in CATEGORIES.items():
        raw = fetch_category(cid, args.per_category, token)
        converted = [q for q in (convert(item, rng) for item in raw) if q]
        imported += converted
        print(f"{name}: {len(converted)} questions")

    existing = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
    own = [q for q in existing if q.get("source") != "opentdb"]
    seen = {q["q"] for q in own}
    fresh = []
    for q in imported:
        if q["q"] not in seen:
            seen.add(q["q"])
            fresh.append(q)
    QUESTIONS_PATH.write_text(json.dumps(own + fresh, ensure_ascii=False, indent=2) + "\n",
                              encoding="utf-8")
    print(f"wrote {QUESTIONS_PATH.name}: {len(own)} own + {len(fresh)} from OpenTDB")


if __name__ == "__main__":
    sys.exit(main())

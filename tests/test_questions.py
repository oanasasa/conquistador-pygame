"""Question bank, live OpenTDB fetching (with fake replies; tests never go
online) and the deck. Never prints answers."""
import base64
import random
import time

from game.opening import OpeningPhase
from game.questions import QuestionDeck, load_questions, public_view
from net import opentdb
from net.client import GameClient
from net.server import GameServer


def b64(s):
    return base64.b64encode(s.encode("utf-8")).decode("ascii")


def fake_item(n=0, qtype="multiple", category="Mythology"):
    return {"type": b64(qtype), "difficulty": b64("easy"), "category": b64(category),
            "question": b64(f"Question {n}?"), "correct_answer": b64(f"right {n}"),
            "incorrect_answers": [b64(f"w{n}a"), b64(f"w{n}b"), b64(f"w{n}c")]}


# ---- converting -------------------------------------------------------------

def test_convert_keeps_four_shuffled_choices_and_marks_the_source():
    q = opentdb.convert(fake_item(), random.Random(1))
    assert len(q["choices"]) == 4 and q["choices"][q["answer"]] == "right 0"
    assert q["source"] == "opentdb" and q["category"] == "Mythology"


def test_convert_skips_true_false():
    assert opentdb.convert(fake_item(qtype="boolean"), random.Random(1)) is None


def test_public_view_has_category_but_never_the_answer():
    view = public_view(opentdb.convert(fake_item(), random.Random(1)))
    assert "answer" not in view and view["category"] == "Mythology"


# ---- fetching ---------------------------------------------------------------

def test_fetch_one_request_per_category_with_difficulty_and_rate_limit():
    calls, sleeps, batches = [], [], []

    def get(params):
        calls.append(dict(params))
        return {"response_code": 0, "results": [fake_item(i) for i in range(3)]}

    total = opentdb.fetch(["History", "Art"], "hard", random.Random(1),
                          lambda name, b: batches.append((name, len(b))), get=get,
                          sleep=sleeps.append)
    assert total == 6 and batches == [("History", 3), ("Art", 3)]
    assert [c["category"] for c in calls] == [23, 25]
    assert all(c["difficulty"] == "hard" and c["type"] == "multiple" for c in calls)
    assert sleeps == [opentdb.REQUEST_GAP]          # waits between requests, not before the first


def test_fetch_any_difficulty_sends_no_filter_and_asks_for_fewer_when_short():
    calls = []

    def get(params):
        calls.append(dict(params))
        if params["amount"] > 12:
            return {"response_code": 1, "results": []}
        return {"response_code": 0, "results": [fake_item(i) for i in range(params["amount"])]}

    total = opentdb.fetch(["Art"], "any", random.Random(1), lambda *_: None, get=get,
                          sleep=lambda _: None)
    assert "difficulty" not in calls[0]
    assert [c["amount"] for c in calls] == [50, 25, 12] and total == 12


def test_fetch_gives_up_on_endless_rate_limiting():
    n = []

    def get(params):
        n.append(1)
        return {"response_code": 5}

    opentdb.fetch(["Art"], "any", random.Random(1), lambda *_: None, get=get, sleep=lambda _: None)
    assert len(n) == opentdb.MAX_REQUESTS


# ---- the deck -----------------------------------------------------------------

def test_deck_deals_every_question_before_repeating_and_accepts_more():
    deck = QuestionDeck([{"q": str(i)} for i in range(5)], random.Random(2))
    first_round = {deck.draw()["q"] for _ in range(5)}
    assert first_round == {str(i) for i in range(5)}
    deck.add([{"q": "new"}])
    assert "new" in {deck.draw()["q"] for _ in range(6)}


def test_builtin_bank_is_well_formed():
    for q in load_questions():
        assert 3 <= len(q["choices"]) <= 4 and 0 <= q["answer"] < len(q["choices"])


def test_fourth_choice_can_win_a_duel():
    q = {"q": "test", "choices": ["a", "b", "c", "d"], "answer": 3}
    g = OpeningPhase([0, 1], lambda: q, 0.0)
    g.submit_pick(0, 2)
    g.submit_pick(1, 2)
    g.tick(100)
    assert g.answer_duel(0, 3, 101) == "correct"


# ---- the server -----------------------------------------------------------------

def wait_lobby(client, pred, timeout=3.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        for msg in client.messages():
            if msg.get("t") == "lobby" and pred(msg):
                return msg
        time.sleep(0.02)
    raise AssertionError("no matching lobby message")


def test_server_fetches_for_the_room_and_blocks_start_until_questions_arrive():
    release = []

    def fake_fetch(categories, difficulty, rng, on_batch, should_stop):
        assert categories == ["Mythology"] and difficulty == "easy"
        while not release:
            time.sleep(0.01)
        on_batch("Mythology", [opentdb.convert(fake_item(i), rng) for i in range(4)])

    server = GameServer("room", port=5598, categories=["Mythology"], difficulty="easy",
                        fetch=fake_fetch)
    server.start()
    try:
        a = GameClient("127.0.0.1", 5598, "Ana")
        a.send({"t": "add_bot"})
        lobby = wait_lobby(a, lambda m: len(m["players"]) == 2)
        assert lobby["questions"]["status"] == "loading"
        a.send({"t": "start"})                     # refused while loading
        time.sleep(0.2)
        assert server.game is None
        release.append(1)
        lobby = wait_lobby(a, lambda m: m["questions"]["status"] == "ready")
        assert lobby["questions"]["count"] == 4    # online questions replaced the built-in ones
        a.send({"t": "start"})
        time.sleep(0.2)
        assert server.game is not None
        a.close()
    finally:
        server.stop()


def test_server_offline_falls_back_to_builtin_questions():
    def offline(*args, **kwargs):
        raise OSError("no internet")

    server = GameServer("room", port=5597, categories=["Art"], fetch=offline)
    server.start()
    try:
        a = GameClient("127.0.0.1", 5597, "Ana")
        lobby = wait_lobby(a, lambda m: m["questions"]["status"] == "offline")
        assert lobby["questions"]["count"] == len(load_questions())
        a.close()
    finally:
        server.stop()

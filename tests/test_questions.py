"""The question bank and the OpenTDB importer. Never prints answers."""
import base64
import random

from game.opening import OpeningPhase
from game.questions import load_questions, public_view
from tools.import_opentdb import convert


def b64(s):
    return base64.b64encode(s.encode("utf-8")).decode("ascii")


def fake_item(qtype="multiple"):
    return {"type": b64(qtype), "difficulty": b64("easy"), "category": b64("Mythology"),
            "question": b64("Who carries the sky?"), "correct_answer": b64("Atlas"),
            "incorrect_answers": [b64("Hermes"), b64("Ares"), b64("Apollo")]}


def test_convert_keeps_four_shuffled_choices_and_marks_the_source():
    q = convert(fake_item(), random.Random(1))
    assert len(q["choices"]) == 4 and q["choices"][q["answer"]] == "Atlas"
    assert q["source"] == "opentdb" and q["reviewed"] is True
    assert q["category"] == "Mythology" and q["difficulty"] == "easy"


def test_convert_skips_true_false():
    assert convert(fake_item("boolean"), random.Random(1)) is None


def test_question_bank_is_well_formed():
    for q in load_questions():
        assert q["q"].strip()
        assert 3 <= len(q["choices"]) <= 4
        assert len(set(q["choices"])) == len(q["choices"])
        assert 0 <= q["answer"] < len(q["choices"])


def test_public_view_has_category_but_never_the_answer():
    q = convert(fake_item(), random.Random(1))
    view = public_view(q)
    assert "answer" not in view and view["category"] == "Mythology"


def test_fourth_choice_can_win_a_duel():
    q = {"q": "test", "choices": ["a", "b", "c", "d"], "answer": 3}
    g = OpeningPhase([0, 1], lambda: q, 0.0)
    g.submit_pick(0, 2)
    g.submit_pick(1, 2)
    g.tick(100)
    assert g.answer_duel(0, 3, 101) == "correct"

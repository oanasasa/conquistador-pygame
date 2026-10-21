import json
import random
from pathlib import Path

QUESTIONS_PATH = Path(__file__).resolve().parent.parent / "data" / "questions.json"


def load_questions(path=QUESTIONS_PATH):
    with open(path, encoding="utf-8") as f:
        return [q for q in json.load(f) if q.get("reviewed")]


def public_view(q):
    """The question as clients may see it: everything except the answer."""
    view = {"q": q["q"], "choices": list(q["choices"])}
    for key in ("category", "difficulty"):
        if q.get(key):
            view[key] = q[key]
    return view


class QuestionDeck:
    """Draws random questions, avoiding an immediate repeat when possible."""

    def __init__(self, questions, rng=None):
        if not questions:
            raise ValueError("no reviewed questions available")
        self.questions = questions
        self.rng = rng or random.Random()
        self.last = None

    def draw(self):
        options = [q for q in self.questions if q is not self.last] or self.questions
        self.last = self.rng.choice(options)
        return self.last


REVEAL_SECONDS = 3.0   # how long a won duel question stays open for the others


class Reveal:
    """After a duel question is won, it stays open for a moment so players who
    haven't answered yet can still answer and see if they were right. Those
    answers can't change the outcome; they are added to the result as late.
    The game moves on when everyone has answered or the time is up."""

    def __init__(self, question, question_no, asked_at, waiting, result, follow=None):
        self.question = question
        self.no = question_no
        self.asked_at = asked_at
        self.waiting = set(waiting)
        self.result = result
        self.follow = follow       # what the game does next, for phases that need it

    def answer(self, player, choice, question_no, now):
        """Returns True if the late answer was recorded."""
        if (question_no is not None and question_no != self.no) or player not in self.waiting:
            return False
        self.waiting.discard(player)
        self.result["answers"].append({
            "player": player, "correct": choice == self.question["answer"],
            "elapsed": round(now - self.asked_at, 2), "late": True})
        return True

    @property
    def done(self):
        return not self.waiting

import json
import random
from pathlib import Path

QUESTIONS_PATH = Path(__file__).resolve().parent.parent / "data" / "questions.json"


def load_questions(path=QUESTIONS_PATH):
    with open(path, encoding="utf-8") as f:
        return [q for q in json.load(f) if q.get("reviewed")]


def public_view(q):
    """The question as clients may see it: everything except the answer."""
    return {"q": q["q"], "choices": list(q["choices"])}


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

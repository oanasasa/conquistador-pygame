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
    """Deals questions in a shuffled order without repeats until all have been
    used, then reshuffles. Questions can be added while a game is running."""

    def __init__(self, questions=(), rng=None):
        self.rng = rng or random.Random()
        self.questions = list(questions)
        self._pile = []
        self.last = None

    def __len__(self):
        return len(self.questions)

    def add(self, questions):
        new = list(questions)
        self.questions += new
        self.rng.shuffle(new)
        self._pile = new + self._pile          # the pile is drawn from the end

    def replace(self, questions):
        self.questions = list(questions)
        self._pile = []

    def draw(self):
        if not self.questions:
            raise ValueError("no questions available")
        if not self._pile:
            self._pile = list(self.questions)
            self.rng.shuffle(self._pile)
            if len(self._pile) > 1 and self._pile[-1] is self.last:
                self._pile.insert(0, self._pile.pop())   # no immediate repeat
        self.last = self._pile.pop()
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

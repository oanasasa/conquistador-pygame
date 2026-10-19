"""A computer player. Runs on the host next to the server, so it plays by the
same rules as everyone: it selects regions and answers through the game
phase's `select`/`answer` methods and is judged like any other player.
Works with any phase that offers `bot_task(player)`."""
import random

PICK_DELAY = (3.0, 9.0)       # seconds before the bot selects, like a human thinking
ANSWER_DELAY = (1.5, 6.0)     # seconds before the bot answers a question
ACCURACY = 0.6                # chance the bot answers correctly


class Bot:
    def __init__(self, pid, rng=None, accuracy=ACCURACY):
        self.pid = pid
        self.rng = rng or random.Random()
        self.accuracy = accuracy
        self.task = None      # (kind, token) the bot is waiting to act on
        self.due = None       # when it will act

    def act(self, game, now):
        """Let the bot move if it's time. Returns True if the shared state changed."""
        task = game.bot_task(self.pid)
        key = task[:2] if task else None
        if key != self.task:
            self.task = key
            delay = PICK_DELAY if key and key[0] == "select" else ANSWER_DELAY
            self.due = now + self.rng.uniform(*delay) if key else None
        if self.due is None or now < self.due:
            return False
        self.due = None
        kind, _, payload = task
        if kind == "select":
            accepted = game.select(self.pid, self.rng.choice(payload), now)
            return accepted and game.picks_visible
        n = len(payload["choices"])
        if self.rng.random() < self.accuracy:
            choice = payload["answer"]
        else:
            choice = self.rng.choice([i for i in range(n) if i != payload["answer"]])
        return game.answer(self.pid, choice, now) is not None

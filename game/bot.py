"""A computer player for the opening phase. Runs on the host next to the
server, so it plays by the same rules as everyone: it submits picks and
answers through OpeningPhase and is judged like any other player."""
import random

PICK_DELAY = (3.0, 9.0)       # seconds before the bot picks, like a human thinking
ANSWER_DELAY = (1.5, 6.0)     # seconds before the bot answers a bonus question
ACCURACY = 0.6                # chance the bot answers correctly


class Bot:
    def __init__(self, pid, rng=None, accuracy=ACCURACY):
        self.pid = pid
        self.rng = rng or random.Random()
        self.accuracy = accuracy
        self.task = None      # what the bot is waiting to do: ("pick" | "duel", deadline)
        self.due = None       # when it will do it

    def _current_task(self, game):
        if game.phase == "pick" and self.pid in game.pickers:
            return ("pick", game.deadline)
        if (game.phase == "duel" and self.pid in game.duel.players
                and self.pid not in game.duel.locked_out):
            return ("duel", game.deadline)   # deadline changes with every new question
        return None

    def act(self, game, now):
        """Let the bot move if it's time. Returns True if the shared state changed."""
        task = self._current_task(game)
        if task != self.task:
            self.task = task
            delay = PICK_DELAY if task and task[0] == "pick" else ANSWER_DELAY
            self.due = now + self.rng.uniform(*delay) if task else None
        if self.due is None or now < self.due:
            return False
        self.due = None
        if task[0] == "pick":
            free = game.free_regions()
            if free:
                game.submit_pick(self.pid, self.rng.choice(free))
            return False      # picks are hidden, nothing to broadcast
        question = game.duel.question
        n = len(question["choices"])
        if self.rng.random() < self.accuracy:
            choice = question["answer"]
        else:
            choice = self.rng.choice([i for i in range(n) if i != question["answer"]])
        return game.answer_duel(self.pid, choice, now) is not None

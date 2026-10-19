"""Opening phase: every player secretly picks a starting region.

Pure game logic with no pygame and no sockets. Times are passed in as `now`
(seconds, any monotonic clock) so the server and the tests drive the clock.
"""
import random

from game.board import NUM_REGIONS
from game.questions import public_view

PICK_SECONDS = 15
DUEL_SECONDS = 10


class Duel:
    def __init__(self, region, players):
        self.region = region
        self.players = list(players)
        self.question = None
        self.question_no = 0
        self.asked_at = 0.0
        self.locked_out = set()

    def ask(self, question, number, now):
        self.question = question
        self.question_no = number
        self.asked_at = now
        self.locked_out = set()


class OpeningPhase:
    def __init__(self, players, next_question, now, num_regions=NUM_REGIONS, rng=None):
        self.players = list(players)
        self.next_question = next_question   # callable returning a question dict
        self.num_regions = num_regions
        self.rng = rng or random.Random()
        self.owner = {}            # region -> player
        self.picks = {}            # player -> region, current pick round only
        self.pickers = set()       # who picks in the current round
        self.repickers = set()     # duel losers waiting for the next pick round
        self.missed = set()        # never picked; get a random region at the end
        self.duels = []            # queued Duels
        self.duel = None           # the Duel being played
        self.last_result = None    # {"region", "winner", "elapsed"} of the last duel
        self.questions_asked = 0   # numbers questions across all duels
        self.phase = None
        self.deadline = 0.0
        self._start_pick_round(set(self.players), now)

    # ---- queries -------------------------------------------------------

    def free_regions(self):
        return [r for r in range(self.num_regions) if r not in self.owner]

    def region_of(self, player):
        for region, owner in self.owner.items():
            if owner == player:
                return region
        return None

    def is_done(self):
        return self.phase == "done"

    # ---- actions -------------------------------------------------------

    def submit_pick(self, player, region):
        """Record (or change) a hidden pick. Returns True if accepted."""
        if self.phase != "pick" or player not in self.pickers:
            return False
        if region not in self.free_regions():
            return False
        self.picks[player] = region
        return True

    def answer_duel(self, player, choice, now):
        """Judge an answer in arrival order: the first correct one wins.

        Returns "correct", "wrong", or None if the answer was not accepted.
        """
        duel = self.duel
        if self.phase != "duel" or player not in duel.players or player in duel.locked_out:
            return None
        if choice == duel.question["answer"]:
            self._finish_duel(player, now, elapsed=now - duel.asked_at)
            return "correct"
        duel.locked_out.add(player)
        if duel.locked_out >= set(duel.players):
            self._ask(now)   # everyone wrong: new question, same duel
        return "wrong"

    def tick(self, now):
        """Handle expired timers. Returns True if the state changed.

        A pick round ends early once every picker has chosen a region."""
        if self.phase == "pick" and (now >= self.deadline or self.picks.keys() >= self.pickers):
            self._end_pick_round(now)
            return True
        if self.phase == "duel" and now >= self.deadline:
            self._ask(now)   # nobody got it in time: new question
            return True
        return False

    def remove_player(self, player, now):
        """A player disconnected: free their region and drop them from duels."""
        if player not in self.players:
            return
        self.players.remove(player)
        self.owner = {r: p for r, p in self.owner.items() if p != player}
        self.picks.pop(player, None)
        for group in (self.pickers, self.repickers, self.missed):
            group.discard(player)
        for d in self.duels:
            if player in d.players:
                d.players.remove(player)
        if self.duel and player in self.duel.players:
            self.duel.players.remove(player)
            self.duel.locked_out.discard(player)
        self._settle_uncontested(now)

    # ---- shared interface (server and bots) ----------------------------

    picks_visible = False

    def select(self, player, region, now=None):
        return self.submit_pick(player, region)

    def answer(self, player, choice, now):
        return self.answer_duel(player, choice, now)

    def bot_task(self, player):
        """What `player` could do now: (kind, token, options) or None."""
        if self.phase == "pick" and player in self.pickers:
            return ("select", self.deadline, self.free_regions())
        if (self.phase == "duel" and player in self.duel.players
                and player not in self.duel.locked_out):
            return ("answer", self.deadline, self.duel.question)
        return None

    # ---- snapshots -----------------------------------------------------

    def public_state(self, viewer, now):
        """What `viewer` may see. Other players' picks and all answers stay hidden."""
        state = {
            "stage": "opening",
            "phase": self.phase,
            "remaining": max(0.0, self.deadline - now) if self.phase in ("pick", "duel") else 0.0,
            "owner": {str(r): p for r, p in self.owner.items()},
            "pickers": sorted(self.pickers),
            "your_pick": self.picks.get(viewer),
            "last_result": self.last_result,
            "duel": None,
        }
        if self.phase == "duel":
            d = self.duel
            state["duel"] = {
                "region": d.region,
                "players": list(d.players),
                "question": public_view(d.question),
                "question_no": d.question_no,
                "locked_out": sorted(d.locked_out),
            }
        return state

    # ---- internals -----------------------------------------------------

    def _start_pick_round(self, pickers, now):
        self.phase = "pick"
        self.pickers = set(pickers)
        self.picks = {}
        self.deadline = now + PICK_SECONDS

    def _end_pick_round(self, now):
        by_region = {}
        for player in sorted(self.pickers):
            if player in self.picks:
                by_region.setdefault(self.picks[player], []).append(player)
            else:
                self.missed.add(player)
        for region, players in sorted(by_region.items()):
            if len(players) == 1:
                self.owner[region] = players[0]
            else:
                self.duels.append(Duel(region, players))
        self.pickers = set()
        self.picks = {}
        self._advance(now)

    def _advance(self, now):
        if self.duels:
            self.phase = "duel"
            self.duel = self.duels.pop(0)
            self._ask(now)
            self._settle_uncontested(now)
        elif self.repickers:
            losers, self.repickers = self.repickers, set()
            self._start_pick_round(losers, now)
        else:
            self._assign_random()
            self.phase = "done"
            self.duel = None

    def _ask(self, now):
        self.questions_asked += 1
        self.duel.ask(self.next_question(), self.questions_asked, now)
        self.deadline = now + DUEL_SECONDS

    def _finish_duel(self, winner, now, elapsed):
        duel = self.duel
        self.owner[duel.region] = winner
        self.repickers.update(p for p in duel.players if p != winner)
        self.last_result = {"region": duel.region, "winner": winner,
                            "elapsed": round(elapsed, 2) if elapsed is not None else None}
        self.duel = None
        self._advance(now)

    def _settle_uncontested(self, now):
        """After a disconnect, a duel with one player left goes to that player."""
        for d in [d for d in self.duels if len(d.players) <= 1]:
            self.duels.remove(d)
            if d.players:
                self.owner[d.region] = d.players[0]
        if self.phase == "duel" and self.duel and len(self.duel.players) <= 1:
            if self.duel.players:
                self._finish_duel(self.duel.players[0], now, elapsed=None)
            else:
                self.duel = None
                self._advance(now)
        elif self.phase == "pick" and not self.pickers:
            self._end_pick_round(now)

    def _assign_random(self):
        for player in sorted(self.missed):
            if player in self.players and self.region_of(player) is None:
                free = self.free_regions()
                if free:
                    self.owner[self.rng.choice(free)] = player
        self.missed = set()

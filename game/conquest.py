"""Main game, after every player has a starting region (their base).

Land grab: while free land remains, each round every player has a fixed
10 seconds to select a free region next to their land. Selections are
visible, and the first player to select a region locks it. Then everyone
with a selection answers one question; each correct player takes their region.

War: once no free land remains, players take turns attacking an enemy region
next to their land. A normal region is a duel with its owner (quickest correct
answer wins). A base has 3 towers and is attacked with up to 3 duel questions
in a row; each one the attacker wins destroys a tower. When the last tower
falls, the attacker takes all of the defender's land and the defender is out.

Pure game logic with no pygame and no sockets; `now` is passed in.
"""
from game.board import default_board
from game.questions import REVEAL_SECONDS, Reveal, public_view

SELECT_SECONDS = 10
QUESTION_SECONDS = 10
TOWERS = 3


class ConquestPhase:
    picks_visible = True

    def __init__(self, players, owner, next_question, now, board=None):
        self.board = board or default_board()
        self.players = sorted(players)                       # alive, in turn order
        self.owner = dict(owner)                             # region -> player
        self.bases = {p: r for r, p in owner.items()}        # player -> base region
        self.towers = {p: TOWERS for p in self.players}
        self.next_question = next_question
        self.phase = None
        self.deadline = 0.0
        self.selections = {}       # player -> region, visible to everyone
        self.question = None
        self.question_no = 0
        self.asked_at = 0.0
        self.answering = set()     # land grab: players answering this question
        self.answered = {}         # land grab: player -> True/False
        self.attacker = None       # war: whose turn it is
        self.attack = None         # war: {"region", "defender", "base", "tower_q", "locked_out"}
        self.last_result = None
        self.results = 0           # numbers results so clients notice new ones
        self.answers = []          # [{"player", "correct", "elapsed"}] for the open question
        self.reveal = None         # a won duel question still open for the others
        self._pending_follow = None  # what happens after the reveal
        self.winner = None
        self._next_round(now)

    # ---- queries -------------------------------------------------------

    def free_regions(self):
        return [r for r in range(self.board.num_regions) if r not in self.owner]

    def selectable(self, player):
        """Regions `player` may select right now."""
        if self.phase == "grab_select" and player in self.players:
            taken = {r for p, r in self.selections.items() if p != player}
            return [r for r in self.board.frontier(self.owner, player)
                    if r not in self.owner and r not in taken]
        if self.phase == "war_select" and player == self.attacker:
            return [r for r in self.board.frontier(self.owner, player) if r in self.owner]
        return []

    def is_done(self):
        return self.phase == "over"

    # ---- actions -------------------------------------------------------

    def select(self, player, region, now=None):
        """Select (or change) a target region. Returns True if accepted."""
        if region not in self.selectable(player):
            return False
        self.selections[player] = region
        return True

    def answer(self, player, choice, now, question_no=None):
        """Returns "correct", "wrong", "late" (answered after the other player
        had already won, for display only), or None if not accepted.
        `question_no` is the question the player saw; an answer meant for an
        earlier question is never applied to the current one."""
        if self.reveal:
            if now >= self.deadline:
                self._end_reveal(now)
                return None
            if not self.reveal.answer(player, choice, question_no, now):
                return None
            if self.reveal.done:
                self._end_reveal(now)
            return "late"
        if self.phase not in ("grab_question", "war_duel") or (
                question_no is not None and question_no != self.question_no):
            return None
        correct = choice == self.question["answer"]
        record = {"player": player, "correct": correct, "elapsed": round(now - self.asked_at, 2)}
        if self.phase == "grab_question":
            if player not in self.answering or player in self.answered:
                return None
            self.answered[player] = correct
            self.answers.append(record)
            if self.answered.keys() >= self.answering:
                self._finish_grab(now)
            return "correct" if correct else "wrong"
        if self.phase == "war_duel":
            a = self.attack
            fighters = (self.attacker, a["defender"])
            if player not in fighters or player in a["locked_out"]:
                return None
            self.answers.append(record)
            if correct:
                self._duel_won(player, now)
                return "correct"
            a["locked_out"].add(player)
            if a["locked_out"] >= set(fighters):
                self._duel_won(None, now)      # both wrong: the defender holds
            return "wrong"
        return None

    def tick(self, now):
        """Handle expired timers. Returns True if the state changed."""
        if now < self.deadline:
            return False
        if self.reveal:
            self._end_reveal(now)
            return True
        if self.phase == "grab_select":
            if self.selections:
                self._ask(now)
                self.phase = "grab_question"
                self.answering = set(self.selections)
                self.answered = {}
            else:
                self._next_round(now)
            return True
        if self.phase == "grab_question":
            self._finish_grab(now)
            return True
        if self.phase == "war_select":
            region = self.selections.get(self.attacker)
            if region is None:
                self._result({"kind": "skip", "attacker": self.attacker})
                self._next_turn(now)
            else:
                defender = self.owner[region]
                self.attack = {"region": region, "defender": defender,
                               "base": region == self.bases.get(defender),
                               "tower_q": 1, "locked_out": set()}
                self.phase = "war_duel"
                self._ask(now)
            return True
        if self.phase == "war_duel":
            self._duel_won(None, now)          # time ran out: the defender holds
            return True
        return False

    def remove_player(self, player, now):
        """A player disconnected: their land becomes free and they are out."""
        if player not in self.players:
            return
        self.players.remove(player)
        self.owner = {r: p for r, p in self.owner.items() if p != player}
        self.bases.pop(player, None)
        self.towers.pop(player, None)
        self.selections.pop(player, None)
        self.answering.discard(player)
        self.answered.pop(player, None)
        if self.reveal:
            self.reveal = None           # skip the pause
            fighter = player in (self.attacker, self.attack["defender"])
            if not fighter and len(self.players) > 1:
                self._follow(self._pending_follow, now)
                return
        if len(self.players) <= 1:
            self._game_over(self.players[0] if self.players else None)
        elif self.phase == "grab_question" and self.answered.keys() >= self.answering:
            self._finish_grab(now)
        elif self.phase in ("war_select", "war_duel") and (
                player == self.attacker or (self.attack and player == self.attack["defender"])):
            self.attack = None
            self._next_turn(now, after=player)

    # ---- bots ----------------------------------------------------------

    def bot_task(self, player):
        """What `player` could do now: (kind, token, options) or None."""
        if self.reveal:
            return None
        if self.phase in ("grab_select", "war_select") and player not in self.selections:
            options = self.selectable(player)
            return ("select", self.deadline, options) if options else None
        if self.phase == "grab_question" and player in self.answering and player not in self.answered:
            return ("answer", self.deadline, self.question)
        if self.phase == "war_duel" and player in (self.attacker, self.attack["defender"]) \
                and player not in self.attack["locked_out"]:
            return ("answer", self.deadline, self.question)
        return None

    # ---- snapshots -----------------------------------------------------

    def public_state(self, viewer, now):
        """What `viewer` may see. Answers are never included."""
        state = {
            "stage": "conquest",
            "phase": self.phase,
            "remaining": max(0.0, self.deadline - now) if self.phase != "over" else 0.0,
            "owner": {str(r): p for r, p in self.owner.items()},
            "bases": {str(p): r for p, r in self.bases.items()},
            "towers": {str(p): n for p, n in self.towers.items()},
            "players": list(self.players),
            "selections": {str(p): r for p, r in self.selections.items()},
            "selectable": self.selectable(viewer),
            "attacker": self.attacker,
            "last_result": self.last_result,
            "winner": self.winner,
            "question": None,
            "question_no": self.question_no,
            "answering": [],
            "answered": [],
            "attack": None,
        }
        if self.phase in ("grab_question", "war_duel"):
            state["question"] = public_view(self.question)
        if self.phase == "grab_question":
            state["answering"] = sorted(self.answering)
            state["answered"] = sorted(self.answered)
        if self.phase == "war_duel":
            a = self.attack
            state["attack"] = {"region": a["region"], "defender": a["defender"],
                               "base": a["base"], "tower_q": a["tower_q"],
                               "locked_out": sorted(a["locked_out"]),
                               "reveal": self.reveal is not None,
                               "waiting": sorted(self.reveal.waiting) if self.reveal else []}
        return state

    # ---- internals -----------------------------------------------------

    def _result(self, result):
        self.results += 1
        result["no"] = self.results
        self.last_result = result
        return result

    def _ask(self, now):
        self.question = self.next_question()
        self.question_no += 1
        self.asked_at = now
        self.answers = []
        self.deadline = now + QUESTION_SECONDS

    def _next_round(self, now, after=None):
        self.selections = {}
        self.question = None
        if self._check_winner():
            return
        if self.free_regions():
            self.phase = "grab_select"
            self.deadline = now + SELECT_SECONDS
        else:
            self._next_turn(now, after=after)

    def _next_turn(self, now, after=None):
        """Hand the attack to the next alive player in turn order."""
        self.attack = None
        self.selections = {}
        self.question = None
        if self._check_winner():
            return
        if self.free_regions():          # a player left and freed land: grab it first
            self.phase = "grab_select"
            self.deadline = now + SELECT_SECONDS
            return
        prev = after if after is not None else self.attacker
        if prev is None:
            self.attacker = self.players[0]
        else:
            later = [p for p in self.players if p > prev]
            self.attacker = later[0] if later else self.players[0]
        self.phase = "war_select"
        self.deadline = now + SELECT_SECONDS

    def _finish_grab(self, now):
        won = {}
        for player, correct in self.answered.items():
            region = self.selections.get(player)
            if correct and region is not None and region not in self.owner:
                self.owner[region] = player
                won[player] = region
        missed = sorted(p for p in self.answering if p not in won)
        self._result({"kind": "grab", "won": {str(p): r for p, r in won.items()},
                      "missed": missed, "answers": sorted(self.answers, key=lambda a: a["elapsed"])})
        self.answering, self.answered = set(), {}
        self._next_round(now)

    def _duel_won(self, winner, now):
        """Resolve one war question. `winner` is None if the defender held by default."""
        a = self.attack
        attacker, defender, region = self.attacker, a["defender"], a["region"]
        attacker_won = winner == attacker
        result = {"kind": "attack", "attacker": attacker, "defender": defender,
                  "region": region, "base": a["base"], "attacker_won": attacker_won,
                  "elapsed": round(now - self.asked_at, 2) if winner is not None else None,
                  "answers": list(self.answers)}
        follow = "turn"
        if not a["base"]:
            if attacker_won:
                self.owner[region] = attacker
        else:
            if attacker_won:
                self.towers[defender] -= 1
            result["towers_left"] = self.towers[defender]
            result["tower_q"] = a["tower_q"]
            if self.towers[defender] <= 0:
                for r, p in list(self.owner.items()):
                    if p == defender:
                        self.owner[r] = attacker
                self.players.remove(defender)
                self.bases.pop(defender)
                self.towers.pop(defender)
                result["base_fell"] = True
            elif a["tower_q"] < TOWERS:
                follow = "next_tower"
        self._result(result)
        answered = {x["player"] for x in self.answers}
        waiting = [p for p in (attacker, defender) if p not in answered]
        if winner is not None and waiting:
            # Keep the question open so the other fighter can still answer.
            self.reveal = Reveal(self.question, self.question_no, self.asked_at, waiting, result)
            self._pending_follow = follow
            self.deadline = now + REVEAL_SECONDS
            return
        self._follow(follow, now)

    def _end_reveal(self, now):
        self.reveal = None
        self._follow(self._pending_follow, now)

    def _follow(self, follow, now):
        """Continue after a war question: the next siege question or the next turn."""
        if follow == "next_tower":
            self.attack["tower_q"] += 1
            self.attack["locked_out"] = set()
            self._ask(now)
        else:
            self._next_turn(now)

    def _check_winner(self):
        """Bases only fall with all their land, so the last player standing
        owns the whole map (unless the others disconnected)."""
        if len(self.players) <= 1:
            self._game_over(self.players[0] if self.players else None)
            return True
        return False

    def _game_over(self, winner):
        self.winner = winner
        self.phase = "over"
        self.attack = None
        self.question = None

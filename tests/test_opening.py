import random

from game.opening import DUEL_SECONDS, PICK_SECONDS, OpeningPhase
from game.questions import REVEAL_SECONDS

# Fake question for tests only; the real bank lives in data/questions.json.
FAKE_Q = {"q": "test", "choices": ["a", "b", "c"], "answer": 0}
RIGHT, WRONG = 0, 1


def make(players=(0, 1, 2), now=0.0, seed=1):
    return OpeningPhase(list(players), lambda: FAKE_Q, now, rng=random.Random(seed), interlude=0)


def win(game, player, now):
    """`player` answers correctly first; let the reveal for the others run out."""
    assert game.answer_duel(player, RIGHT, now) == "correct"
    game.tick(now + REVEAL_SECONDS)


def end_picks(game, now):
    game.tick(now + PICK_SECONDS)
    return now + PICK_SECONDS


def test_no_conflicts_assigns_each_pick():
    g = make()
    for p, r in [(0, 0), (1, 5), (2, 11)]:
        assert g.submit_pick(p, r)
    end_picks(g, 0)
    assert g.is_done()
    assert g.owner == {0: 0, 5: 1, 11: 2}


def test_picks_can_change_until_timer_and_stay_hidden():
    g = make()
    g.submit_pick(0, 3)
    g.submit_pick(0, 4)
    g.submit_pick(1, 7)
    state = g.public_state(0, now=1)
    assert state["your_pick"] == 4
    assert "picks" not in state and 7 not in state.values()
    end_picks(g, 0)
    assert g.owner[4] == 0


def test_two_way_conflict_goes_to_duel_and_loser_repicks():
    g = make()
    g.submit_pick(0, 2)
    g.submit_pick(1, 2)
    g.submit_pick(2, 9)
    t = end_picks(g, 0)
    assert g.phase == "duel" and g.duel.region == 2
    assert g.owner == {9: 2}
    assert g.answer_duel(1, RIGHT, t + 1.5) == "correct"
    assert g.owner[2] == 1
    res = g.last_result
    assert (res["region"], res["winner"], res["elapsed"]) == (2, 1, 1.5)
    assert res["answers"] == [{"player": 1, "correct": True, "elapsed": 1.5}]
    assert g.reveal and g.phase == "duel"          # question stays open for player 0
    g.tick(t + 1.5 + REVEAL_SECONDS)
    assert g.phase == "pick" and g.pickers == {0}
    assert not g.submit_pick(0, 2)          # taken regions are rejected
    assert g.submit_pick(0, 3)
    end_picks(g, t + 1.5)
    assert g.is_done() and g.owner[3] == 0


def test_three_way_conflict_two_losers_repick():
    g = make()
    for p in (0, 1, 2):
        g.submit_pick(p, 6)
    t = end_picks(g, 0)
    assert sorted(g.duel.players) == [0, 1, 2]
    win(g, 2, t + 1)
    assert g.owner == {6: 2}
    assert g.phase == "pick" and g.pickers == {0, 1}


def test_quickest_correct_answer_wins():
    g = make(players=(0, 1))
    g.submit_pick(0, 1)
    g.submit_pick(1, 1)
    t = end_picks(g, 0)
    # Both know the answer; the server processes them in arrival order.
    assert g.answer_duel(1, RIGHT, t + 0.8) == "correct"
    assert g.answer_duel(0, RIGHT, t + 0.9) == "late"     # right, but slower
    assert g.owner[1] == 1


def test_wrong_answer_locks_out_then_other_wins():
    g = make(players=(0, 1))
    g.submit_pick(0, 4)
    g.submit_pick(1, 4)
    t = end_picks(g, 0)
    assert g.answer_duel(0, WRONG, t + 1) == "wrong"
    assert g.answer_duel(0, RIGHT, t + 2) is None   # locked out
    assert g.answer_duel(1, RIGHT, t + 3) == "correct"
    assert g.owner[4] == 1


def test_everyone_wrong_or_timeout_asks_new_question():
    g = make(players=(0, 1))
    g.submit_pick(0, 4)
    g.submit_pick(1, 4)
    t = end_picks(g, 0)
    g.answer_duel(0, WRONG, t + 1)
    g.answer_duel(1, WRONG, t + 2)
    assert g.phase == "duel" and g.duel.question_no == 2
    assert g.duel.locked_out == set()
    g.tick(t + 2 + DUEL_SECONDS)
    assert g.duel.question_no == 3


def test_missed_pick_gets_random_free_region():
    g = make()
    g.submit_pick(0, 0)
    g.submit_pick(1, 1)
    end_picks(g, 0)
    assert g.is_done()
    region = g.region_of(2)
    assert region is not None and region not in (0, 1)


def test_repickers_colliding_duel_again():
    g = make()
    for p in (0, 1, 2):
        g.submit_pick(p, 6)
    t = end_picks(g, 0)
    win(g, 0, t + 1)
    g.submit_pick(1, 8)
    g.submit_pick(2, 8)
    t = end_picks(g, t + 1)
    assert g.phase == "duel" and g.duel.region == 8
    win(g, 2, t + 1)
    g.submit_pick(1, 9)
    end_picks(g, t + 1)
    assert g.is_done()
    assert g.owner == {6: 0, 8: 2, 9: 1}


def test_disconnect_during_duel_gives_region_to_remaining_player():
    g = make()
    g.submit_pick(0, 3)
    g.submit_pick(1, 3)
    g.submit_pick(2, 5)
    t = end_picks(g, 0)
    g.remove_player(0, t + 1)
    assert g.owner[3] == 1
    assert g.is_done()


def test_answer_never_in_public_state():
    g = make(players=(0, 1))
    g.submit_pick(0, 1)
    g.submit_pick(1, 1)
    t = end_picks(g, 0)
    assert "answer" not in g.public_state(0, t)["duel"]["question"]


def test_pick_round_ends_as_soon_as_everyone_picked():
    g = make(players=(0, 1))
    g.submit_pick(0, 2)
    assert not g.tick(1.0)                   # one player still choosing
    g.submit_pick(1, 7)
    assert g.tick(2.0)                       # both picked: no waiting for the timer
    assert g.is_done() and g.owner == {2: 0, 7: 1}


def test_repick_round_ends_when_the_loser_picks():
    g = make(players=(0, 1))
    g.submit_pick(0, 4)
    g.submit_pick(1, 4)
    g.tick(1.0)
    win(g, 0, 2.0)
    assert g.phase == "pick" and g.pickers == {1}
    g.submit_pick(1, 9)
    assert g.tick(3.0) and g.is_done()


def test_question_numbers_keep_counting_across_duels():
    # The client blocks re-answering by question number, so a second duel must
    # not reuse the first duel's numbers.
    g = make()
    for p in (0, 1, 2):
        g.submit_pick(p, 6)
    t = end_picks(g, 0)
    first = g.duel.question_no
    win(g, 0, t + 1)
    g.submit_pick(1, 8)
    g.submit_pick(2, 8)
    end_picks(g, t + 1)
    assert g.duel.question_no > first


def test_slower_correct_answer_is_shown_but_does_not_win():
    g = make(players=(0, 1))
    g.submit_pick(0, 1)
    g.submit_pick(1, 1)
    t = end_picks(g, 0)
    q = g.duel.question_no
    assert g.answer_duel(1, RIGHT, t + 0.8, q) == "correct"
    assert g.answer_duel(0, RIGHT, t + 1.2, q) == "late"
    assert g.owner[1] == 1
    answers = g.last_result["answers"]
    assert answers[0] == {"player": 1, "correct": True, "elapsed": 0.8}
    assert answers[1] == {"player": 0, "correct": True, "elapsed": 1.2, "late": True}
    assert g.answer_duel(0, RIGHT, t + 1.3, q) is None      # only once


def test_late_answer_window_closes():
    g = make(players=(0, 1))
    g.submit_pick(0, 1)
    g.submit_pick(1, 1)
    t = end_picks(g, 0)
    q = g.duel.question_no
    g.answer_duel(1, RIGHT, t + 1, q)
    assert g.answer_duel(0, RIGHT, t + 10, q) is None


def test_answer_for_an_old_question_is_not_applied_to_the_new_one():
    g = make(players=(0, 1))
    g.submit_pick(0, 1)
    g.submit_pick(1, 1)
    t = end_picks(g, 0)
    old = g.duel.question_no
    g.tick(t + DUEL_SECONDS)                     # timeout: new question
    assert g.answer_duel(0, RIGHT, t + DUEL_SECONDS + 0.1, old) is None
    assert 1 not in g.owner


def test_reveal_ends_as_soon_as_everyone_answered():
    g = make(players=(0, 1))
    g.submit_pick(0, 1)
    g.submit_pick(1, 1)
    t = end_picks(g, 0)
    g.answer_duel(1, RIGHT, t + 1)
    assert g.reveal and g.public_state(0, t + 1)["duel"]["waiting"] == [0]
    g.answer_duel(0, WRONG, t + 1.5)
    assert g.reveal is None and g.phase == "pick"


def test_reveal_times_out():
    g = make(players=(0, 1))
    g.submit_pick(0, 1)
    g.submit_pick(1, 1)
    t = end_picks(g, 0)
    g.answer_duel(1, RIGHT, t + 1)
    assert not g.tick(t + 1 + REVEAL_SECONDS - 0.1)
    assert g.tick(t + 1 + REVEAL_SECONDS)
    assert g.reveal is None and g.phase == "pick"


def test_losers_get_a_pause_before_choosing_again():
    g = OpeningPhase([0, 1], lambda: FAKE_Q, 0.0, rng=random.Random(1), interlude=3)
    g.submit_pick(0, 4)
    g.submit_pick(1, 4)
    t = end_picks(g, 0)
    g.answer_duel(0, RIGHT, t + 1)
    g.answer_duel(1, WRONG, t + 1.5)              # both answered: the reveal ends
    assert g.phase == "interlude"
    assert g.public_state(1, t + 1.5)["next"] == {"phase": "pick", "pickers": [1]}
    assert not g.submit_pick(1, 5)                # no choosing during the pause
    assert g.tick(t + 4.5)
    assert g.phase == "pick" and g.pickers == {1}
    assert g.deadline == t + 4.5 + PICK_SECONDS

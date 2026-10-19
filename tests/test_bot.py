import random

from game.bot import ANSWER_DELAY, PICK_DELAY, Bot
from game.opening import OpeningPhase

# Fake question for tests only; the real bank lives in data/questions.json.
FAKE_Q = {"q": "test", "choices": ["a", "b", "c"], "answer": 0}


def make(players=(0, 1)):
    return OpeningPhase(list(players), lambda: FAKE_Q, 0.0, rng=random.Random(1))


def test_bot_waits_then_picks_a_free_region():
    g = make()
    g.submit_pick(0, 5)
    bot = Bot(1, random.Random(2))
    bot.act(g, 0.0)
    assert 1 not in g.picks                       # still thinking
    bot.act(g, PICK_DELAY[1])
    assert g.picks[1] in g.free_regions()


def test_bot_answers_duel_after_delay():
    g = make()
    g.submit_pick(0, 5)
    g.submit_pick(1, 5)
    g.tick(100)                                   # end the pick round
    assert g.phase == "duel"
    bot = Bot(1, random.Random(3), accuracy=1.0)
    assert not bot.act(g, 100)
    assert bot.act(g, 100 + ANSWER_DELAY[1])
    assert g.owner[5] == 1


def test_wrong_bot_gets_locked_out_and_human_can_win():
    g = make()
    g.submit_pick(0, 5)
    g.submit_pick(1, 5)
    g.tick(100)
    bot = Bot(1, random.Random(4), accuracy=0.0)
    bot.act(g, 100)
    bot.act(g, 100 + ANSWER_DELAY[1])
    assert g.duel.locked_out == {1}
    assert g.answer_duel(0, FAKE_Q["answer"], 107) == "correct"
    assert g.owner[5] == 0


def test_full_game_with_only_bots_finishes():
    g = make(players=(0, 1, 2))
    bots = [Bot(p, random.Random(p), accuracy=0.5) for p in (0, 1, 2)]
    t = 0.0
    while not g.is_done() and t < 600:
        g.tick(t)
        for b in bots:
            b.act(g, t)
        t += 0.1
    assert g.is_done()
    assert sorted(g.owner.values()) == [0, 1, 2]


def test_bot_pick_delay_feels_human_and_ends_round_with_human():
    assert PICK_DELAY[0] >= 3.0
    g = make()
    g.submit_pick(0, 5)                      # human picked right away
    bot = Bot(1, random.Random(5))
    bot.act(g, 0.0)
    bot.act(g, PICK_DELAY[0] - 0.1)
    assert 1 not in g.picks                  # never instant
    bot.act(g, PICK_DELAY[1])
    assert g.tick(PICK_DELAY[1]) and g.phase != "pick"

import random

from game.board import default_board, grid_board
from game.bot import Bot
from game.conquest import QUESTION_SECONDS, SELECT_SECONDS, TOWERS, ConquestPhase
from game.questions import REVEAL_SECONDS

# Fake question for tests only; the real bank lives in data/questions.json.
FAKE_Q = {"q": "test", "choices": ["a", "b", "c"], "answer": 0}
RIGHT, WRONG = 0, 1

# Grid (region numbers):
#   0  1  2  3
#   4  5  6  7
#   8  9 10 11


GRID = grid_board(4, 3)


def make(owner, now=0.0):
    return ConquestPhase(sorted(set(owner.values())), owner, lambda: FAKE_Q, now, board=GRID,
                         interlude=0)


def test_neighbors_and_frontier():
    assert GRID.neighbors(0) == [1, 4]
    assert GRID.neighbors(5) == [1, 4, 6, 9]
    assert GRID.frontier({0: 0, 1: 0, 11: 1}, 0) == [2, 4, 5]


def test_romania_map_borders_are_symmetric_and_connected():
    board = default_board()
    assert board.num_regions == 20
    for r in range(board.num_regions):
        for n in board.neighbors(r):
            assert r in board.neighbors(n)
    seen, todo = {0}, [0]
    while todo:
        for n in board.neighbors(todo.pop()):
            if n not in seen:
                seen.add(n)
                todo.append(n)
    assert len(seen) == board.num_regions


# ---- land grab -------------------------------------------------------------

def test_grab_select_only_adjacent_free_regions():
    g = make({0: 0, 11: 1})
    assert g.phase == "grab_select"
    assert g.selectable(0) == [1, 4]
    assert not g.select(0, 5)              # not adjacent
    assert not g.select(0, 11)             # owned
    assert g.select(0, 1)


def test_first_selector_locks_the_region_and_can_change():
    g = make({0: 0, 2: 1})
    assert g.select(0, 1)
    assert not g.select(1, 1)              # locked by player 0
    assert g.select(0, 4)                  # changing releases region 1
    assert g.select(1, 1)
    state = g.public_state(1, 1.0)
    assert state["selections"] == {"0": 4, "1": 1}   # visible to everyone


def test_select_window_is_fixed_ten_seconds():
    g = make({0: 0, 11: 1})
    g.select(0, 1)
    g.select(1, 10)
    assert not g.tick(SELECT_SECONDS - 0.1)      # no early end even if all selected
    assert g.tick(SELECT_SECONDS)
    assert g.phase == "grab_question"
    assert g.answering == {0, 1}


def test_grab_question_correct_answers_take_their_regions():
    g = make({0: 0, 11: 1})
    g.select(0, 1)
    g.select(1, 10)
    t = SELECT_SECONDS
    g.tick(t)
    g.answer(0, RIGHT, t + 1)
    g.answer(1, WRONG, t + 2)              # last answer ends the question early
    assert g.owner == {0: 0, 1: 0, 11: 1}
    res = g.last_result
    assert (res["kind"], res["won"], res["missed"]) == ("grab", {"0": 1}, [1])
    assert [(a["player"], a["correct"]) for a in res["answers"]] == [(0, True), (1, False)]
    assert g.phase == "grab_select"


def test_grab_question_times_out():
    g = make({0: 0, 11: 1})
    g.select(0, 1)
    g.tick(SELECT_SECONDS)
    g.tick(SELECT_SECONDS + QUESTION_SECONDS)
    assert 1 not in g.owner and g.phase == "grab_select"


def test_no_selection_starts_a_new_round():
    g = make({0: 0, 11: 1})
    g.tick(SELECT_SECONDS)
    assert g.phase == "grab_select" and g.deadline == 2 * SELECT_SECONDS


def test_war_starts_when_no_free_land():
    owner = {r: 0 for r in range(6)} | {r: 1 for r in range(6, 11)}
    g = make(owner)
    assert g.select(1, 11)
    g.tick(SELECT_SECONDS)
    g.answer(1, RIGHT, SELECT_SECONDS + 1)
    g.tick(SELECT_SECONDS + QUESTION_SECONDS)
    assert g.phase == "war_select" and g.attacker == 0


# ---- war -------------------------------------------------------------------

def full_board():
    """Player 0: left half (base 0). Player 1: right half (base 3)."""
    owner = {r: (0 if r % 4 < 2 else 1) for r in range(12)}
    g = ConquestPhase([0, 1], owner, lambda: FAKE_Q, 0.0, board=GRID, interlude=0)
    g.bases = {0: 0, 1: 3}
    return g


def win(g, player, now):
    """`player` answers correctly first; let the reveal for the other run out.
    Returns the time after the reveal."""
    assert g.answer(player, RIGHT, now) == "correct"
    if g.reveal:
        g.tick(now + REVEAL_SECONDS)
        return now + REVEAL_SECONDS
    return now


def start_attack(g, attacker, region, now):
    assert g.phase == "war_select" and g.attacker == attacker
    assert g.select(attacker, region)
    assert not g.select(1 - attacker, region)   # only the attacker selects
    g.tick(now + SELECT_SECONDS)
    assert g.phase == "war_duel"
    return now + SELECT_SECONDS


def test_attack_only_adjacent_enemy_regions():
    g = full_board()
    assert g.phase == "war_select" and g.attacker == 0
    assert g.selectable(0) == [2, 6, 10]
    assert g.selectable(1) == []


def test_attacker_wins_normal_region_then_turn_passes():
    g = full_board()
    t = start_attack(g, 0, 6, 0)
    assert g.answer(0, RIGHT, t + 2) == "correct"
    assert g.owner[6] == 0
    assert g.last_result["attacker_won"] and g.last_result["elapsed"] == 2
    assert g.reveal and g.phase == "war_duel"      # the defender can still answer
    g.tick(t + 2 + REVEAL_SECONDS)
    assert g.phase == "war_select" and g.attacker == 1


def test_defender_quicker_keeps_region():
    g = full_board()
    t = start_attack(g, 0, 6, 0)
    assert g.answer(1, RIGHT, t + 1) == "correct"
    assert g.answer(0, RIGHT, t + 2) == "late"     # right, but slower
    assert g.owner[6] == 1
    assert g.phase == "war_select"                 # both answered: no waiting


def test_both_wrong_or_timeout_defender_holds():
    g = full_board()
    t = start_attack(g, 0, 6, 0)
    g.answer(0, WRONG, t + 1)
    g.answer(1, WRONG, t + 2)
    assert g.owner[6] == 1 and g.attacker == 1
    t = start_attack(g, 1, 1, t + 2)
    g.tick(t + QUESTION_SECONDS)
    assert g.owner[1] == 0 and g.attacker == 0


def test_no_target_skips_turn():
    g = full_board()
    g.tick(SELECT_SECONDS)
    assert (g.last_result["kind"], g.last_result["attacker"]) == ("skip", 0)
    assert g.attacker == 1


def test_base_attack_three_questions_one_tower_each():
    g = full_board()
    g.owner[2] = 0                       # player 0 now borders base 3
    t = start_attack(g, 0, 3, 0)
    assert g.attack["base"]
    t = win(g, 0, t + 1)                 # tower 1 down
    assert g.towers[1] == TOWERS - 1 and g.attack["tower_q"] == 2
    t = win(g, 1, t + 1)                 # defender saves tower 2
    assert g.towers[1] == TOWERS - 1 and g.attack["tower_q"] == 3
    g.tick(t + QUESTION_SECONDS)         # nobody: tower 3 stands
    assert g.towers[1] == 2
    assert g.owner[3] == 1 and g.phase == "war_select" and g.attacker == 1


def test_all_three_towers_in_one_attack_takes_all_land_and_wins():
    g = full_board()
    g.owner[2] = 0
    t = start_attack(g, 0, 3, 0)
    for _ in range(TOWERS):
        t = win(g, 0, t + 1)
    assert g.last_result["base_fell"]
    assert set(g.owner.values()) == {0}
    assert g.phase == "over" and g.winner == 0


def test_towers_stay_destroyed_between_attacks():
    g = full_board()
    g.owner[2] = 0
    g.towers[1] = 1                      # two towers already down earlier
    t = start_attack(g, 0, 3, 0)
    win(g, 0, t + 1)
    assert g.is_done() and g.winner == 0


def test_base_falls_eliminates_only_that_player_with_three():
    owner = {0: 0, 1: 0, 2: 1, 3: 1, 4: 0, 5: 0, 6: 1, 7: 1, 8: 2, 9: 2, 10: 2, 11: 2}
    g = ConquestPhase([0, 1, 2], owner, lambda: FAKE_Q, 0.0, board=GRID, interlude=0)
    g.bases = {0: 0, 1: 3, 2: 11}
    g.towers[2] = 1
    g.attacker = 0                       # make player 1 the next attacker
    g._next_turn(0.0)
    t = start_attack(g, 1, 10, 0)
    assert not g.attack["base"]
    t = win(g, 1, t + 1)
    assert g.owner[10] == 1
    t = start_attack(g, 2, 5, t)         # player 2 attacks player 0
    t = win(g, 0, t + 1)                 # player 0 defends
    assert g.owner[5] == 0 and g.attacker == 0
    g.owner[7] = 0                       # give player 0 a border with base 11
    t = start_attack(g, 0, 11, t)
    win(g, 0, t + 1)                     # last tower falls
    assert 2 not in g.players
    assert g.owner[11] == 0 and g.owner[8] == 0 and g.owner[9] == 0
    assert g.owner[10] == 1              # land taken earlier by player 1 stays
    assert g.phase == "war_select" and g.attacker == 1


def test_answers_never_in_public_state():
    g = full_board()
    t = start_attack(g, 0, 6, 0)
    assert "answer" not in g.public_state(1, t)["question"]


def test_disconnect_frees_land_then_grab_resumes():
    g = full_board()
    g.select(0, 6)
    g.remove_player(1, 1.0)
    assert g.is_done() and g.winner == 0


def test_bots_play_a_full_game_to_the_end():
    owner = {0: 0, 3: 1, 9: 2}
    g = ConquestPhase([0, 1, 2], owner, lambda: FAKE_Q, 0.0, board=GRID, interlude=0)
    bots = [Bot(p, random.Random(p), accuracy=0.5) for p in (0, 1, 2)]
    t = 0.0
    while not g.is_done() and t < 5000:
        g.tick(t)
        for b in bots:
            b.act(g, t)
        t += 0.1
    assert g.is_done()
    assert set(g.owner.values()) == {g.winner} and len(g.owner) == 12


def test_war_slower_correct_answer_is_shown():
    g = full_board()
    t = start_attack(g, 0, 6, 0)
    q = g.question_no
    assert g.answer(1, RIGHT, t + 1.0, q) == "correct"     # defender quicker
    assert g.answer(0, RIGHT, t + 1.4, q) == "late"
    assert g.owner[6] == 1
    answers = g.last_result["answers"]
    assert [(a["player"], a["correct"], a.get("late", False)) for a in answers] == \
        [(1, True, False), (0, True, True)]


def test_siege_late_answer_goes_to_its_own_tower_question():
    g = full_board()
    g.owner[2] = 0
    t = start_attack(g, 0, 3, 0)
    q1 = g.question_no
    g.answer(0, RIGHT, t + 1, q1)                 # tower 1 down; question stays open
    assert g.reveal and g.question_no == q1
    assert g.answer(1, RIGHT, t + 1.5, q1) == "late"   # defender was right, but slower
    assert g.last_result["answers"][-1]["late"]
    assert g.reveal is None                        # both answered: next tower right away
    assert g.question_no != q1
    assert g.attack["tower_q"] == 2 and g.attack["locked_out"] == set()
    assert g.answer(1, RIGHT, t + 2, q1) is None   # old question number is ignored


def test_results_are_numbered():
    g = full_board()
    g.tick(SELECT_SECONDS)
    first = g.last_result["no"]
    g.tick(2 * SELECT_SECONDS)
    assert g.last_result["no"] == first + 1


# ---- the pause between a riddle and choosing again -------------------------

def test_after_a_grab_riddle_the_game_pauses_before_the_next_selection():
    g = ConquestPhase([0, 1], {0: 0, 11: 1}, lambda: FAKE_Q, 0.0, board=GRID, interlude=3)
    g.select(0, 1)
    g.select(1, 10)
    t = SELECT_SECONDS
    g.tick(t)
    g.answer(0, RIGHT, t + 1)
    g.answer(1, RIGHT, t + 2)
    assert g.phase == "interlude" and g.owner[1] == 0
    state = g.public_state(0, t + 2)
    assert state["next"] == {"phase": "grab_select"} and state["remaining"] == 3
    assert g.selectable(0) == [] and not g.select(0, 2)    # no choosing during the pause
    assert not g.tick(t + 4.9)
    assert g.tick(t + 5)
    assert g.phase == "grab_select"
    assert g.deadline == t + 5 + SELECT_SECONDS             # the timer starts after the pause


def test_after_a_war_duel_the_pause_names_the_next_attacker():
    owner = {r: (0 if r % 4 < 2 else 1) for r in range(12)}
    g = ConquestPhase([0, 1], owner, lambda: FAKE_Q, 0.0, board=GRID, interlude=3)
    g.bases = {0: 0, 1: 3}
    g.select(0, 6)
    g.tick(SELECT_SECONDS)
    g.answer(0, WRONG, SELECT_SECONDS + 1)
    g.answer(1, WRONG, SELECT_SECONDS + 2)
    assert g.phase == "interlude"
    assert g.public_state(1, SELECT_SECONDS + 2)["next"] == {"phase": "war_select", "attacker": 1}
    g.tick(SELECT_SECONDS + 5)
    assert g.phase == "war_select" and g.attacker == 1


def test_no_pause_between_siege_questions():
    owner = {r: (0 if r % 4 < 2 else 1) for r in range(12)}
    owner[2] = 0
    g = ConquestPhase([0, 1], owner, lambda: FAKE_Q, 0.0, board=GRID, interlude=3)
    g.bases = {0: 0, 1: 3}
    g.select(0, 3)
    g.tick(SELECT_SECONDS)
    g.answer(0, RIGHT, SELECT_SECONDS + 1)
    g.answer(1, WRONG, SELECT_SECONDS + 1.5)                # both answered: no reveal wait
    assert g.phase == "war_duel" and g.attack["tower_q"] == 2

"""End-to-end over real localhost sockets: lobby, start, hidden picks, duel."""
import time

import pytest

from game import opening
from net.client import GameClient
from net.server import GameServer

PORT = 5599


def wait_for(client, kind, pred=lambda m: True, timeout=3.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        for msg in client.messages():
            if msg.get("t") == kind and pred(msg):
                return msg
        time.sleep(0.02)
    raise AssertionError(f"no {kind} message")


@pytest.fixture
def server(monkeypatch):
    monkeypatch.setattr(opening, "PICK_SECONDS", 0.5)
    s = GameServer("test room", port=PORT)
    s.start()
    yield s
    s.stop()


def test_lobby_pick_and_duel(server):
    a = GameClient("127.0.0.1", PORT, "Ana")
    assert wait_for(a, "welcome")["you"] == 0
    b = GameClient("127.0.0.1", PORT, "Bob")
    assert wait_for(b, "welcome")["you"] == 1
    lobby = wait_for(a, "lobby", lambda m: len(m["players"]) == 2)
    assert lobby["host"] == 0

    b.send({"t": "start"})                     # only the host may start
    time.sleep(0.2)
    assert server.game is None
    a.send({"t": "start"})
    wait_for(b, "state", lambda m: m["phase"] == "pick")

    a.send({"t": "pick", "region": 4})
    b.send({"t": "pick", "region": 4})
    mine = wait_for(a, "state", lambda m: m["your_pick"] == 4)
    assert mine["phase"] == "pick"

    duel = wait_for(b, "state", lambda m: m["phase"] == "duel")["duel"]
    assert duel["region"] == 4 and "answer" not in duel["question"]
    correct = server.game.duel.question["answer"]
    q = duel["question_no"]
    b.send({"t": "answer", "choice": correct, "q": q})
    st = wait_for(a, "state", lambda m: m["last_result"] is not None)
    assert st["last_result"]["winner"] == 1
    assert st["owner"] == {"4": 1}
    assert st["duel"]["reveal"] and st["duel"]["waiting"] == [0]   # Ana can still answer
    a.send({"t": "answer", "choice": correct, "q": q})
    st = wait_for(a, "state", lambda m: m["phase"] == "pick")
    assert st["pickers"] == [0]
    late = st["last_result"]["answers"][-1]
    assert late["player"] == 0 and late["correct"] and late["late"]

    for c in (a, b):
        c.close()


def test_room_full_and_late_join_rejected(server):
    clients = [GameClient("127.0.0.1", PORT, f"P{i}") for i in range(3)]
    for c in clients:
        wait_for(c, "welcome")
    extra = GameClient("127.0.0.1", PORT, "Late")
    assert wait_for(extra, "error")["msg"] == "Room is full"
    for c in clients + [extra]:
        c.close()


def test_host_adds_bot_and_plays_alone(server):
    a = GameClient("127.0.0.1", PORT, "Ana")
    wait_for(a, "welcome")
    a.send({"t": "add_bot"})
    lobby = wait_for(a, "lobby", lambda m: len(m["players"]) == 2)
    assert lobby["players"][1]["bot"] and lobby["host"] == 0
    a.send({"t": "start"})
    wait_for(a, "state", lambda m: m["phase"] == "pick")
    a.send({"t": "pick", "region": 0})
    # The pick round is shortened to 0.5s, so the bot usually misses it and gets
    # a random free region; either way the game must reach "done".
    st = wait_for(a, "state", lambda m: m["phase"] == "done", timeout=8)
    assert st["owner"]["0"] == 0
    assert sorted(st["owner"].values()) == [0, 1]
    a.close()

"""Host-authoritative game server. Runs in background threads on the host machine.

Only the server holds the question answers. Clients get questions without
answers, send back a choice index, and the server judges it.

When the room is created with categories, the server downloads questions
from opentdb.com in the background and keeps them in memory only. Without
internet it falls back to the built-in questions in data/questions.json.
"""
import random
import socket
import threading
import time

from game.bot import Bot
from game.conquest import ConquestPhase
from game.opening import OpeningPhase
from game.questions import QuestionDeck, load_questions
from net import opentdb, protocol

SHOW_START_SECONDS = 3   # how long the starting regions show before the land grab


class GameServer:
    def __init__(self, room_name, port=protocol.GAME_PORT, categories=(), difficulty="any",
                 fetch=opentdb.fetch):
        self.room_name = room_name
        self.port = port
        self.deck = QuestionDeck(load_questions())     # built-in, until online ones arrive
        self.categories = [c for c in categories if c in opentdb.CATEGORIES]
        self.difficulty = difficulty if difficulty in opentdb.DIFFICULTIES else "any"
        self._fetch = fetch
        # "loading" -> "ready" (online questions arrived) or "offline" (built-in only)
        self.questions_status = "loading" if self.categories else "builtin"
        self.online_count = 0
        self.fetch_done = not self.categories
        self.lock = threading.Lock()
        self.clients = {}        # player id -> socket
        self.names = {}          # player id -> name (humans and bots)
        self.bots = {}           # player id -> Bot, played by the server itself
        self.host_id = None
        self.game = None         # OpeningPhase, then ConquestPhase
        self.opening_done_at = None
        self.running = False
        self.sock = None

    # ---- lifecycle -----------------------------------------------------

    def start(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("", self.port))   # raises OSError if the port is taken
        self.sock.listen()
        self.running = True
        threading.Thread(target=self._accept_loop, daemon=True).start()
        threading.Thread(target=self._tick_loop, daemon=True).start()
        if self.categories:
            threading.Thread(target=self._fetch_questions, daemon=True).start()

    def stop(self):
        self.running = False
        try:
            self.sock.close()
        except OSError:
            pass
        with self.lock:
            for s in self.clients.values():
                try:
                    s.close()
                except OSError:
                    pass
            self.clients.clear()

    @property
    def in_lobby(self):
        return self.running and self.game is None

    def player_count(self):
        with self.lock:
            return len(self.names)

    # ---- threads -------------------------------------------------------

    def _accept_loop(self):
        while self.running:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            threading.Thread(target=self._client_loop, args=(conn,), daemon=True).start()

    def _fetch_questions(self):
        """Download questions for the room's categories; nothing is saved."""
        def on_batch(category, batch):
            with self.lock:
                if not batch:
                    return
                if self.online_count == 0:
                    self.deck.replace(batch)       # drop the built-in ones
                else:
                    self.deck.add(batch)
                self.online_count += len(batch)
                self.questions_status = "ready"
                self._broadcast_lobby()
        try:
            self._fetch(self.categories, self.difficulty, random.Random(), on_batch,
                        should_stop=lambda: not self.running)
        except (OSError, ValueError, KeyError):
            pass                                   # offline or a bad reply: keep what we have
        with self.lock:
            self.fetch_done = True
            if self.online_count == 0:
                self.questions_status = "offline"
            self._broadcast_lobby()

    def _tick_loop(self):
        while self.running:
            time.sleep(0.1)
            with self.lock:
                if not self.game:
                    continue
                now = time.monotonic()
                changed = self.game.tick(now)
                changed = self._maybe_start_conquest(now) or changed
                for bot in self.bots.values():
                    changed = bot.act(self.game, now) or changed
                if changed:
                    self._broadcast_state()

    def _maybe_start_conquest(self, now):
        """After the opening, show the starting regions briefly, then begin."""
        if not isinstance(self.game, OpeningPhase) or not self.game.is_done():
            return False
        if self.opening_done_at is None:
            self.opening_done_at = now
            return False
        if now - self.opening_done_at < SHOW_START_SECONDS:
            return False
        self.game = ConquestPhase(self.game.players, self.game.owner, self.deck.draw, now,
                                  board=self.game.board)
        return True

    def _client_loop(self, conn):
        pid = None
        for msg in protocol.read_messages(conn):
            with self.lock:
                if pid is None:
                    pid = self._handle_hello(conn, msg)
                    if pid is None:
                        break
                else:
                    self._handle(pid, msg)
        with self.lock:
            if pid is not None:
                self._drop(pid)
        try:
            conn.close()
        except OSError:
            pass

    # ---- message handling (called with self.lock held) ----------------

    def _handle_hello(self, conn, msg):
        if msg.get("t") != "hello":
            return None
        name = str(msg.get("name", "")).strip()[:16] or "Player"
        if self.game is not None:
            self._safe_send(conn, {"t": "error", "msg": "Game already started"})
            return None
        free = [i for i in range(protocol.MAX_PLAYERS) if i not in self.names]
        if not free:
            self._safe_send(conn, {"t": "error", "msg": "Room is full"})
            return None
        pid = free[0]
        self.clients[pid] = conn
        self.names[pid] = name
        if self.host_id is None:
            self.host_id = pid
        self._safe_send(conn, {"t": "welcome", "you": pid})
        self._broadcast_lobby()
        return pid

    def _handle(self, pid, msg):
        kind = msg.get("t")
        now = time.monotonic()
        if kind == "start" and pid == self.host_id and self.game is None:
            if len(self.names) >= protocol.MIN_PLAYERS and self.questions_status != "loading":
                self.game = OpeningPhase(sorted(self.names), self.deck.draw, now)
                self._broadcast_lobby()
                self._broadcast_state()
        elif kind == "add_bot" and pid == self.host_id and self.game is None:
            free = [i for i in range(protocol.MAX_PLAYERS) if i not in self.names]
            if free:
                n = len(self.bots) + 1
                self.names[free[0]] = "Bot" if n == 1 else f"Bot {n}"
                self.bots[free[0]] = Bot(free[0])
                self._broadcast_lobby()
        elif kind == "remove_bot" and pid == self.host_id and self.game is None:
            if self.bots:
                bot_id = max(self.bots)
                del self.bots[bot_id]
                del self.names[bot_id]
                self._broadcast_lobby()
        elif kind == "pick" and self.game:
            if self.game.select(pid, msg.get("region"), now):
                if self.game.picks_visible:
                    self._broadcast_state()
                else:
                    self._send_state(pid)   # hidden picks: only the picker hears back
        elif kind == "answer" and self.game:
            if self.game.answer(pid, msg.get("choice"), now, msg.get("q")) is not None:
                self._broadcast_state()

    def _drop(self, pid):
        self.clients.pop(pid, None)
        self.names.pop(pid, None)
        if self.game:
            self.game.remove_player(pid, time.monotonic())
            self._broadcast_lobby()
            self._broadcast_state()
        else:
            if pid == self.host_id:
                humans = [i for i in self.names if i not in self.bots]
                self.host_id = min(humans) if humans else None
            self._broadcast_lobby()

    # ---- sending -------------------------------------------------------

    def _lobby_msg(self):
        return {"t": "lobby", "room": self.room_name, "host": self.host_id,
                "started": self.game is not None,
                "players": [{"id": i, "name": n, "bot": i in self.bots}
                            for i, n in sorted(self.names.items())],
                "questions": {"categories": self.categories, "difficulty": self.difficulty,
                              "status": self.questions_status, "count": len(self.deck),
                              "loading": not self.fetch_done}}

    def _broadcast_lobby(self):
        msg = self._lobby_msg()
        for s in list(self.clients.values()):
            self._safe_send(s, msg)

    def _send_state(self, pid):
        state = self.game.public_state(pid, time.monotonic())
        self._safe_send(self.clients.get(pid), {"t": "state", **state})

    def _broadcast_state(self):
        for pid in list(self.clients):
            self._send_state(pid)

    @staticmethod
    def _safe_send(sock, msg):
        if sock is None:
            return
        try:
            protocol.send(sock, msg)
        except OSError:
            pass

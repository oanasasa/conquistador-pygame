"""One scene per screen. Scenes read shared state from the App and send
player actions through it; they never judge answers themselves."""
import pygame

from net import protocol
from ui.widgets import (BG, GRAY, HEIGHT, MARGIN, PLAYER_COLORS, WHITE, WIDTH,
                        Button, TextInput, draw_board, region_at, text)

ANSWER_KEYS = [pygame.K_1, pygame.K_2, pygame.K_3]


class Scene:
    def __init__(self, app):
        self.app = app

    def handle(self, event):
        pass

    def draw(self, screen):
        pass

    def draw_error(self, screen):
        if self.app.error:
            text(screen, self.app.error, (MARGIN, HEIGHT - 40), (255, 120, 120), size=26)


class NameEntry(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.input = TextInput((WIDTH // 2 - 160, 260, 320, 44), placeholder="your name")
        self.ok = Button((WIDTH // 2 - 80, 330, 160, 44), "Continue")

    def handle(self, event):
        entered = self.input.handle(event) or self.ok.clicked(event)
        if entered and self.input.value.strip():
            self.app.set_name(self.input.value.strip())

    def draw(self, screen):
        screen.fill(BG)
        text(screen, "CONQUISTADOR", (WIDTH // 2, 140), size=64, center=True)
        text(screen, "Choose a username", (WIDTH // 2, 220), GRAY, center=True)
        self.ok.enabled = bool(self.input.value.strip())
        self.input.draw(screen)
        self.ok.draw(screen)


class Lobby(Scene):
    """Browse LAN rooms, create one, or join by IP."""

    def __init__(self, app):
        super().__init__(app)
        self.create = Button((MARGIN, 90, 220, 44), "Create room")
        self.solo = Button((MARGIN + 240, 90, 220, 44), "Play vs bot")
        self.ip = TextInput((MARGIN, HEIGHT - 120, 260, 44), placeholder="host IP, e.g. 192.168.1.5",
                            max_len=40)
        self.ip.active = False
        self.join_ip = Button((MARGIN + 270, HEIGHT - 120, 140, 44), "Join IP")
        self.room_buttons = []

    def handle(self, event):
        if self.create.clicked(event):
            self.app.create_room()
            return
        if self.solo.clicked(event):
            self.app.create_room(with_bot=True)
            return
        if (self.ip.handle(event) or self.join_ip.clicked(event)) and self.ip.value.strip():
            self.app.join(self.ip.value.strip(), protocol.GAME_PORT)
            return
        for button, room in self.room_buttons:
            if button.clicked(event):
                self.app.join(room["ip"], room["port"])
                return

    def draw(self, screen):
        screen.fill(BG)
        text(screen, f"Hi {self.app.name}!", (MARGIN, 20), size=42)
        self.create.draw(screen)
        self.solo.draw(screen, (60, 140, 80))
        text(screen, "Rooms on your network:", (MARGIN, 160), GRAY)
        rooms = self.app.browser.list_rooms() if self.app.browser else []
        self.room_buttons = []
        if not rooms:
            text(screen, "No rooms found yet...", (MARGIN + 20, 200), GRAY, size=26)
        for i, room in enumerate(rooms[:5]):
            y = 195 + i * 50
            full = room["players"] >= room["max"]
            text(screen, f"{room['room']}  ({room['ip']})  {room['players']}/{room['max']}",
                 (MARGIN + 20, y + 10))
            b = Button((WIDTH - MARGIN - 120, y, 120, 40), "Full" if full else "Join", not full)
            b.draw(screen)
            self.room_buttons.append((b, room))
        text(screen, "Or join by IP:", (MARGIN, HEIGHT - 150), GRAY, size=26)
        self.ip.draw(screen)
        self.join_ip.enabled = bool(self.ip.value.strip())
        self.join_ip.draw(screen)
        if self.app.local_ip:
            text(screen, f"Your IP: {self.app.local_ip}", (WIDTH - 260, HEIGHT - 110), GRAY, size=26)
        self.draw_error(screen)


class Room(Scene):
    """Waiting room: player list, host starts the game."""

    def __init__(self, app):
        super().__init__(app)
        self.start = Button((MARGIN, 400, 200, 50), "Start")
        self.leave = Button((MARGIN + 220, 400, 160, 50), "Leave")
        self.add_bot = Button((MARGIN + 400, 400, 160, 50), "Add bot")
        self.remove_bot = Button((MARGIN + 580, 400, 180, 50), "Remove bot")

    def handle(self, event):
        if self.start.clicked(event):
            self.app.send({"t": "start"})
        elif self.leave.clicked(event):
            self.app.leave()
        elif self.add_bot.clicked(event):
            self.app.send({"t": "add_bot"})
        elif self.remove_bot.clicked(event):
            self.app.send({"t": "remove_bot"})

    def draw(self, screen):
        screen.fill(BG)
        lobby = self.app.lobby or {}
        text(screen, lobby.get("room", "Connecting..."), (MARGIN, 20), size=48)
        if self.app.server:
            text(screen, f"Others can join at {self.app.local_ip}", (MARGIN, 70), GRAY, size=26)
        players = lobby.get("players", [])
        for i, p in enumerate(players):
            y = 120 + i * 50
            pygame.draw.rect(screen, PLAYER_COLORS[p["id"]], (MARGIN, y, 36, 36), border_radius=6)
            tag = []
            if p["id"] == lobby.get("host"):
                tag.append("host")
            if p["id"] == self.app.you:
                tag.append("you")
            if p.get("bot"):
                tag.append("computer")
            label = p["name"] + (f"  ({', '.join(tag)})" if tag else "")
            text(screen, label, (MARGIN + 50, y + 8))
        is_host = self.app.you is not None and self.app.you == lobby.get("host")
        if is_host:
            self.start.enabled = len(players) >= protocol.MIN_PLAYERS
            self.start.draw(screen, (60, 140, 80))
            self.add_bot.enabled = len(players) < protocol.MAX_PLAYERS
            self.add_bot.draw(screen)
            self.remove_bot.enabled = any(p.get("bot") for p in players)
            self.remove_bot.draw(screen)
            if not self.start.enabled:
                text(screen, "Waiting for another player, or add a bot to play alone.",
                     (MARGIN, 470), GRAY, size=26)
        else:
            text(screen, "Waiting for the host to start...", (MARGIN, 470), GRAY, size=26)
        self.leave.draw(screen, (120, 70, 70))
        self.draw_error(screen)


YELLOW = (255, 210, 60)
RED_TEXT = (255, 120, 120)


def result_line(app):
    """One line describing what just happened, for any stage."""
    res = app.state.get("last_result") if app.state else None
    if not res:
        return None
    name = app.player_name
    kind = res.get("kind")
    if kind is None:                                  # opening duel
        if res.get("elapsed") is None:
            return f"{name(res['winner'])} took region {res['region'] + 1}"
        return f"{name(res['winner'])} won region {res['region'] + 1} (answered in {res['elapsed']:.1f}s)"
    if kind == "grab":
        parts = [f"{name(int(p))} took region {r + 1}" for p, r in res["won"].items()]
        parts += [f"{name(p)} missed" for p in res["missed"]]
        return ". ".join(parts) + "." if parts else None
    if kind == "skip":
        return f"{name(res['attacker'])} didn't attack."
    att, dfn, region = name(res["attacker"]), name(res["defender"]), res["region"] + 1
    speed = f" ({res['elapsed']:.1f}s)" if res.get("elapsed") is not None else ""
    if res.get("base_fell"):
        return f"{dfn}'s base fell! {att} takes all of {dfn}'s land."
    if res["base"]:
        if res["attacker_won"]:
            return f"{att} destroyed a tower of {dfn}'s base{speed}. Towers left: {res['towers_left']}."
        return f"{dfn}'s tower holds. Towers left: {res['towers_left']}."
    if res["attacker_won"]:
        return f"{att} took region {region} from {dfn}{speed}."
    return f"{dfn} held region {region}."


def owner_map(state):
    return {int(r): p for r, p in state.get("owner", {}).items()}


def bases_map(state):
    """{base region: towers left} for the board."""
    towers = state.get("towers", {})
    return {r: towers.get(p, 0) for p, r in state.get("bases", {}).items()}


def draw_timer(screen, app, size=48):
    text(screen, f"{app.remaining():0.0f}s", (WIDTH - MARGIN - 70, 15), WHITE, size=size)


def draw_result(screen, app, y=100):
    line = result_line(app)
    if line:
        text(screen, line, (MARGIN, y), YELLOW, size=26)


# ---- opening ---------------------------------------------------------------

class MapPick(Scene):
    """15-second hidden pick. Ends early once everyone has picked."""

    def handle(self, event):
        st = self.app.state
        if (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                and self.app.you in st["pickers"]):
            r = region_at(event.pos)
            if r is not None and r not in owner_map(st):
                self.app.send({"t": "pick", "region": r})

    def draw(self, screen):
        st = self.app.state
        screen.fill(BG)
        me = self.app.you
        if me in st["pickers"]:
            text(screen, "Pick your starting region!", (MARGIN, 15), PLAYER_COLORS[me], size=42)
            hint = ("Picks are secret. The round ends when everyone has picked."
                    if st["your_pick"] is None else
                    f"You picked region {st['your_pick'] + 1}. Waiting for the others...")
            text(screen, hint, (MARGIN, 60), GRAY, size=26)
        else:
            names = ", ".join(self.app.player_name(p) for p in st["pickers"])
            text(screen, f"Waiting for {names} to pick a region...", (MARGIN, 15), size=36)
        draw_timer(screen, self.app)
        draw_result(screen, self.app)
        draw_board(screen, owner_map(st), my_pick=st["your_pick"],
                   my_color=PLAYER_COLORS[me] if me is not None else WHITE)


class QuestionScene(Scene):
    """Shared layout for every question: text, three answer buttons (or keys
    1-3), a status line and the board. The server judges the answer."""

    def __init__(self, app):
        super().__init__(app)
        self.buttons = [Button((MARGIN + i * 290, 65, 270, 40), "") for i in range(3)]

    # subclasses provide these
    def question(self):
        raise NotImplementedError

    def may_answer(self):
        raise NotImplementedError

    def status(self):
        raise NotImplementedError

    def draw_map(self, screen):
        raise NotImplementedError

    def can_answer(self):
        return self.may_answer() and self.app.answered_q != self.app.question_token()

    def handle(self, event):
        if not self.can_answer():
            return
        choices = self.question()["choices"]
        for i, b in enumerate(self.buttons[:len(choices)]):
            pressed = event.type == pygame.KEYDOWN and event.key == ANSWER_KEYS[i]
            if pressed or b.clicked(event):
                self.app.answer(i)
                return

    def draw(self, screen):
        screen.fill(BG)
        q = self.question()
        text(screen, q["q"], (MARGIN, 15), size=38)
        active = self.can_answer()
        for i, (b, choice) in enumerate(zip(self.buttons, q["choices"])):
            b.label = f"{i + 1}) {choice}"
            b.enabled = active
            b.draw(screen)
        text(screen, f"{self.app.remaining():0.0f}s", (WIDTH - MARGIN - 50, 15), WHITE, size=40)
        msg, color = self.status()
        text(screen, msg, (MARGIN, 118), color, size=26)
        self.draw_map(screen)


class Duel(QuestionScene):
    """Opening bonus question for a contested region. Quickest correct answer
    wins. Players not in the duel watch but cannot answer."""

    def question(self):
        return self.app.state["duel"]["question"]

    def may_answer(self):
        duel = self.app.state["duel"]
        return self.app.you in duel["players"] and self.app.you not in duel["locked_out"]

    def status(self):
        duel = self.app.state["duel"]
        me = self.app.you
        region = duel["region"] + 1
        if me in duel["players"]:
            if me in duel["locked_out"]:
                return "Wrong! You're locked out of this question.", RED_TEXT
            if not self.can_answer():
                return "Answer sent...", GRAY
            return f"Bonus question for region {region}: fastest correct answer wins! (1-3)", YELLOW
        fighters = " vs ".join(self.app.player_name(p) for p in duel["players"])
        return f"{fighters} are fighting for region {region}. You're watching.", GRAY

    def draw_map(self, screen):
        st = self.app.state
        draw_board(screen, owner_map(st), contested=st["duel"]["region"])


class Done(Scene):
    def draw(self, screen):
        st = self.app.state
        screen.fill(BG)
        text(screen, "Starting regions are set!", (MARGIN, 15), size=42)
        owners = owner_map(st)
        parts = [f"{self.app.player_name(p)}: region {r + 1}"
                 for r, p in sorted(owners.items(), key=lambda kv: kv[1])]
        text(screen, "   ".join(parts), (MARGIN, 60), GRAY, size=26)
        text(screen, "These are your bases. The land grab begins...", (MARGIN, 100), YELLOW, size=26)
        draw_board(screen, owners, bases={r: 3 for r in owners})


# ---- land grab -------------------------------------------------------------

def conquest_board(screen, app, **extra):
    st = app.state
    draw_board(screen, owner_map(st), bases=bases_map(st), **extra)


class GrabSelect(Scene):
    """Fixed 10 seconds to select a free region next to your land. Selections
    are visible; the first to select a region locks it."""

    def handle(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            r = region_at(event.pos)
            if r is not None and r in self.app.state["selectable"]:
                self.app.send({"t": "pick", "region": r})

    def draw(self, screen):
        st = self.app.state
        me = self.app.you
        screen.fill(BG)
        mine = st["selections"].get(str(me))
        if st["selectable"] or mine is not None:
            text(screen, "Land grab: choose a free region next to your land",
                 (MARGIN, 15), PLAYER_COLORS[me], size=36)
            hint = ("Faded tiles are locked by other players. You can change your choice."
                    if mine is None else
                    f"You chose region {mine + 1}. A question follows when the time is up.")
        else:
            text(screen, "Land grab", (MARGIN, 15), size=36)
            hint = "No free region next to your land. Waiting for the others..."
        text(screen, hint, (MARGIN, 60), GRAY, size=26)
        draw_timer(screen, self.app)
        draw_result(screen, self.app)
        locked = {r: int(p) for p, r in st["selections"].items()}
        conquest_board(screen, self.app, selections=locked, selectable=st["selectable"],
                       my_pick=mine, my_color=PLAYER_COLORS[me])


class GrabQuestion(QuestionScene):
    """Everyone who selected a region answers; each correct player takes it."""

    def question(self):
        return self.app.state["question"]

    def may_answer(self):
        st = self.app.state
        return self.app.you in st["answering"] and self.app.you not in st["answered"]

    def status(self):
        st = self.app.state
        me = self.app.you
        waiting = [self.app.player_name(p) for p in st["answering"] if p not in st["answered"]]
        if me in st["answering"]:
            if self.can_answer():
                region = st["selections"][str(me)] + 1
                return f"Answer correctly to take region {region}! (1-3)", YELLOW
            if waiting:
                return f"Answer sent. Waiting for {', '.join(waiting)}...", GRAY
            return "Answer sent...", GRAY
        return "You didn't choose a region this round. You're watching.", GRAY

    def draw_map(self, screen):
        st = self.app.state
        locked = {r: int(p) for p, r in st["selections"].items()}
        mine = st["selections"].get(str(self.app.you))
        conquest_board(screen, self.app, selections=locked, my_pick=mine,
                       my_color=PLAYER_COLORS[self.app.you])


# ---- war -------------------------------------------------------------------

class WarSelect(Scene):
    """The attacker has a fixed 10 seconds to choose an adjacent enemy region."""

    def handle(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            r = region_at(event.pos)
            if r is not None and r in self.app.state["selectable"]:
                self.app.send({"t": "pick", "region": r})

    def draw(self, screen):
        st = self.app.state
        me = self.app.you
        attacker = st["attacker"]
        target = st["selections"].get(str(attacker))
        screen.fill(BG)
        if attacker == me:
            text(screen, "Your turn: attack a region next to your land",
                 (MARGIN, 15), PLAYER_COLORS[me], size=36)
            hint = ("Attacking a base starts a 3-tower siege." if target is None else
                    f"Target: region {target + 1}. You can change it until the time is up.")
        else:
            text(screen, f"{self.app.player_name(attacker)} is choosing a target...",
                 (MARGIN, 15), PLAYER_COLORS[attacker], size=36)
            hint = ("" if target is None else
                    f"Target: region {target + 1} ({self.app.player_name(owner_map(st)[target])})")
        text(screen, hint, (MARGIN, 60), GRAY, size=26)
        draw_timer(screen, self.app)
        draw_result(screen, self.app)
        conquest_board(screen, self.app, selectable=st["selectable"], contested=target)


class WarDuel(QuestionScene):
    """Attacker vs defender; quickest correct answer wins. Others watch."""

    def question(self):
        return self.app.state["question"]

    def fighters(self):
        st = self.app.state
        return st["attacker"], st["attack"]["defender"]

    def may_answer(self):
        me = self.app.you
        return me in self.fighters() and me not in self.app.state["attack"]["locked_out"]

    def status(self):
        st = self.app.state
        a = st["attack"]
        me = self.app.you
        att, dfn = (self.app.player_name(p) for p in self.fighters())
        if a["base"]:
            towers = st["towers"].get(str(a["defender"]), 0)
            what = f"{att} attacks {dfn}'s base: question {a['tower_q']} of 3, towers left {towers}"
        else:
            what = f"{att} attacks {dfn}'s region {a['region'] + 1}"
        if me in self.fighters():
            if me in a["locked_out"]:
                return "Wrong! You're locked out of this question.", RED_TEXT
            if not self.can_answer():
                return "Answer sent...", GRAY
            return what + ". Fastest correct answer wins! (1-3)", YELLOW
        return what + ". You're watching.", GRAY

    def draw_map(self, screen):
        conquest_board(screen, self.app, contested=self.app.state["attack"]["region"])


class GameOver(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.leave = Button((WIDTH - MARGIN - 200, 60, 200, 44), "Back to lobby")

    def handle(self, event):
        if self.leave.clicked(event):
            self.app.leave()

    def draw(self, screen):
        st = self.app.state
        winner = st["winner"]
        screen.fill(BG)
        if winner is None:
            text(screen, "Game over", (MARGIN, 15), size=48)
        else:
            text(screen, f"{self.app.player_name(winner)} conquers the map!", (MARGIN, 15),
                 PLAYER_COLORS[winner], size=48)
        draw_result(screen, self.app, y=70)
        self.leave.draw(screen)
        conquest_board(screen, self.app)

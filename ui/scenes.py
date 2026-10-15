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
        self.ip = TextInput((MARGIN, HEIGHT - 120, 260, 44), placeholder="host IP, e.g. 192.168.1.5",
                            max_len=40)
        self.ip.active = False
        self.join_ip = Button((MARGIN + 270, HEIGHT - 120, 140, 44), "Join IP")
        self.room_buttons = []

    def handle(self, event):
        if self.create.clicked(event):
            self.app.create_room()
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

    def handle(self, event):
        if self.start.clicked(event):
            self.app.send({"t": "start"})
        elif self.leave.clicked(event):
            self.app.leave()

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
            label = p["name"] + (f"  ({', '.join(tag)})" if tag else "")
            text(screen, label, (MARGIN + 50, y + 8))
        is_host = self.app.you is not None and self.app.you == lobby.get("host")
        if is_host:
            self.start.enabled = len(players) >= protocol.MIN_PLAYERS
            self.start.draw(screen, (60, 140, 80))
            if not self.start.enabled:
                text(screen, "Waiting for at least one more player...", (MARGIN, 470), GRAY, size=26)
        else:
            text(screen, "Waiting for the host to start...", (MARGIN, 470), GRAY, size=26)
        self.leave.draw(screen, (120, 70, 70))
        self.draw_error(screen)


def result_line(app):
    res = app.state.get("last_result") if app.state else None
    if not res:
        return None
    who = app.player_name(res["winner"])
    if res.get("elapsed") is None:
        return f"{who} took region {res['region'] + 1}"
    return f"{who} won region {res['region'] + 1} (answered in {res['elapsed']:.1f}s)"


def owner_map(state):
    return {int(r): p for r, p in state.get("owner", {}).items()}


class MapPick(Scene):
    """15-second hidden pick. Click a free region; you may change it until time runs out."""

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
        remaining = self.app.remaining()
        if me in st["pickers"]:
            text(screen, "Pick your starting region!", (MARGIN, 15), PLAYER_COLORS[me], size=42)
            hint = ("Picks are secret. You can change yours until the timer ends."
                    if st["your_pick"] is None else
                    f"You picked region {st['your_pick'] + 1}. Click another to change.")
            text(screen, hint, (MARGIN, 60), GRAY, size=26)
        else:
            names = ", ".join(self.app.player_name(p) for p in st["pickers"])
            text(screen, f"Waiting for {names} to pick a region...", (MARGIN, 15), size=36)
        text(screen, f"{remaining:0.0f}s", (WIDTH - MARGIN - 70, 15), WHITE, size=48)
        line = result_line(self.app)
        if line:
            text(screen, line, (MARGIN, 100), (255, 210, 60), size=26)
        draw_board(screen, owner_map(st), my_pick=st["your_pick"],
                   my_color=PLAYER_COLORS[me] if me is not None else WHITE)


class Duel(Scene):
    """Bonus question for a contested region. Quickest correct answer wins.
    Players not in the duel watch but cannot answer."""

    def __init__(self, app):
        super().__init__(app)
        self.buttons = [Button((MARGIN + i * 290, 65, 270, 40), "") for i in range(3)]

    def can_answer(self):
        duel = self.app.state["duel"]
        me = self.app.you
        return (me in duel["players"] and me not in duel["locked_out"]
                and self.app.answered_q != duel["question_no"])

    def handle(self, event):
        if not self.can_answer():
            return
        choices = self.app.state["duel"]["question"]["choices"]
        for i, b in enumerate(self.buttons[:len(choices)]):
            pressed = event.type == pygame.KEYDOWN and event.key == ANSWER_KEYS[i]
            if pressed or b.clicked(event):
                self.app.answer(i)
                return

    def draw(self, screen):
        st = self.app.state
        duel = st["duel"]
        me = self.app.you
        screen.fill(BG)
        q = duel["question"]
        text(screen, q["q"], (MARGIN, 15), size=38)
        active = self.can_answer()
        for i, (b, choice) in enumerate(zip(self.buttons, q["choices"])):
            b.label = f"{i + 1}) {choice}"
            b.enabled = active
            b.draw(screen)
        text(screen, f"{self.app.remaining():0.0f}s", (WIDTH - MARGIN - 50, 15), WHITE, size=40)

        fighters = " vs ".join(self.app.player_name(p) for p in duel["players"])
        region = duel["region"] + 1
        if me in duel["players"]:
            if me in duel["locked_out"]:
                msg, color = "Wrong! You're locked out of this question.", (255, 120, 120)
            elif not active:
                msg, color = "Answer sent...", GRAY
            else:
                msg, color = f"Bonus question for region {region}: fastest correct answer wins! (1-3)", (255, 210, 60)
        else:
            msg, color = f"{fighters} are fighting for region {region}. You're watching.", GRAY
        text(screen, msg, (MARGIN, 118), color, size=26)
        draw_board(screen, owner_map(st), contested=duel["region"])


class Done(Scene):
    def draw(self, screen):
        st = self.app.state
        screen.fill(BG)
        text(screen, "Starting regions are set!", (MARGIN, 15), size=42)
        owners = owner_map(st)
        parts = [f"{self.app.player_name(p)}: region {r + 1}"
                 for r, p in sorted(owners.items(), key=lambda kv: kv[1])]
        text(screen, "   ".join(parts), (MARGIN, 60), GRAY, size=26)
        text(screen, "The fight begins... (coming next)", (MARGIN, 100), (255, 210, 60), size=26)
        draw_board(screen, owners)


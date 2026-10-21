"""One scene per screen. Scenes read shared state from the App and send
player actions through it; they never judge answers themselves."""
import pygame

from net import protocol
from ui.widgets import (BOARD_TOP, GOLD, GRAY, HEIGHT, INK, INK_SOFT, MARGIN, PARCH_DARK,
                        PLAYER_COLORS, WHITE, WIDTH, WOOD_GREEN, WOOD_RED, Button, TextInput,
                        dim, draw_background, draw_board, draw_mark, draw_panel, draw_seal,
                        draw_shield, ease_out_back, fit_text, font, leather, region_at,
                        region_name, text, timer_color, wrap_text)
from ui.widgets import draw_timer as timer_ring

ANSWER_KEYS = [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4]

# Text colors on the leather background
YELLOW = GOLD
RED_TEXT = (226, 122, 98)
GREEN_TEXT = (164, 204, 120)
# The same meanings, darker, for text on parchment
ON_PARCHMENT = {YELLOW: (128, 80, 16), GRAY: INK_SOFT, RED_TEXT: (150, 40, 30),
                GREEN_TEXT: (60, 100, 40), WHITE: INK}


def flourish(screen, center, width, color=GOLD):
    """A decorative rule with a diamond in the middle, for titles."""
    x, y = center
    pygame.draw.line(screen, color, (x - width // 2, y), (x - 10, y), 1)
    pygame.draw.line(screen, color, (x + 10, y), (x + width // 2, y), 1)
    pygame.draw.polygon(screen, color, [(x - 6, y), (x, y - 5), (x + 6, y), (x, y + 5)])


class Scene:
    def __init__(self, app):
        self.app = app

    def handle(self, event):
        pass

    def draw(self, screen):
        pass

    def draw_error(self, screen):
        if self.app.error:
            text(screen, self.app.error, (MARGIN, HEIGHT - 34), RED_TEXT, size=26)


class NameEntry(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.input = TextInput((WIDTH // 2 - 160, 300, 320, 46), placeholder="your name")
        self.ok = Button((WIDTH // 2 - 90, 372, 180, 46), "Continue")

    def handle(self, event):
        entered = self.input.handle(event) or self.ok.clicked(event)
        if entered and self.input.value.strip():
            self.app.set_name(self.input.value.strip())

    def draw(self, screen):
        draw_background(screen)
        text(screen, "Conquistador", (WIDTH // 2, 110), GOLD, size=86, center=True, bold=True)
        flourish(screen, (WIDTH // 2, 158), 420)
        text(screen, "A game of wits and conquest", (WIDTH // 2, 184), GRAY, size=30,
             center=True, italic=True)
        draw_panel(screen, (WIDTH // 2 - 200, 222, 400, 220), header="Who rides to battle?")
        text(screen, "Choose your name", (WIDTH // 2 - 160, 274), INK_SOFT, size=26, italic=True)
        self.ok.enabled = bool(self.input.value.strip())
        self.input.draw(screen)
        self.ok.draw(screen, WOOD_GREEN)
        text(screen, "Questions from the Open Trivia Database (opentdb.com), CC BY-SA 4.0",
             (WIDTH // 2, HEIGHT - 24), GRAY, size=22, center=True, italic=True)


class Lobby(Scene):
    """Browse LAN rooms, create one, or join by IP."""

    def __init__(self, app):
        super().__init__(app)
        self.create = Button((MARGIN, 84, 220, 46), "Create room")
        self.solo = Button((MARGIN + 240, 84, 220, 46), "Play vs bot")
        self.ip = TextInput((MARGIN, HEIGHT - 96, 300, 46), placeholder="host IP, e.g. 192.168.1.5",
                            max_len=40)
        self.ip.active = False
        self.join_ip = Button((MARGIN + 316, HEIGHT - 96, 150, 46), "Join IP")
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
        draw_background(screen)
        text(screen, f"Hail, {self.app.name}!", (MARGIN, 18), GOLD, size=48, bold=True)
        self.create.draw(screen)
        self.solo.draw(screen, WOOD_GREEN)
        panel = draw_panel(screen, (MARGIN, 152, WIDTH - 2 * MARGIN, 290),
                           header="Rooms on your network")
        rooms = self.app.browser.list_rooms() if self.app.browser else []
        self.room_buttons = []
        if not rooms:
            text(screen, "No rooms found yet... create one, or ask the host for their IP.",
                 (panel.x + 24, panel.y + 66), INK_SOFT, size=26, italic=True)
        for i, room in enumerate(rooms[:4]):
            y = panel.y + 56 + i * 54
            full = room["players"] >= room["max"]
            text(screen, room["room"], (panel.x + 24, y + 8), INK, size=30, bold=True)
            text(screen, f"{room['ip']}   ·   {room['players']}/{room['max']} players",
                 (panel.x + 300, y + 12), INK_SOFT, size=24, italic=True)
            b = Button((panel.right - 150, y, 126, 42), "Full" if full else "Join", not full)
            b.draw(screen)
            self.room_buttons.append((b, room))
            pygame.draw.line(screen, PARCH_DARK, (panel.x + 20, y + 50), (panel.right - 20, y + 50), 1)
        text(screen, "Or join by IP:", (MARGIN, HEIGHT - 128), GRAY, size=26, italic=True)
        self.ip.draw(screen)
        self.join_ip.enabled = bool(self.ip.value.strip())
        self.join_ip.draw(screen)
        if self.app.local_ip:
            text(screen, f"Your IP: {self.app.local_ip}", (WIDTH - 250, HEIGHT - 84), GRAY, size=26)
        self.draw_error(screen)


class Room(Scene):
    """Waiting room: player list, host starts the game."""

    def __init__(self, app):
        super().__init__(app)
        y = 420
        self.start = Button((MARGIN, y, 190, 50), "Start")
        self.add_bot = Button((MARGIN + 206, y, 170, 50), "Add bot")
        self.remove_bot = Button((MARGIN + 392, y, 190, 50), "Remove bot")
        self.leave = Button((WIDTH - MARGIN - 160, y, 160, 50), "Leave")

    def handle(self, event):
        lobby = self.app.lobby or {}
        is_host = self.app.you is not None and self.app.you == lobby.get("host")
        if is_host and self.start.clicked(event):
            self.app.send({"t": "start"})
        elif self.leave.clicked(event):
            self.app.leave()
        elif is_host and self.add_bot.clicked(event):
            self.app.send({"t": "add_bot"})
        elif is_host and self.remove_bot.clicked(event):
            self.app.send({"t": "remove_bot"})

    def draw(self, screen):
        draw_background(screen)
        lobby = self.app.lobby or {}
        text(screen, lobby.get("room", "Connecting..."), (MARGIN, 18), GOLD, size=52, bold=True)
        if self.app.server:
            text(screen, f"Others can join at {self.app.local_ip}", (MARGIN, 70), GRAY, size=26,
                 italic=True)
        panel = draw_panel(screen, (MARGIN, 110, 560, 280), header="The company")
        players = lobby.get("players", [])
        for i, p in enumerate(players):
            y = panel.y + 66 + i * 62
            draw_shield(screen, (panel.x + 40, y + 14), PLAYER_COLORS[p["id"]], size=14)
            tag = []
            if p["id"] == lobby.get("host"):
                tag.append("host")
            if p["id"] == self.app.you:
                tag.append("you")
            if p.get("bot"):
                tag.append("computer")
            r = text(screen, p["name"], (panel.x + 72, y), INK, size=34, bold=True)
            if tag:
                text(screen, ", ".join(tag), (r.right + 14, y + 8), INK_SOFT, size=24, italic=True)
        for i in range(len(players), protocol.MAX_PLAYERS):
            y = panel.y + 66 + i * 62
            text(screen, "an empty seat...", (panel.x + 72, y + 4), PARCH_DARK, size=28, italic=True)
        is_host = self.app.you is not None and self.app.you == lobby.get("host")
        if is_host:
            self.start.enabled = len(players) >= protocol.MIN_PLAYERS
            self.start.draw(screen, WOOD_GREEN)
            self.add_bot.enabled = len(players) < protocol.MAX_PLAYERS
            self.add_bot.draw(screen)
            self.remove_bot.enabled = any(p.get("bot") for p in players)
            self.remove_bot.draw(screen)
            if not self.start.enabled:
                text(screen, "Waiting for another player, or add a bot to play alone.",
                     (MARGIN, 486), GRAY, size=26, italic=True)
        else:
            text(screen, "Waiting for the host to start...", (MARGIN, 486), GRAY, size=26,
                 italic=True)
        self.leave.draw(screen, WOOD_RED)
        self.draw_error(screen)


def result_line(app):
    """One line describing what just happened, for any stage."""
    res = app.state.get("last_result") if app.state else None
    if not res:
        return None
    name = app.player_name
    kind = res.get("kind")
    if kind is None:                                  # opening duel
        if res.get("elapsed") is None:
            return f"{name(res['winner'])} took {region_name(res['region'])}"
        return f"{name(res['winner'])} won {region_name(res['region'])} (answered in {res['elapsed']:.1f}s)"
    if kind == "grab":
        parts = [f"{name(int(p))} took {region_name(r)}" for p, r in res["won"].items()]
        parts += [f"{name(p)} missed" for p in res["missed"]]
        return ". ".join(parts) + "." if parts else None
    if kind == "skip":
        return f"{name(res['attacker'])} didn't attack."
    att, dfn, region = name(res["attacker"]), name(res["defender"]), region_name(res["region"])
    speed = f" ({res['elapsed']:.1f}s)" if res.get("elapsed") is not None else ""
    if res.get("base_fell"):
        return f"{dfn}'s base fell! {att} takes all of {dfn}'s land."
    if res["base"]:
        if res["attacker_won"]:
            return f"{att} destroyed a tower of {dfn}'s base{speed}. Towers left: {res['towers_left']}."
        return f"{dfn}'s tower holds. Towers left: {res['towers_left']}."
    if res["attacker_won"]:
        return f"{att} took {region} from {dfn}{speed}."
    return f"{dfn} held {region}."


def owner_map(state):
    return {int(r): p for r, p in state.get("owner", {}).items()}


def bases_map(state):
    """{base region: towers left} for the board."""
    towers = state.get("towers", {})
    return {r: towers.get(p, 0) for p, r in state.get("bases", {}).items()}


def draw_timer(screen, app):
    timer_ring(screen, app.remaining())


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
        draw_background(screen)
        me = self.app.you
        if me in st["pickers"]:
            text(screen, "Pick your starting region!", (MARGIN, 15), PLAYER_COLORS[me], size=42,
                 bold=True)
            hint = ("Picks are secret. The round ends when everyone has picked."
                    if st["your_pick"] is None else
                    f"You picked {region_name(st['your_pick'])}. Waiting for the others...")
            text(screen, hint, (MARGIN, 60), GRAY, size=26)
        else:
            names = ", ".join(self.app.player_name(p) for p in st["pickers"])
            text(screen, f"Waiting for {names} to pick a region...", (MARGIN, 15), size=36,
                 bold=True)
        draw_timer(screen, self.app)
        draw_result(screen, self.app)
        draw_board(screen, owner_map(st), my_pick=st["your_pick"],
                   my_color=PLAYER_COLORS[me] if me is not None else WHITE)


class QuestionScene(Scene):
    """Every question pops up as a card over the dimmed map, so attention
    goes only there. Answer with keys 1-4 or by clicking. The server judges."""

    CARD_W = 680
    POP_MS = 280
    joiner = "vs"        # between player names in the header: rivals or not

    def __init__(self, app):
        super().__init__(app)
        self.token = None
        self.shown_at = 0
        self.total = 10.0
        self.card = pygame.Rect(0, 0, 0, 0)
        self.choice_rects = []      # screen coordinates, for clicks

    # subclasses provide these
    def question(self):
        raise NotImplementedError

    def may_answer(self):
        raise NotImplementedError

    def status(self):
        raise NotImplementedError

    def title(self):
        raise NotImplementedError

    def players(self):
        """Players taking part in this question, shown on the card."""
        raise NotImplementedError

    def draw_map(self, screen):
        raise NotImplementedError

    def can_answer(self):
        return self.may_answer() and self.app.answered_q != self.app.question_token()

    def reveal_status(self, info):
        """Status while a won question stays open for the others."""
        res = self.app.state.get("last_result") or {}
        first = next((a["player"] for a in res.get("answers", [])
                      if a["correct"] and not a.get("late")), None)
        if first is None:
            return None
        if first == self.app.you:
            return "You were first!", GREEN_TEXT
        name = self.app.player_name(first)
        if self.app.you in info["waiting"] and self.can_answer():
            return f"{name} answered first! Answer anyway to see if you were right.", YELLOW
        return f"{name} answered first!", YELLOW

    def handle(self, event):
        if not self.can_answer():
            return
        for i, rect in enumerate(self.choice_rects):
            pressed = event.type == pygame.KEYDOWN and event.key == ANSWER_KEYS[i]
            clicked = (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                       and rect.collidepoint(event.pos))
            if pressed or clicked:
                self.app.answer(i)
                return

    def draw(self, screen):
        token = self.app.question_token()
        if token != self.token:                     # a new question: pop it in
            self.token = token
            self.shown_at = pygame.time.get_ticks()
            self.total = max(self.app.remaining(), 1.0)
        progress = min(1.0, (pygame.time.get_ticks() - self.shown_at) / self.POP_MS)

        draw_background(screen)
        text(screen, self.title(), (MARGIN, 20), size=36, bold=True)
        self.draw_map(screen)
        dim(screen, 175 * min(1.0, progress * 1.5))

        card = self.render_card()
        scale = 0.8 + 0.2 * ease_out_back(progress)
        if scale != 1.0:
            size = (int(card.get_width() * scale), int(card.get_height() * scale))
            card = pygame.transform.smoothscale(card, size)
        screen.blit(card, card.get_rect(center=self.card.center))

    def render_card(self):
        """The question on a parchment sheet with an oxblood ribbon header."""
        q = self.question()
        w = self.CARD_W
        lines = wrap_text(q["q"], 36, w - 56, bold=True)
        top = 86 if q.get("category") else 64
        choices_top = top + 6 + len(lines) * 36 + 14
        h = choices_top + len(q["choices"]) * 56 + 66
        self.card = pygame.Rect(0, 0, w, h)
        self.card.center = (WIDTH // 2, min(HEIGHT // 2 + 30, HEIGHT - h // 2 - 8))
        surf = pygame.Surface((w + 8, h + 8), pygame.SRCALPHA)   # room for the shadow
        draw_panel(surf, (0, 0, w, h), header=self.title(), header_h=44)
        self.draw_players(surf, w - 22, 25)

        if q.get("category"):
            label = q["category"] + (f"  ·  {q['difficulty']}" if q.get("difficulty") else "")
            text(surf, label, (28, 58), INK_SOFT, size=24, italic=True)
        for i, line in enumerate(lines):
            text(surf, line, (28, top + i * 36), INK, size=36, bold=True)

        active = self.can_answer()
        mine = self.app.answered_choice if self.app.answered_q == self.app.question_token() else None
        mouse = pygame.mouse.get_pos()
        self.choice_rects = []
        for i, choice in enumerate(q["choices"]):
            local = pygame.Rect(28, choices_top + i * 56, w - 56, 46)
            screen_rect = local.move(self.card.topleft)
            self.choice_rects.append(screen_rect)
            if i == mine:
                fill, ink = (196, 160, 98), INK
            elif active:
                fill = (224, 204, 160) if screen_rect.collidepoint(mouse) else PARCH_DARK
                ink = INK
            else:
                fill, ink = (214, 198, 164), (150, 128, 96)
            pygame.draw.rect(surf, fill, local, border_radius=4)
            pygame.draw.rect(surf, INK if i == mine else INK_SOFT, local, 3 if i == mine else 1,
                             border_radius=4)
            draw_seal(surf, (local.x + 24, local.centery), str(i + 1), r=15,
                      color=(150, 36, 30) if active or i == mine else (158, 120, 104))
            label, size = fit_text(choice, local.w - 64, 32, 22)
            text(surf, label, (local.x + 52, local.centery - font(size).get_height() // 2), ink,
                 size=size)

        bar_y = choices_top + len(q["choices"]) * 56 + 4
        bar = pygame.Rect(28, bar_y, w - 56, 10)
        fraction = max(0.0, min(1.0, self.app.remaining() / self.total))
        pygame.draw.rect(surf, (186, 160, 116), bar)
        pygame.draw.rect(surf, timer_color(fraction), (bar.x, bar.y, int(bar.w * fraction), bar.h))
        pygame.draw.rect(surf, INK_SOFT, bar, 1)
        text(surf, f"{self.app.remaining():0.0f}s", (bar.right - 30, bar_y + 18), INK_SOFT, size=26,
             bold=True)

        msg, color = self.status()
        text(surf, msg, (28, bar_y + 18), ON_PARCHMENT.get(color, INK), size=26, italic=True)
        return surf

    def draw_players(self, surf, right, cy):
        """Heraldic shields and names, right-aligned in the ribbon."""
        x = right
        players = self.players()
        for i, p in enumerate(reversed(players)):
            name = self.app.player_name(p)
            r = text(surf, name, (0, -100), size=26, bold=True)        # measure only
            x -= r.width
            text(surf, name, (x, cy - r.height // 2), WHITE, size=26, bold=True)
            x -= 16
            draw_shield(surf, (x + 4, cy - 2), PLAYER_COLORS[p], size=8)
            x -= 16
            if i < len(players) - 1:
                vs = text(surf, self.joiner, (0, -100), size=24, italic=True)
                x -= vs.width + 2
                text(surf, self.joiner, (x, cy - vs.height // 2), GOLD, size=24, italic=True)
                x -= 12


class Duel(QuestionScene):
    """Opening bonus question for a contested region. Quickest correct answer
    wins. Players not in the duel watch but cannot answer."""

    def question(self):
        return self.app.state["duel"]["question"]

    def title(self):
        return f"Bonus question for {region_name(self.app.state['duel']['region'])}"

    def players(self):
        return self.app.state["duel"]["players"]

    def may_answer(self):
        duel = self.app.state["duel"]
        if duel["reveal"]:
            return self.app.you in duel["waiting"]
        return self.app.you in duel["players"] and self.app.you not in duel["locked_out"]

    def status(self):
        duel = self.app.state["duel"]
        me = self.app.you
        if duel["reveal"]:
            return self.reveal_status(duel) or ("", GRAY)
        if me in duel["players"]:
            if me in duel["locked_out"]:
                return "Wrong! You're locked out of this question.", RED_TEXT
            if not self.can_answer():
                return "Answer sent...", GRAY
            return "Fastest correct answer wins!", YELLOW
        return "You're watching this fight.", GRAY

    def draw_map(self, screen):
        st = self.app.state
        draw_board(screen, owner_map(st), contested=st["duel"]["region"])


class Done(Scene):
    def draw(self, screen):
        st = self.app.state
        draw_background(screen)
        text(screen, "Starting regions are set!", (MARGIN, 15), size=42, bold=True)
        owners = owner_map(st)
        parts = [f"{self.app.player_name(p)}: {region_name(r)}"
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
        draw_background(screen)
        mine = st["selections"].get(str(me))
        if st["selectable"] or mine is not None:
            text(screen, "Land grab: choose a free region next to your land",
                 (MARGIN, 15), PLAYER_COLORS[me], size=36, bold=True)
            hint = ("Hatched lands are locked by other players. You can change your choice."
                    if mine is None else
                    f"You chose {region_name(mine)}. A question follows when the time is up.")
        else:
            text(screen, "Land grab", (MARGIN, 15), size=36, bold=True)
            hint = "No free region next to your land. Waiting for the others..."
        text(screen, hint, (MARGIN, 60), GRAY, size=26)
        draw_timer(screen, self.app)
        draw_result(screen, self.app)
        locked = {r: int(p) for p, r in st["selections"].items()}
        conquest_board(screen, self.app, selections=locked, selectable=st["selectable"],
                       my_pick=mine, my_color=PLAYER_COLORS[me])


class GrabQuestion(QuestionScene):
    """Everyone who selected a region answers; each correct player takes it."""

    joiner = "&"

    def question(self):
        return self.app.state["question"]

    def title(self):
        mine = self.app.state["selections"].get(str(self.app.you))
        return "Land grab" + (f" for {region_name(mine)}" if mine is not None else "")

    def players(self):
        return self.app.state["answering"]

    def may_answer(self):
        st = self.app.state
        return self.app.you in st["answering"] and self.app.you not in st["answered"]

    def status(self):
        st = self.app.state
        me = self.app.you
        waiting = [self.app.player_name(p) for p in st["answering"] if p not in st["answered"]]
        if me in st["answering"]:
            if self.can_answer():
                return "Answer correctly to take your region!", YELLOW
            if waiting:
                return f"Answer sent. Waiting for {', '.join(waiting)}...", GRAY
            return "Answer sent...", GRAY
        return "You didn't choose a region this round. Watching.", GRAY

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
        draw_background(screen)
        if attacker == me:
            text(screen, "Your turn: attack a region next to your land",
                 (MARGIN, 15), PLAYER_COLORS[me], size=36, bold=True)
            hint = ("Attacking a base starts a 3-tower siege." if target is None else
                    f"Target: {region_name(target)}. You can change it until the time is up.")
        else:
            text(screen, f"{self.app.player_name(attacker)} is choosing a target...",
                 (MARGIN, 15), PLAYER_COLORS[attacker], size=36, bold=True)
            hint = ("" if target is None else
                    f"Target: {region_name(target)} ({self.app.player_name(owner_map(st)[target])})")
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

    def players(self):
        return list(self.fighters())

    def title(self):
        st = self.app.state
        a = st["attack"]
        if a["base"]:
            towers = st["towers"].get(str(a["defender"]), 0)
            return f"Siege: tower {a['tower_q']} of 3 ({towers} standing)"
        return f"Attack on {region_name(a['region'])}"

    def may_answer(self):
        a = self.app.state["attack"]
        if a["reveal"]:
            return self.app.you in a["waiting"]
        return self.app.you in self.fighters() and self.app.you not in a["locked_out"]

    def status(self):
        a = self.app.state["attack"]
        me = self.app.you
        if a["reveal"]:
            return self.reveal_status(a) or ("", GRAY)
        att, dfn = (self.app.player_name(p) for p in self.fighters())
        if me in self.fighters():
            if me in a["locked_out"]:
                return "Wrong! You're locked out of this question.", RED_TEXT
            if not self.can_answer():
                return "Answer sent...", GRAY
            if me == self.fighters()[0]:
                return "You attack! Fastest correct answer wins.", YELLOW
            return f"{att} attacks you! Fastest correct answer wins.", YELLOW
        return f"{att} attacks {dfn}. You're watching.", GRAY

    def draw_map(self, screen):
        conquest_board(screen, self.app, contested=self.app.state["attack"]["region"])


class GameOver(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.leave = Button((WIDTH - MARGIN - 200, 22, 200, 46), "Back to lobby")

    def handle(self, event):
        if self.leave.clicked(event):
            self.app.leave()

    def draw(self, screen):
        st = self.app.state
        winner = st["winner"]
        draw_background(screen)
        if winner is None:
            text(screen, "Game over", (MARGIN, 14), GOLD, size=52, bold=True)
        else:
            text(screen, f"{self.app.player_name(winner)} conquers the realm!", (MARGIN, 14),
                 PLAYER_COLORS[winner], size=52, bold=True)
        flourish(screen, (MARGIN + 260, 76), 520)
        draw_result(screen, self.app)
        self.leave.draw(screen, WOOD_RED)
        conquest_board(screen, self.app)


# ---- result popup ------------------------------------------------------------

def answer_rows(res):
    """[(player, correct, detail)] for each answer, in the order they arrived.
    Shows who was first and how much slower the other correct answers were."""
    answers = res.get("answers") or []
    on_time = [a["elapsed"] for a in answers if a["correct"] and not a.get("late")]
    fastest = min(on_time) if on_time else None
    race = res.get("kind") != "grab"         # in a land grab every correct answer wins
    rows = []
    for a in answers:
        if not a["correct"]:
            detail = f"wrong ({a['elapsed']:.1f}s)"
        elif a.get("late") and fastest is not None:
            detail = f"correct, but {a['elapsed'] - fastest:.1f}s slower"
        elif race and a["elapsed"] == fastest:
            detail = f"correct in {a['elapsed']:.1f}s - FIRST!"
        else:
            detail = f"correct in {a['elapsed']:.1f}s"
        rows.append((a["player"], a["correct"], detail))
    return rows


class ResultPopup:
    """Shows what happened after every question or turn. It sits in the
    header strip above the map (or at the top, over a question card), so it
    never covers the map or catches clicks."""

    SHOW_MS = 4000
    POP_MS = 220

    def __init__(self, app):
        self.app = app
        self.key = None
        self.shown_at = 0

    def result(self):
        st = self.app.state
        return st.get("last_result") if st else None

    def update(self):
        res = self.result()
        key = (self.app.state["stage"], res.get("no")) if res else None
        if key != self.key:
            self.key = key
            self.shown_at = pygame.time.get_ticks()

    def visible(self):
        return self.key is not None and pygame.time.get_ticks() - self.shown_at < self.SHOW_MS

    def draw(self, screen, compact):
        if not self.visible():
            return
        res = self.result()
        title = result_line(self.app) or ""
        rows = answer_rows(res)
        progress = min(1.0, (pygame.time.get_ticks() - self.shown_at) / self.POP_MS)
        if compact:
            self.draw_banner(screen, title, rows, progress)
        else:
            self.draw_header(screen, title, rows, progress)

    def draw_banner(self, screen, title, rows, progress):
        parts = [title] + [f"{self.app.player_name(p)}: {d}" for p, _, d in rows]
        line = "   ".join(parts)
        rect = pygame.Rect(MARGIN, 0, WIDTH - 2 * MARGIN, 42)
        rect.y = int(-42 + 52 * ease_out_back(progress))
        draw_panel(screen, rect)
        text(screen, wrap_text(line, 24, rect.w - 32)[0], (rect.x + 16, rect.y + 11), INK, size=24)

    def draw_header(self, screen, title, rows, progress):
        """Result in the strip between the scene title and the map."""
        strip = pygame.Rect(0, 90, WIDTH, BOARD_TOP - 92)
        screen.blit(leather(), strip, strip)                   # replaces the plain result line
        slide = int(-30 * (1 - ease_out_back(progress)))
        x = MARGIN + slide
        pygame.draw.rect(screen, YELLOW, (x, strip.y + 4, 4, strip.h - 8), border_radius=2)
        text(screen, title, (x + 14, strip.y + 4), YELLOW, size=26)
        x += 14
        for player, correct, detail in rows:
            draw_mark(screen, (x + 9, strip.y + 39), correct, r=9)
            r = text(screen, self.app.player_name(player), (x + 24, strip.y + 30),
                     PLAYER_COLORS[player], size=24)
            r = text(screen, detail, (r.right + 8, strip.y + 31), WHITE, size=22)
            x = r.right + 24

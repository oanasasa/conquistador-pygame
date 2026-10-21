"""One scene per screen. Scenes read shared state from the App and send
player actions through it; they never judge answers themselves."""
import pygame

from net import opentdb, protocol
from ui.widgets import (BOARD_TOP, GOLD, GRAY, HEIGHT, INK, INK_SOFT, MARGIN, OXBLOOD,
                        PARCH_DARK, PLAYER_COLORS, WHITE, WIDTH, WOOD_GREEN, WOOD_RED, Button,
                        Dropdown, TextInput, dim, draw_background, draw_board, draw_mark, draw_panel, draw_seal,
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


def draw_mute_hint(screen, muted):
    """Top-right reminder of the mute key, in the menus."""
    label = "M: let the minstrels play" if muted else "M: silence the minstrels"
    text(screen, label, (WIDTH - MARGIN - font(20, italic=True).size(label)[0], 6), GRAY,
         size=20, italic=True)


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

    def typing(self):
        """True while a text field has focus (so letter keys are text, not shortcuts)."""
        return False

    def draw_error(self, screen):
        if self.app.error:
            text(screen, self.app.error, (MARGIN, HEIGHT - 34), RED_TEXT, size=26)


class NameEntry(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.input = TextInput((WIDTH // 2 - 160, 300, 320, 46), placeholder="thy name")
        self.ok = Button((WIDTH // 2 - 90, 372, 180, 46), "Onward")

    def typing(self):
        return True

    def handle(self, event):
        entered = self.input.handle(event) or self.ok.clicked(event)
        if entered and self.input.value.strip():
            self.app.set_name(self.input.value.strip())

    def draw(self, screen):
        draw_background(screen)
        text(screen, "Conquistador", (WIDTH // 2, 110), GOLD, size=86, center=True, bold=True)
        flourish(screen, (WIDTH // 2, 158), 420)
        text(screen, "A contest of wits and conquest", (WIDTH // 2, 184), GRAY, size=30,
             center=True, italic=True)
        draw_panel(screen, (WIDTH // 2 - 200, 222, 400, 220), header="Who rides to battle?")
        text(screen, "By what name shall ye be known?", (WIDTH // 2 - 160, 274), INK_SOFT, size=26, italic=True)
        self.ok.enabled = bool(self.input.value.strip())
        self.input.draw(screen)
        self.ok.draw(screen, WOOD_GREEN)
        text(screen, "Riddles from the Open Trivia Database (opentdb.com), CC BY-SA 4.0",
             (WIDTH // 2, HEIGHT - 24), GRAY, size=22, center=True, italic=True)


class Lobby(Scene):
    """Browse LAN rooms, create one, or join by IP."""

    def __init__(self, app):
        super().__init__(app)
        self.create = Button((MARGIN, 84, 220, 46), "Raise a hall")
        self.solo = Button((MARGIN + 240, 84, 220, 46), "Face a bot")
        self.ip = TextInput((MARGIN, HEIGHT - 96, 300, 46), placeholder="e.g. 192.168.1.5",
                            max_len=40)
        self.ip.active = False
        self.join_ip = Button((MARGIN + 316, HEIGHT - 96, 150, 46), "Seek")
        self.room_buttons = []

    def typing(self):
        return self.ip.active

    def handle(self, event):
        if self.create.clicked(event):
            self.app.open_settings()
            return
        if self.solo.clicked(event):
            self.app.open_settings(with_bot=True)
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
                           header="Halls within earshot")
        rooms = self.app.browser.list_rooms() if self.app.browser else []
        self.room_buttons = []
        if not rooms:
            text(screen, "No hall within earshot. Raise thine own, or ask thy host where they dwell.",
                 (panel.x + 24, panel.y + 66), INK_SOFT, size=26, italic=True)
        for i, room in enumerate(rooms[:4]):
            y = panel.y + 56 + i * 54
            full = room["players"] >= room["max"]
            text(screen, room["room"], (panel.x + 24, y + 2), INK, size=30, bold=True)
            text(screen, topics_line(room.get("category"), room.get("difficulty")),
                 (panel.x + 24, y + 28), INK_SOFT, size=22, italic=True)
            text(screen, f"{room['ip']}   ·   {room['players']}/{room['max']} souls",
                 (panel.x + 360, y + 12), INK_SOFT, size=24, italic=True)
            b = Button((panel.right - 150, y, 126, 42), "Full" if full else "Enter", not full)
            b.draw(screen)
            self.room_buttons.append((b, room))
            pygame.draw.line(screen, PARCH_DARK, (panel.x + 20, y + 50), (panel.right - 20, y + 50), 1)
        text(screen, "Or seek a hall by its address:", (MARGIN, HEIGHT - 128), GRAY, size=26, italic=True)
        self.ip.draw(screen)
        self.join_ip.enabled = bool(self.ip.value.strip())
        self.join_ip.draw(screen)
        if self.app.local_ip:
            label = f"Thine address: {self.app.local_ip}"
            text(screen, label, (WIDTH - MARGIN - font(26).size(label)[0], HEIGHT - 84), GRAY, size=26)
        self.draw_error(screen)


RANKS = {"any": "Any", "easy": "Squire", "medium": "Knight", "hard": "King"}


def rank_name(difficulty):
    """OpenTDB difficulty as a rank of trial: easy -> Squire, and so on."""
    return RANKS.get(difficulty or "any", (difficulty or "any").capitalize())


def topics_line(category, difficulty):
    """'History · Knight's trial' for a hall's question settings."""
    if not category:
        return "The realm's own riddles"
    if (difficulty or "any") == "any":
        return f"{category}  ·  trials of every rank"
    return f"{category}  ·  {rank_name(difficulty)}'s trial"


class CampaignSettings(Scene):
    """Popup before creating a room: the question category (one, or all
    mixed) and difficulty. The host's game fetches matching questions from
    opentdb.com when the room opens; nothing is saved."""

    def __init__(self, app):
        super().__init__(app)
        self.behind = Lobby(app)
        self.panel = pygame.Rect(150, 56, 600, 488)
        x0 = self.panel.x + 30
        self.lore = Dropdown((x0, self.panel.y + 122, self.panel.w - 60, 46), opentdb.CHOICES,
                             app.campaign["category"], visible=8)
        self.level_rects = {key: pygame.Rect(x0 + i * 136, self.panel.y + 258, 126, 48)
                            for i, key in enumerate(opentdb.DIFFICULTIES)}
        with_bot = (app.settings_for or {}).get("with_bot")
        self.back = Button((x0, self.panel.bottom - 72, 170, 50), "Turn back")
        self.go = Button((self.panel.right - 30 - 270, self.panel.bottom - 72, 270, 50),
                         "Face the automaton" if with_bot else "Raise the hall")

    def handle(self, event):
        c = self.app.campaign
        if self.lore.handle(event):
            c["category"] = self.lore.selected
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for key, rect in self.level_rects.items():
                if rect.collidepoint(event.pos):
                    c["difficulty"] = key
        if self.back.clicked(event):
            self.app.close_settings()
        elif self.go.clicked(event):
            self.app.create_room(with_bot=self.app.settings_for["with_bot"],
                                 category=c["category"], difficulty=c["difficulty"])

    def draw(self, screen):
        self.behind.draw(screen)
        dim(screen, 170)
        c = self.app.campaign
        p = draw_panel(screen, self.panel, header="Prepare thy campaign", header_h=44)
        mouse = pygame.mouse.get_pos()

        text(screen, "The lore", (p.x + 30, p.y + 62), INK, size=32, bold=True)
        text(screen, "In what learning shall thy foes be tested? Choose one, or all.",
             (p.x + 30, p.y + 94), INK_SOFT, size=22, italic=True)
        self.lore.draw(screen)

        text(screen, "The rank of trial", (p.x + 30, p.y + 196), INK, size=32, bold=True)
        text(screen, "How grievous shall the riddles be?", (p.x + 30, p.y + 228), INK_SOFT,
             size=22, italic=True)
        for key, rect in self.level_rects.items():
            on = c["difficulty"] == key
            fill = OXBLOOD if on else ((224, 204, 160) if rect.collidepoint(mouse) else PARCH_DARK)
            pygame.draw.rect(screen, fill, rect, border_radius=4)
            pygame.draw.rect(screen, GOLD if on else INK_SOFT, rect, 2 if on else 1, border_radius=4)
            text(screen, rank_name(key), rect.center, GOLD if on else INK, size=28, center=True,
                 bold=on)

        for i, line in enumerate(wrap_text(
                "Messengers shall ride to opentdb.com for thy riddles when the hall is raised, "
                "and nothing shall be kept thereafter. Should they fail to return, the realm's "
                "own riddles shall serve.", 22, p.w - 60)):
            text(screen, line, (p.x + 30, p.y + 330 + i * 22), INK_SOFT, size=22, italic=True)
        self.back.draw(screen, WOOD_RED)
        self.go.draw(screen, WOOD_GREEN)
        self.lore.draw_list(screen)          # last, so the open list lies on top


class Room(Scene):
    """Waiting room: player list, host starts the game."""

    def __init__(self, app):
        super().__init__(app)
        y = 420
        self.start = Button((MARGIN, y, 190, 50), "To battle!")
        self.add_bot = Button((MARGIN + 204, y, 196, 50), "Summon bot")
        self.remove_bot = Button((MARGIN + 414, y, 196, 50), "Dismiss bot")
        self.leave = Button((WIDTH - MARGIN - 160, y, 160, 50), "Depart")

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
            text(screen, f"Others may enter at {self.app.local_ip}", (MARGIN, 70), GRAY, size=26,
                 italic=True)
        panel = draw_panel(screen, (MARGIN, 110, 560, 280), header="The company")
        players = lobby.get("players", [])
        for i, p in enumerate(players):
            y = panel.y + 66 + i * 62
            draw_shield(screen, (panel.x + 40, y + 14), PLAYER_COLORS[p["id"]], size=14)
            tag = []
            if p["id"] == lobby.get("host"):
                tag.append("lord of the hall")
            if p["id"] == self.app.you:
                tag.append("thyself")
            if p.get("bot"):
                tag.append("a thing of gears")
            r = text(screen, p["name"], (panel.x + 72, y), INK, size=34, bold=True)
            if tag:
                text(screen, ", ".join(tag), (r.right + 14, y + 8), INK_SOFT, size=24, italic=True)
        for i in range(len(players), protocol.MAX_PLAYERS):
            y = panel.y + 66 + i * 62
            text(screen, "an empty seat at the table...", (panel.x + 72, y + 4), PARCH_DARK, size=28, italic=True)
        questions = lobby.get("questions") or {}
        loading = questions.get("status") == "loading"
        self.draw_questions(screen, questions)
        is_host = self.app.you is not None and self.app.you == lobby.get("host")
        if is_host:
            self.start.enabled = len(players) >= protocol.MIN_PLAYERS and not loading
            self.start.draw(screen, WOOD_GREEN)
            self.add_bot.enabled = len(players) < protocol.MAX_PLAYERS
            self.add_bot.draw(screen)
            self.remove_bot.enabled = any(p.get("bot") for p in players)
            self.remove_bot.draw(screen)
            if len(players) < protocol.MIN_PLAYERS:
                text(screen, "Await another soul, or summon a bot to fight alone.",
                     (MARGIN, 486), GRAY, size=26, italic=True)
            elif loading:
                text(screen, "The messengers ride... ye may march once the first riddles arrive.",
                     (MARGIN, 486), GRAY, size=26, italic=True)
        else:
            text(screen, "Await the command of the lord of the hall...", (MARGIN, 486), GRAY, size=26,
                 italic=True)
        self.leave.draw(screen, WOOD_RED)
        self.draw_error(screen)

    def draw_questions(self, screen, info):
        """Right-hand sheet: the hall's lore, rank of trial and riddle status."""
        p = draw_panel(screen, (600, 110, WIDTH - MARGIN - 600, 280), header="The riddles")
        x, y = p.x + 22, p.y + 60
        category = info.get("category")
        lines = wrap_text(category or "The realm's own riddles", 28, p.w - 60, bold=True)
        pygame.draw.polygon(screen, OXBLOOD, [(x, y + 10), (x + 6, y + 4), (x + 12, y + 10),
                                              (x + 6, y + 16)])
        for line in lines:
            text(screen, line, (x + 22, y), INK, size=28, bold=True)
            y += 30
        if category:
            rank = info.get("difficulty") or "any"
            text(screen, "Trials of every rank" if rank == "any" else f"Rank: {rank_name(rank)}",
                 (x, y + 6), INK_SOFT, size=24, italic=True)
            y += 32
        status, count = info.get("status"), info.get("count", 0)
        if status == "loading":
            dots = "." * (pygame.time.get_ticks() // 400 % 4)
            msg = f"Messengers ride to opentdb.com{dots}"
        elif status == "ready":
            msg = f"{count} riddles at hand" + (", more on the road" if info.get("loading") else "")
        elif status == "offline":
            msg = f"The messengers returned not. The realm's own {count} riddles shall serve."
        else:
            msg = f"{count} riddles of the realm"
        for line in wrap_text(msg, 24, p.w - 44):
            text(screen, line, (x, y + 10), (128, 80, 16), size=24, italic=True)
            y += 24


def result_line(app):
    """One line describing what just happened, for any stage."""
    res = app.state.get("last_result") if app.state else None
    if not res:
        return None
    name = app.player_name
    kind = res.get("kind")
    if kind is None:                                  # opening duel
        if res.get("elapsed") is None:
            return f"{name(res['winner'])} claimeth {region_name(res['region'])}"
        return f"{name(res['winner'])} winneth {region_name(res['region'])}, answering in {res['elapsed']:.1f}s"
    if kind == "grab":
        parts = [f"{name(int(p))} seizeth {region_name(r)}" for p, r in res["won"].items()]
        parts += [f"{name(p)} faltered" for p in res["missed"]]
        return ". ".join(parts) + "." if parts else None
    if kind == "skip":
        return f"{name(res['attacker'])} held back this turn."
    att, dfn, region = name(res["attacker"]), name(res["defender"]), region_name(res["region"])
    speed = f" ({res['elapsed']:.1f}s)" if res.get("elapsed") is not None else ""
    if res.get("base_fell"):
        return f"{dfn}'s castle hath fallen! {att} taketh all of {dfn}'s lands."
    if res["base"]:
        if res["attacker_won"]:
            return f"{att} toppleth a tower of {dfn}'s castle{speed}. Towers standing: {res['towers_left']}."
        return f"{dfn}'s tower holdeth! Towers standing: {res['towers_left']}."
    if res["attacker_won"]:
        return f"{att} wresteth {region} from {dfn}{speed}."
    return f"{dfn} holdeth {region}."


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
            text(screen, "Claim thy homeland!", (MARGIN, 15), PLAYER_COLORS[me], size=42,
                 bold=True)
            hint = ("Thy choice is secret. The round endeth when all have chosen."
                    if st["your_pick"] is None else
                    f"Thou hast chosen {region_name(st['your_pick'])}. Await the others...")
            text(screen, hint, (MARGIN, 60), GRAY, size=26)
        else:
            names = ", ".join(self.app.player_name(p) for p in st["pickers"])
            text(screen, f"{names} yet ponder their homeland...", (MARGIN, 15), size=36,
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

    def revealing(self):
        """True while a won duel question stays open for the others."""
        return False

    def tick_clock(self):
        """The clock ticks while the riddle is open, louder in the last three seconds."""
        left = self.app.remaining()
        self.app.sound.riddle_clock(left > 0 and not self.revealing(), urgent=left <= 3)

    def reveal_status(self, info):
        """Status while a won question stays open for the others."""
        res = self.app.state.get("last_result") or {}
        first = next((a["player"] for a in res.get("answers", [])
                      if a["correct"] and not a.get("late")), None)
        if first is None:
            return None
        if first == self.app.you:
            return "Thou wast first!", GREEN_TEXT
        name = self.app.player_name(first)
        if self.app.you in info["waiting"] and self.can_answer():
            return f"{name} answered first! Answer still, to learn if thou wert right.", YELLOW
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
        self.tick_clock()
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
            label = q["category"] + (f"  ·  {rank_name(q['difficulty'])}'s trial"
                                     if q.get("difficulty") else "")
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

    def revealing(self):
        return self.app.state["duel"]["reveal"]

    def question(self):
        return self.app.state["duel"]["question"]

    def title(self):
        return f"A duel for {region_name(self.app.state['duel']['region'])}"

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
                return "False! Thou art barred from this riddle.", RED_TEXT
            if not self.can_answer():
                return "Thine answer is sent...", GRAY
            return "The swiftest true answer wins!", YELLOW
        return "Thou watchest this duel.", GRAY

    def draw_map(self, screen):
        st = self.app.state
        draw_board(screen, owner_map(st), contested=st["duel"]["region"])


class Done(Scene):
    def draw(self, screen):
        st = self.app.state
        draw_background(screen)
        text(screen, "The homelands are claimed!", (MARGIN, 15), size=42, bold=True)
        owners = owner_map(st)
        parts = [f"{self.app.player_name(p)}: {region_name(r)}"
                 for r, p in sorted(owners.items(), key=lambda kv: kv[1])]
        text(screen, "   ".join(parts), (MARGIN, 60), GRAY, size=26)
        text(screen, "Here stand thy castles. Now the scramble for land begins...", (MARGIN, 100), YELLOW, size=26)
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
            text(screen, "Seize free land beside thine own",
                 (MARGIN, 15), PLAYER_COLORS[me], size=36, bold=True)
            hint = ("Hatched lands are claimed by others. Thou mayst change thy mind."
                    if mine is None else
                    f"Thou hast marked {region_name(mine)}. A riddle follows when the sand runs out.")
        else:
            text(screen, "The scramble for land", (MARGIN, 15), size=36, bold=True)
            hint = "No free land borders thine. Await the others..."
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
        return "A riddle" + (f" for {region_name(mine)}" if mine is not None else " of the land")

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
                return "Answer true to take thy land!", YELLOW
            if waiting:
                return f"Thine answer is sent. Awaiting {', '.join(waiting)}...", GRAY
            return "Thine answer is sent...", GRAY
        return "Thou markedst no land this round. Watch and wait.", GRAY

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
            text(screen, "Thy turn! March upon a land beside thine own",
                 (MARGIN, 15), PLAYER_COLORS[me], size=36, bold=True)
            hint = ("Strike at a castle to lay siege to its three towers." if target is None else
                    f"Thy target: {region_name(target)}. Thou mayst change it ere the sand runs out.")
        else:
            text(screen, f"{self.app.player_name(attacker)} chooseth a target...",
                 (MARGIN, 15), PLAYER_COLORS[attacker], size=36, bold=True)
            hint = ("" if target is None else
                    f"Their target: {region_name(target)}, held by {self.app.player_name(owner_map(st)[target])}")
        text(screen, hint, (MARGIN, 60), GRAY, size=26)
        draw_timer(screen, self.app)
        draw_result(screen, self.app)
        conquest_board(screen, self.app, selectable=st["selectable"], contested=target)


class WarDuel(QuestionScene):
    """Attacker vs defender; quickest correct answer wins. Others watch."""

    def revealing(self):
        return self.app.state["attack"]["reveal"]

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
            return f"Siege! Tower {a['tower_q']} of 3, {towers} yet standing"
        return f"Battle for {region_name(a['region'])}"

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
                return "False! Thou art barred from this riddle.", RED_TEXT
            if not self.can_answer():
                return "Thine answer is sent...", GRAY
            if me == self.fighters()[0]:
                return "Thou attackest! The swiftest true answer wins.", YELLOW
            return f"{att} marcheth upon thee! The swiftest true answer wins.", YELLOW
        return f"{att} marcheth upon {dfn}. Thou watchest.", GRAY

    def draw_map(self, screen):
        conquest_board(screen, self.app, contested=self.app.state["attack"]["region"])


class GameOver(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.leave = Button((WIDTH - MARGIN - 200, 22, 200, 46), "Return to the halls")

    def handle(self, event):
        if self.leave.clicked(event):
            self.app.leave()

    def draw(self, screen):
        st = self.app.state
        winner = st["winner"]
        draw_background(screen)
        if winner is None:
            text(screen, "The war is ended", (MARGIN, 14), GOLD, size=52, bold=True)
        else:
            text(screen, f"{self.app.player_name(winner)} conquers the realm!", (MARGIN, 14),
                 PLAYER_COLORS[winner], size=52, bold=True)
        flourish(screen, (MARGIN + 260, 76), 520)
        draw_result(screen, self.app)
        self.leave.draw(screen, WOOD_RED)
        conquest_board(screen, self.app)


class Interlude(Scene):
    """A short pause after a riddle: what happened, who answered how fast, and
    what comes next. The next selection timer starts only after it."""

    POP_MS = 260

    def __init__(self, app):
        super().__init__(app)
        self.shown_at = pygame.time.get_ticks()
        self.total = max(app.remaining(), 1.0)

    def heading(self, res):
        kind = (res or {}).get("kind")
        if kind is None:
            return "The duel is done"
        if kind == "grab":
            return "The riddle is done"
        if kind == "skip":
            return "A turn passeth"
        if res.get("base_fell"):
            return "A castle hath fallen!"
        return "The siege goeth on" if res.get("base") else "The battle is done"

    def what_next(self):
        nxt = self.app.state.get("next") or {}
        me, name = self.app.you, self.app.player_name
        phase = nxt.get("phase")
        if phase == "grab_select":
            return "Make ready to choose thy next land!"
        if phase == "war_select":
            if nxt.get("attacker") == me:
                return "Thy turn to march cometh! Make ready."
            return f"{name(nxt.get('attacker'))} shall march next."
        if phase == "pick":
            pickers = nxt.get("pickers", [])
            if me in pickers:
                return "Thou must choose a new homeland!"
            return f"{', '.join(name(p) for p in pickers)} must choose anew."
        return "The war draweth to its end..."

    def draw(self, screen):
        st = self.app.state
        draw_background(screen)
        if st.get("stage") == "conquest":
            conquest_board(screen, self.app)
        else:
            draw_board(screen, owner_map(st))
        progress = min(1.0, (pygame.time.get_ticks() - self.shown_at) / self.POP_MS)
        dim(screen, 130 * progress)
        text(screen, "Hold! Take stock ere the next move", (MARGIN, 15), GOLD, size=36, bold=True)
        text(screen, self.what_next(), (MARGIN, 60), GRAY, size=26, italic=True)
        draw_timer(screen, self.app)

        res = st.get("last_result")
        w = 600
        lines = wrap_text(result_line(self.app) or "", 30, w - 60, bold=True)
        rows = answer_rows(res) if res else []
        nxt = self.what_next()
        h = 64 + len(lines) * 32 + (14 + len(rows) * 34 if rows else 0) + 104
        card = pygame.Surface((w + 8, h + 8), pygame.SRCALPHA)
        draw_panel(card, (0, 0, w, h), header=self.heading(res), header_h=44)
        y = 60
        for line in lines:
            text(card, line, (30, y), INK, size=30, bold=True)
            y += 32
        if rows:
            y += 14
            for player, correct, detail in rows:
                draw_mark(card, (40, y + 12), correct)
                r = text(card, self.app.player_name(player), (60, y), INK, size=28, bold=True)
                draw_shield(card, (r.right + 14, y + 12), PLAYER_COLORS[player], size=7)
                text(card, detail, (r.right + 30, y + 3), INK_SOFT, size=26, italic=True)
                y += 34
        y += 12
        flourish(card, (w // 2, y), w - 120, INK_SOFT)
        text(card, nxt, (w // 2, y + 26), (128, 80, 16), size=30, center=True, bold=True)
        bar = pygame.Rect(30, h - 30, w - 60, 8)
        fraction = max(0.0, min(1.0, self.app.remaining() / self.total))
        pygame.draw.rect(card, (186, 160, 116), bar)
        pygame.draw.rect(card, OXBLOOD, (bar.x, bar.y, int(bar.w * fraction), bar.h))
        pygame.draw.rect(card, INK_SOFT, bar, 1)

        scale = 0.8 + 0.2 * ease_out_back(progress)
        if scale != 1.0:
            card = pygame.transform.smoothscale(
                card, (int(card.get_width() * scale), int(card.get_height() * scale)))
        screen.blit(card, card.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 20)))


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
            detail = f"false ({a['elapsed']:.1f}s)"
        elif a.get("late") and fastest is not None:
            detail = f"true, but {a['elapsed'] - fastest:.1f}s too slow"
        elif race and a["elapsed"] == fastest:
            detail = f"true in {a['elapsed']:.1f}s - FIRST!"
        else:
            detail = f"true in {a['elapsed']:.1f}s"
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
        if not self.visible() or self.app.scene_key == "interlude":
            return                          # the interlude card already shows it
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

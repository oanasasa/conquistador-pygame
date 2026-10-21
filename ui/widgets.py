import pygame

from game.board import COLS, ROWS

WIDTH, HEIGHT = 900, 600
MARGIN = 20
BOARD_TOP = 150

BG = (30, 30, 40)
WHITE = (255, 255, 255)
GRAY = (150, 150, 160)
NEUTRAL = (90, 90, 90)
PLAYER_COLORS = [(220, 60, 60), (60, 120, 220), (60, 180, 80)]

_fonts = {}


def font(size=30):
    if size not in _fonts:
        _fonts[size] = pygame.font.SysFont(None, size)
    return _fonts[size]


def text(screen, s, pos, color=WHITE, size=30, center=False):
    surf = font(size).render(s, True, color)
    rect = surf.get_rect(center=pos) if center else surf.get_rect(topleft=pos)
    screen.blit(surf, rect)
    return rect


class Button:
    def __init__(self, rect, label, enabled=True):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.enabled = enabled

    def clicked(self, event):
        return (self.enabled and event.type == pygame.MOUSEBUTTONDOWN
                and event.button == 1 and self.rect.collidepoint(event.pos))

    def draw(self, screen, color=(70, 90, 140)):
        hover = self.enabled and self.rect.collidepoint(pygame.mouse.get_pos())
        fill = color if self.enabled else (60, 60, 70)
        if hover:
            fill = tuple(min(255, c + 30) for c in fill)
        pygame.draw.rect(screen, fill, self.rect, border_radius=6)
        text(screen, self.label, self.rect.center, WHITE if self.enabled else GRAY,
             size=28, center=True)


class TextInput:
    def __init__(self, rect, value="", max_len=16, placeholder=""):
        self.rect = pygame.Rect(rect)
        self.value = value
        self.max_len = max_len
        self.placeholder = placeholder
        self.active = True

    def handle(self, event):
        """Returns True when Enter is pressed while active."""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.active = self.rect.collidepoint(event.pos)
        elif self.active and event.type == pygame.TEXTINPUT:
            self.value = (self.value + event.text)[:self.max_len]
        elif self.active and event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                self.value = self.value[:-1]
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                return True
        return False

    def draw(self, screen):
        pygame.draw.rect(screen, (50, 50, 65), self.rect, border_radius=6)
        pygame.draw.rect(screen, WHITE if self.active else GRAY, self.rect, 2, border_radius=6)
        shown, color = (self.value, WHITE) if self.value else (self.placeholder, GRAY)
        caret = "|" if self.active and pygame.time.get_ticks() // 500 % 2 else ""
        text(screen, shown + caret, (self.rect.x + 10, self.rect.y + 10), color)


# ---- the region board ---------------------------------------------------

GRID_COLS, GRID_ROWS = COLS, ROWS
CELL_W = (WIDTH - MARGIN * 2) // GRID_COLS
CELL_H = (HEIGHT - BOARD_TOP - MARGIN) // GRID_ROWS


def region_rect(region):
    row, col = divmod(region, GRID_COLS)
    return pygame.Rect(MARGIN + col * CELL_W, BOARD_TOP + row * CELL_H, CELL_W - 4, CELL_H - 4)


REGION_RECTS = [region_rect(r) for r in range(GRID_COLS * GRID_ROWS)]


def region_at(pos):
    for r, rect in enumerate(REGION_RECTS):
        if rect.collidepoint(pos):
            return r
    return None


def faded(color, amount=0.45):
    """Mix a player color with the neutral gray (for locked selections)."""
    return tuple(int(n + (c - n) * amount) for c, n in zip(color, NEUTRAL))


def draw_castle(screen, rect, towers, total=3):
    """Base marker: one small tower per life, dark once destroyed."""
    w, h, gap = 14, 24, 6
    x0 = rect.right - total * (w + gap) - 4
    y = rect.bottom - h - 8
    text(screen, "BASE", (x0, y - 20), WHITE, size=20)
    for i in range(total):
        tower = pygame.Rect(x0 + i * (w + gap), y, w, h)
        pygame.draw.rect(screen, WHITE if i < towers else (55, 55, 60), tower)
        pygame.draw.rect(screen, (30, 30, 40), tower, 2)


def draw_board(screen, owner, my_pick=None, contested=None, my_color=WHITE,
               selections=None, selectable=(), bases=None):
    """owner: {region: player}. selections: {region: player} shown faded (locked).
    selectable: regions the viewer may click. bases: {region: towers left}.
    Region labels are 1-based for players."""
    selections = selections or {}
    bases = bases or {}
    for r, rect in enumerate(REGION_RECTS):
        p = owner.get(r)
        if p is not None:
            color = PLAYER_COLORS[p]
        elif r in selections:
            color = faded(PLAYER_COLORS[selections[r]])
        else:
            color = NEUTRAL
        pygame.draw.rect(screen, color, rect)
        text(screen, str(r + 1), (rect.x + 8, rect.y + 6), (230, 230, 230), size=26)
        if r in bases:
            draw_castle(screen, rect, bases[r])
        if r in selectable:
            pygame.draw.rect(screen, (200, 200, 210), rect, 2)
        if r == my_pick:
            pygame.draw.rect(screen, my_color, rect, 5)
        if r == contested:
            t = pygame.time.get_ticks() // 300 % 2
            pygame.draw.rect(screen, (255, 210, 60) if t else WHITE, rect, 5)


# ---- popups -------------------------------------------------------------

CARD = (44, 46, 62)
CARD_BORDER = (90, 95, 125)
GREEN = (80, 200, 120)
RED = (230, 80, 80)


def wrap_text(s, size, width):
    """Split `s` into lines that fit `width` pixels."""
    words, lines, line = s.split(), [], ""
    for w in words:
        test = f"{line} {w}".strip()
        if font(size).size(test)[0] <= width or not line:
            line = test
        else:
            lines.append(line)
            line = w
    if line:
        lines.append(line)
    return lines


def ease_out_back(t):
    """0 -> 1 with a small overshoot, for the 'pop' effect."""
    c = 1.70158
    t -= 1
    return 1 + (c + 1) * t * t * t + c * t * t


def dim(screen, alpha):
    shade = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
    shade.fill((10, 10, 18, int(alpha)))
    screen.blit(shade, (0, 0))


def draw_card(surface, rect, accent=None, radius=14):
    pygame.draw.rect(surface, CARD, rect, border_radius=radius)
    pygame.draw.rect(surface, accent or CARD_BORDER, rect, 3, border_radius=radius)


def draw_mark(surface, center, ok, r=11):
    """A filled circle with a check (ok) or a cross."""
    x, y = center
    pygame.draw.circle(surface, GREEN if ok else RED, center, r)
    if ok:
        pygame.draw.lines(surface, WHITE, False, [(x - 5, y), (x - 1, y + 4), (x + 6, y - 4)], 3)
    else:
        pygame.draw.line(surface, WHITE, (x - 4, y - 4), (x + 4, y + 4), 3)
        pygame.draw.line(surface, WHITE, (x - 4, y + 4), (x + 4, y - 4), 3)


def timer_color(fraction):
    if fraction > 0.5:
        return GREEN
    if fraction > 0.25:
        return (240, 200, 60)
    return RED

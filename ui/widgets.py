"""Shared drawing pieces in the medieval style: leather background, parchment
panels, wooden buttons, wax seals, heraldic shields and serif text."""
import random

import pygame

WIDTH, HEIGHT = 900, 600
MARGIN = 20
BOARD_TOP = 150

# ---- palette ------------------------------------------------------------------
# On the dark leather background
BG = (38, 27, 19)
WHITE = (238, 224, 192)          # main text: parchment
GRAY = (168, 146, 110)           # secondary text: faded parchment
GOLD = (222, 178, 84)
# On parchment
PARCH = (228, 210, 170)
PARCH_DARK = (206, 184, 140)
INK = (62, 40, 20)
INK_SOFT = (112, 82, 50)
OXBLOOD = (120, 36, 30)
WAX = (150, 36, 30)
# Players: heraldic crimson, azure and vert, bright enough to read on leather
PLAYER_COLORS = [(204, 66, 54), (82, 122, 204), (88, 162, 94)]
NEUTRAL = (90, 90, 90)

_fonts = {}


def font(size=30, bold=False, italic=False):
    """Serif font. Sizes follow the old default font, so layouts keep fitting."""
    key = (size, bold, italic)
    if key not in _fonts:
        _fonts[key] = pygame.font.SysFont(
            "palatino,palatinolinotype,bookantiqua,georgia,timesnewroman,serif",
            max(8, int(size * 0.74)), bold=bold, italic=italic)
    return _fonts[key]


def text(screen, s, pos, color=WHITE, size=30, center=False, bold=False, italic=False):
    surf = font(size, bold, italic).render(s, True, color)
    rect = surf.get_rect(center=pos) if center else surf.get_rect(topleft=pos)
    screen.blit(surf, rect)
    return rect


def opaque_surface(size):
    """A surface with no alpha channel (see ui/mapview.py: on macOS a plain
    Surface can carry alpha, and layered drawing can turn it black)."""
    return pygame.Surface(size, 0, 24)


# ---- textures -------------------------------------------------------------------

_textures = {}


def _grain(surf, base, amount, seed, density=40):
    rng = random.Random(seed)
    w, h = surf.get_size()
    for _ in range(w * h // density):
        d = rng.randint(-amount, amount)
        surf.set_at((rng.randrange(w), rng.randrange(h)),
                    tuple(max(0, min(255, c + d)) for c in base))


def leather():
    """Full-screen dark leather background with grain and a soft vignette."""
    if "leather" not in _textures:
        surf = opaque_surface((WIDTH, HEIGHT))
        surf.fill(BG)
        _grain(surf, BG, 7, 7, density=6)
        shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        for i in range(40):
            pygame.draw.rect(shade, (0, 0, 0, 5), (i, i, WIDTH - 2 * i, HEIGHT - 2 * i), 1)
        surf.blit(shade, (0, 0))
        _textures["leather"] = surf
    return _textures["leather"]


def parchment():
    """A parchment texture to cut panels from."""
    if "parchment" not in _textures:
        surf = opaque_surface((WIDTH, HEIGHT))
        surf.fill(PARCH)
        _grain(surf, PARCH, 12, 3, density=30)
        stains = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        rng = random.Random(11)
        for _ in range(12):
            r = rng.randint(20, 70)
            center = (rng.randrange(WIDTH), rng.randrange(HEIGHT))
            for k in range(r, 0, -6):
                pygame.draw.circle(stains, (150, 115, 60, 3), center, k)
        surf.blit(stains, (0, 0))
        _textures["parchment"] = surf
    return _textures["parchment"]


def draw_background(screen):
    screen.blit(leather(), (0, 0))


# ---- panels and ornaments ----------------------------------------------------

def draw_panel(surface, rect, header=None, header_h=40):
    """A parchment sheet with a double ink border and corner ornaments.
    With `header`, an oxblood ribbon with gold lettering runs across the top."""
    rect = pygame.Rect(rect)
    shadow = pygame.Surface(rect.size, pygame.SRCALPHA)
    shadow.fill((0, 0, 0, 70))
    surface.blit(shadow, rect.move(5, 6))
    # Cut the sheet from a different spot of the texture per panel, staying inside it.
    sx = (rect.x * 7) % max(1, WIDTH - rect.w + 1)
    sy = (rect.y * 5) % max(1, HEIGHT - rect.h + 1)
    surface.blit(parchment(), rect, pygame.Rect(sx, sy, *rect.size))
    edge = pygame.Surface(rect.size, pygame.SRCALPHA)
    for i in range(10):                                   # darker, aged edges
        pygame.draw.rect(edge, (120, 85, 40, 9), (i, i, rect.w - 2 * i, rect.h - 2 * i), 1)
    surface.blit(edge, rect)
    pygame.draw.rect(surface, INK, rect, 3)
    pygame.draw.rect(surface, INK_SOFT, rect.inflate(-12, -12), 1)
    for x, y in (rect.topleft, (rect.right - 1, rect.y), (rect.x, rect.bottom - 1),
                 (rect.right - 1, rect.bottom - 1)):
        pygame.draw.circle(surface, INK, (x, y), 6)
        pygame.draw.circle(surface, GOLD, (x, y), 3)
    if header is not None:
        band = pygame.Rect(rect.x + 3, rect.y + 3, rect.w - 6, header_h)
        pygame.draw.rect(surface, OXBLOOD, band)
        pygame.draw.line(surface, GOLD, band.bottomleft, (band.right - 1, band.bottom), 2)
        pygame.draw.line(surface, (90, 26, 22), (band.x, band.y + 3), (band.right - 1, band.y + 3), 1)
        text(surface, header, (band.x + 16, band.y + (header_h - font(28, True).get_height()) // 2),
             GOLD, size=28, bold=True)
    return rect


def draw_shield(surface, center, color, size=11):
    """A small heraldic shield in a player's color."""
    x, y = center
    s = size
    pts = [(x - s, y - s), (x + s, y - s), (x + s, y + s * 0.2),
           (x, y + s * 1.2), (x - s, y + s * 0.2)]
    pygame.draw.polygon(surface, color, pts)
    pygame.draw.polygon(surface, INK, pts, 2)
    pygame.draw.line(surface, (255, 255, 255), (x - s + 3, y - s + 3), (x - s + 3, y), 1)


def draw_seal(surface, center, label, r=14, color=WAX, label_color=GOLD):
    """A red wax seal with a numeral, used for answer keys."""
    x, y = center
    for dx, dy in ((-2, 1), (2, -1), (1, 2), (-1, -2)):                  # uneven wax edge
        pygame.draw.circle(surface, color, (x + dx, y + dy), r - 1)
    pygame.draw.circle(surface, (110, 24, 20), (x, y), r - 4, 1)
    text(surface, label, (x, y + 1), label_color, size=26, center=True, bold=True)


# ---- controls --------------------------------------------------------------------

WOOD = (104, 70, 40)
WOOD_GREEN = (62, 88, 50)
WOOD_RED = (118, 44, 34)


class Button:
    def __init__(self, rect, label, enabled=True):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.enabled = enabled

    def clicked(self, event):
        return (self.enabled and event.type == pygame.MOUSEBUTTONDOWN
                and event.button == 1 and self.rect.collidepoint(event.pos))

    def draw(self, screen, color=WOOD):
        """A wooden plaque with a gold rim and brass rivets."""
        hover = self.enabled and self.rect.collidepoint(pygame.mouse.get_pos())
        fill = color if self.enabled else (78, 64, 50)
        if hover:
            fill = tuple(min(255, c + 22) for c in fill)
        r = self.rect
        pygame.draw.rect(screen, (20, 12, 6), r.move(0, 3), border_radius=5)       # drop shadow
        pygame.draw.rect(screen, fill, r, border_radius=5)
        pygame.draw.line(screen, tuple(min(255, c + 35) for c in fill),
                         (r.x + 5, r.y + 2), (r.right - 6, r.y + 2), 2)           # top highlight
        pygame.draw.rect(screen, GOLD if self.enabled else (110, 92, 70), r, 2, border_radius=5)
        for rx in (r.x + 9, r.right - 10):                                         # rivets
            pygame.draw.circle(screen, (60, 40, 20), (rx, r.centery), 4)
            pygame.draw.circle(screen, GOLD if self.enabled else (130, 110, 84), (rx, r.centery), 2)
        text(screen, self.label, r.center, WHITE if self.enabled else GRAY,
             size=28, center=True, bold=True)


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
        """A parchment strip with ink lettering and a quill-line underline."""
        r = self.rect
        screen.blit(parchment(), r, pygame.Rect(40, 40, *r.size))
        pygame.draw.rect(screen, GOLD if self.active else INK_SOFT, r, 2)
        pygame.draw.line(screen, INK_SOFT, (r.x + 8, r.bottom - 8), (r.right - 8, r.bottom - 8), 1)
        shown, color = (self.value, INK) if self.value else (self.placeholder, (150, 124, 90))
        caret = "|" if self.active and pygame.time.get_ticks() // 500 % 2 else ""
        text(screen, shown + caret, (r.x + 12, r.y + (r.h - font(30).get_height()) // 2 - 2),
             color, italic=not self.value)


def draw_timer(screen, seconds, center=(WIDTH - MARGIN - 34, 40), r=26):
    """Seconds left inside a gold ring."""
    pygame.draw.circle(screen, (24, 16, 10), center, r)
    pygame.draw.circle(screen, GOLD, center, r, 2)
    pygame.draw.circle(screen, (120, 90, 40), center, r - 5, 1)
    text(screen, f"{seconds:0.0f}", center, WHITE, size=34, center=True, bold=True)


# ---- the map ----------------------------------------------------------------

BOARD_AREA = pygame.Rect(MARGIN, BOARD_TOP, WIDTH - 2 * MARGIN, HEIGHT - BOARD_TOP - MARGIN)
_map_view = None


def map_view():
    """The shared parchment map, built on first use (needs pygame initialized)."""
    global _map_view
    if _map_view is None:
        from ui.mapview import MapView
        _map_view = MapView(BOARD_AREA)
    return _map_view


def region_at(pos):
    return map_view().region_at(pos)


def region_name(region):
    return map_view().names[region]


def draw_board(screen, owner, my_pick=None, contested=None, my_color=None,
               selections=None, selectable=(), bases=None):
    """owner: {region: player}. selections: {region: player} locked selections.
    selectable: regions the viewer may click. bases: {region: towers left}."""
    map_view().draw(screen, owner, my_pick=my_pick, contested=contested, my_color=my_color,
                    selections=selections, selectable=selectable, bases=bases)


# ---- popups -------------------------------------------------------------

GREEN = (78, 120, 56)       # ink green, for right answers and plenty of time
RED = (156, 42, 32)         # red ink, for wrong answers and little time


def wrap_text(s, size, width, bold=False):
    """Split `s` into lines that fit `width` pixels."""
    words, lines, line = s.split(), [], ""
    for w in words:
        test = f"{line} {w}".strip()
        if font(size, bold).size(test)[0] <= width or not line:
            line = test
        else:
            lines.append(line)
            line = w
    if line:
        lines.append(line)
    return lines


def fit_text(s, width, size, min_size):
    """Shrink `s` from `size` toward `min_size` until it fits `width` pixels;
    if it still doesn't fit, cut it short with an ellipsis."""
    while size > min_size and font(size).size(s)[0] > width:
        size -= 2
    if font(size).size(s)[0] > width:
        while s and font(size).size(s + "…")[0] > width:
            s = s[:-1]
        s = s.rstrip() + "…"
    return s, size


def ease_out_back(t):
    """0 -> 1 with a small overshoot, for the 'pop' effect."""
    c = 1.70158
    t -= 1
    return 1 + (c + 1) * t * t * t + c * t * t


def dim(screen, alpha):
    shade = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
    shade.fill((18, 10, 4, int(alpha)))
    screen.blit(shade, (0, 0))


def draw_mark(surface, center, ok, r=11):
    """An ink-stamped check (ok) or cross."""
    x, y = center
    pygame.draw.circle(surface, GREEN if ok else RED, center, r)
    pygame.draw.circle(surface, INK, center, r, 1)
    if ok:
        pygame.draw.lines(surface, PARCH, False, [(x - 5, y), (x - 1, y + 4), (x + 6, y - 4)], 3)
    else:
        pygame.draw.line(surface, PARCH, (x - 4, y - 4), (x + 4, y + 4), 3)
        pygame.draw.line(surface, PARCH, (x - 4, y + 4), (x + 4, y - 4), 3)


def timer_color(fraction):
    if fraction > 0.5:
        return GREEN
    if fraction > 0.25:
        return (190, 140, 40)
    return RED

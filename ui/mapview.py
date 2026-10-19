"""The game map drawn as an old parchment map.

The static parts (parchment, sea, land, rivers, mountains, borders, compass)
are rendered once. Each frame adds the players' color washes, locked
selections, highlights, castles and labels on top.
"""
import json
import math
import random

import pygame

from game.board import MAP_PATH

# ---- palette ----------------------------------------------------------------
PARCHMENT = (226, 207, 166)
PARCHMENT_DARK = (196, 170, 122)
LAND = (241, 229, 199)
INK = (74, 48, 24)
INK_SOFT = (122, 88, 52)
INK_FAINT = (176, 148, 108)
RIVER = (78, 104, 128)
SEA_INK = (128, 128, 118)
GOLD = (196, 150, 60)

# Player colors as heraldic watercolor: crimson, azure, vert.
WASH = [(176, 42, 38), (40, 78, 156), (46, 118, 64)]

# Carpathian ridges (lon, lat) for the drawn mountains.
RIDGES = [
    [(24.2, 47.75), (24.7, 47.6), (25.2, 47.42), (25.5, 47.2), (25.72, 46.95), (25.86, 46.7),
     (25.96, 46.45), (26.08, 46.2), (26.18, 45.95), (26.25, 45.72), (26.05, 45.52),
     (25.65, 45.45), (25.25, 45.45), (24.85, 45.5), (24.45, 45.55), (24.05, 45.5),
     (23.65, 45.42), (23.25, 45.36), (22.85, 45.3), (22.45, 45.22), (22.15, 45.08)],
    [(22.65, 46.85), (22.85, 46.62), (23.05, 46.42), (23.2, 46.25)],
]

_fonts = {}


def serif(size, italic=False, bold=False):
    key = (size, italic, bold)
    if key not in _fonts:
        f = pygame.font.SysFont("palatino,palatinolinotype,bookantiqua,georgia,timesnewroman,serif",
                                size, bold=bold, italic=italic)
        _fonts[key] = f
    return _fonts[key]


def ink_text(surface, s, center, size=18, color=INK, italic=False, bold=False, halo=True):
    """Text with a soft parchment halo so it reads over borders and washes."""
    font = serif(size, italic, bold)
    img = font.render(s, True, color)
    rect = img.get_rect(center=center)
    if halo:
        glow = font.render(s, True, LAND)
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            surface.blit(glow, rect.move(dx, dy))
    surface.blit(img, rect)
    return rect


class MapView:
    def __init__(self, area):
        """`area` is the screen rect the map panel fills."""
        with open(MAP_PATH, encoding="utf-8") as f:
            data = json.load(f)
        self.area = pygame.Rect(area)
        self.lands = data["lands"]
        self.names = [land["name"] for land in self.lands]
        proj = data["projection"]
        self._proj = (proj["lat0"], proj["x0"], proj["y0"], proj["span"])

        pad = 16
        scale = min((self.area.w - 2 * pad) / 1.0, (self.area.h - 2 * pad) / data["aspect"])
        self.scale = scale
        w, h = int(scale) + 1, int(scale * data["aspect"]) + 1
        self.map_rect = pygame.Rect(0, 0, w, h)
        self.map_rect.center = self.area.center
        self.data = data

        self._build_raster()
        self._build_masks()
        self.base = self._render_base()
        self._wash_cache = {}
        self._hatch_cache = {}

    # ---- coordinates --------------------------------------------------

    def to_map(self, pt):
        """Normalized map coordinates -> pixels inside the map raster."""
        return (pt[0] * self.scale, pt[1] * self.scale)

    def lonlat(self, lon, lat):
        lat0, x0, y0, span = self._proj
        nx = (lon * math.cos(math.radians(lat0)) - x0) / span
        ny = (-lat - y0) / span
        return self.to_map((nx, ny))

    def anchor(self, land):
        """Screen position for a land's castle and label."""
        x, y = self.to_map(self.lands[land]["anchor"])
        return int(self.map_rect.x + x), int(self.map_rect.y + y)

    def region_at(self, pos):
        x, y = pos[0] - self.map_rect.x, pos[1] - self.map_rect.y
        if not (0 <= x < self.map_rect.w and 0 <= y < self.map_rect.h):
            return None
        r, g, _, _ = self.raster.get_at((x, y))
        return r if g == 0 else None

    # ---- one-time rendering -------------------------------------------

    def _build_raster(self):
        """Land ids painted as colors (red = id, green 0 = land) for clicks and masks."""
        self.raster = pygame.Surface(self.map_rect.size)
        self.raster.fill((255, 255, 255))
        self.county_rings = []       # county borders to draw (not Bucharest: it's a city mark)
        for county in self.data["counties"]:
            for i, ring in enumerate(county["rings"]):
                pts = [self.to_map(p) for p in ring]
                if county["code"] != "B" and i == 0:
                    self.county_rings.append(pts)
                color = (county["land"], 0, 0) if i == 0 else (255, 255, 255)
                pygame.draw.polygon(self.raster, color, pts)
        # Bucharest sits in Ilfov's hole, which was just painted as empty.
        for county in self.data["counties"]:
            if county["code"] == "B":
                pygame.draw.polygon(self.raster, (county["land"], 0, 0),
                                    [self.to_map(p) for p in county["rings"][0]])

    def _build_masks(self):
        self.masks = []
        self.outlines = []
        for land in range(len(self.lands)):
            m = pygame.mask.from_threshold(self.raster, (land, 0, 0, 255), (1, 1, 1, 255))
            self.masks.append(m)
            outlines = []
            for comp in m.connected_components(minimum=30):
                pts = comp.outline(2)
                if len(pts) > 2:
                    outlines.append([(x + self.map_rect.x, y + self.map_rect.y) for x, y in pts])
            self.outlines.append(outlines)
        self.land_mask = pygame.mask.from_threshold(self.raster, (0, 0, 0, 255), (64, 1, 1, 255))

    def _render_base(self):
        rng = random.Random(1492)
        surf = pygame.Surface(self.area.size)
        surf.fill(PARCHMENT)
        w, h = self.area.size
        ox, oy = self.map_rect.x - self.area.x, self.map_rect.y - self.area.y

        # Parchment grain and stains.
        for _ in range(w * h // 60):
            x, y = rng.randrange(w), rng.randrange(h)
            d = rng.randint(-14, 10)
            c = tuple(max(0, min(255, v + d)) for v in PARCHMENT)
            surf.set_at((x, y), c)
        stains = pygame.Surface((w, h), pygame.SRCALPHA)
        for _ in range(10):
            r = rng.randint(25, 80)
            center = (rng.randrange(w), rng.randrange(h))
            for k in range(r, 0, -6):
                pygame.draw.circle(stains, (150, 115, 60, 3), center, k)
        surf.blit(stains, (0, 0))

        self._draw_sea(surf, ox, oy, rng)

        # Land: cream fill with a faint ink shadow along the coast and borders.
        land_surf = self.land_mask.to_surface(setcolor=(*LAND, 255), unsetcolor=(0, 0, 0, 0))
        shadow = self.land_mask.to_surface(setcolor=(120, 90, 50, 70), unsetcolor=(0, 0, 0, 0))
        surf.blit(shadow, (ox + 3, oy + 3))
        surf.blit(land_surf, (ox, oy))

        self._draw_mountains(surf, ox, oy, rng)

        # County borders: faint dotted ink.
        for ring in self.county_rings:
            pts = [(x + ox, y + oy) for x, y in ring]
            for i in range(0, len(pts) - 1, 2):
                pygame.draw.line(surf, INK_FAINT, pts[i], pts[i + 1], 1)

        # Land borders and the country outline, from the raster.
        self._draw_raster_borders(surf, ox, oy)
        self._draw_rivers(surf, ox, oy)

        self._draw_capital(surf, ox, oy)
        self._draw_compass(surf, rng)
        self._draw_frame(surf)
        return surf

    def _draw_sea(self, surf, ox, oy, rng):
        """The Black Sea east of Dobrogea, with wavy hatching."""
        dobrogea = next(i for i, l in enumerate(self.lands) if l["name"] == "Dobrogea")
        w, h = self.map_rect.size
        coast = {}
        for y in range(h):
            for x in range(w - 1, -1, -1):
                r, g, _, _ = self.raster.get_at((x, y))
                if g == 0:
                    if r == dobrogea:
                        coast[y] = x
                    break
        if not coast:
            return
        top = min(coast)
        last = coast[max(coast)]
        sea = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        for y in range(top + oy, surf.get_height()):
            my = y - oy
            cx = coast.get(my)
            if cx is None:
                if my < max(coast):
                    continue
                cx = last + (my - max(coast)) // 3        # the coast keeps going south
            fade = min(1.0, (y - top - oy) / 40)
            sea.fill((150, 160, 150, int(40 * fade)), (cx + ox + 2, y, surf.get_width() - cx - ox, 1))
        surf.blit(sea, (0, 0))
        for y in range(top + oy + 24, surf.get_height() - 14, 9):
            my = min(max(y - oy, top), max(coast))
            start = coast.get(my, last) + ox + 10
            for x in range(start, surf.get_width() - 20, 22):
                pts = [(x + i, y + 2 * math.sin((x + i) / 4.0)) for i in range(0, 12, 2)]
                pygame.draw.lines(surf, SEA_INK, False, pts, 1)
        cx = surf.get_width() - 70
        ink_text(surf, "Pontus", (cx, oy + int(self.map_rect.h * 0.62)), 18, INK_SOFT, italic=True,
                 halo=False)
        ink_text(surf, "Euxinus", (cx, oy + int(self.map_rect.h * 0.62) + 20), 18, INK_SOFT,
                 italic=True, halo=False)

    def _draw_mountains(self, surf, ox, oy, rng):
        for ridge in RIDGES:
            pts = [self.lonlat(lon, lat) for lon, lat in ridge]
            for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
                seg = math.hypot(x2 - x1, y2 - y1)
                steps = max(1, int(seg / 9))
                for i in range(steps):
                    t = i / steps
                    x = x1 + (x2 - x1) * t + rng.uniform(-3, 3) + ox
                    y = y1 + (y2 - y1) * t + rng.uniform(-3, 3) + oy
                    s = rng.uniform(6, 9)
                    peak = [(x - s, y + s * 0.7), (x, y - s * 0.8), (x + s, y + s * 0.7)]
                    pygame.draw.polygon(surf, (232, 218, 186), peak)
                    pygame.draw.polygon(surf, (205, 186, 148), [peak[1], peak[2], (x, y + s * 0.7)])
                    pygame.draw.lines(surf, INK_SOFT, False, peak, 2)

    def _draw_rivers(self, surf, ox, oy):
        for river in self.data["rivers"]:
            pts = [(x + ox, y + oy) for x, y in (self.to_map(p) for p in river["points"])]
            width = 3 if river["name"] == "Danube" else 1
            pygame.draw.lines(surf, RIVER, False, pts, width)
            if width > 1:
                pygame.draw.lines(surf, (130, 156, 176), False, pts, 1)

    def _draw_raster_borders(self, surf, ox, oy):
        w, h = self.map_rect.size
        get = self.raster.get_at
        land_border = []
        coast = []
        for y in range(h - 1):
            for x in range(w - 1):
                a = get((x, y))
                for b in (get((x + 1, y)), get((x, y + 1))):
                    if a == b:
                        continue
                    a_land, b_land = a[1] == 0, b[1] == 0
                    if a_land and b_land:
                        land_border.append((x + ox, y + oy))
                    elif a_land or b_land:
                        coast.append((x + ox, y + oy))
        for x, y in land_border:
            pygame.draw.rect(surf, INK_SOFT, (x, y, 2, 2))
        for x, y in coast:
            pygame.draw.rect(surf, INK, (x - 1, y - 1, 3, 3))

    def _draw_capital(self, surf, ox, oy):
        """Bucharest as a walled-city mark."""
        ring = next(c["rings"][0] for c in self.data["counties"] if c["code"] == "B")
        pts = [self.to_map(p) for p in ring]
        x = int(sum(p[0] for p in pts) / len(pts)) + ox
        y = int(sum(p[1] for p in pts) / len(pts)) + oy
        pygame.draw.circle(surf, LAND, (x, y), 5)
        pygame.draw.circle(surf, INK, (x, y), 5, 1)
        pygame.draw.circle(surf, INK, (x, y), 2)

    def _draw_compass(self, surf, rng):
        cx, cy, r = 70, surf.get_height() - 78, 42
        pygame.draw.circle(surf, INK_SOFT, (cx, cy), r, 1)
        pygame.draw.circle(surf, INK_SOFT, (cx, cy), r - 6, 1)
        for i in range(16):
            a = math.radians(i * 22.5)
            inner = r - 6 if i % 2 else r - 12
            pygame.draw.line(surf, INK_FAINT, (cx + math.sin(a) * inner, cy - math.cos(a) * inner),
                             (cx + math.sin(a) * (r - 1), cy - math.cos(a) * (r - 1)), 1)
        for i in range(4):
            a = math.radians(i * 90)
            tip = (cx + math.sin(a) * (r + 6), cy - math.cos(a) * (r + 6))
            left = (cx + math.sin(a - 1.57) * 7, cy - math.cos(a - 1.57) * 7)
            right = (cx + math.sin(a + 1.57) * 7, cy - math.cos(a + 1.57) * 7)
            pygame.draw.polygon(surf, INK if i == 0 else LAND, [tip, left, (cx, cy)])
            pygame.draw.polygon(surf, INK_SOFT, [tip, right, (cx, cy)])
            pygame.draw.lines(surf, INK, True, [tip, left, (cx, cy), right], 1)
        ink_text(surf, "N", (cx, cy - r - 16), 16, INK, bold=True, halo=False)

    def _draw_frame(self, surf):
        w, h = surf.get_size()
        edge = pygame.Surface((w, h), pygame.SRCALPHA)
        for i in range(18):                                  # darker, burnt edges
            pygame.draw.rect(edge, (110, 75, 35, 10), (i, i, w - 2 * i, h - 2 * i), 1)
        surf.blit(edge, (0, 0))
        pygame.draw.rect(surf, INK, (0, 0, w, h), 3)
        pygame.draw.rect(surf, INK_SOFT, (6, 6, w - 12, h - 12), 1)
        for x, y in ((6, 6), (w - 7, 6), (6, h - 7), (w - 7, h - 7)):
            pygame.draw.circle(surf, INK_SOFT, (x, y), 4, 1)

    # ---- per-frame overlays -------------------------------------------

    def _wash(self, land, player):
        key = (land, player)
        if key not in self._wash_cache:
            self._wash_cache[key] = self.masks[land].to_surface(
                setcolor=(*WASH[player], 120), unsetcolor=(0, 0, 0, 0))
        return self._wash_cache[key]

    def _hatch(self, land, player):
        """Diagonal hatching in a player's color: a locked selection."""
        key = (land, player)
        if key not in self._hatch_cache:
            w, h = self.map_rect.size
            hatch = pygame.Surface((w, h), pygame.SRCALPHA)
            for x in range(-h, w, 7):
                pygame.draw.line(hatch, (*WASH[player], 190), (x, 0), (x + h, h), 2)
            cut = self.masks[land].to_surface(setcolor=(255, 255, 255, 255), unsetcolor=(0, 0, 0, 0))
            hatch.blit(cut, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            self._hatch_cache[key] = hatch
        return self._hatch_cache[key]

    def outline(self, screen, land, color, width):
        for pts in self.outlines[land]:
            pygame.draw.lines(screen, color, True, pts, width)

    def draw(self, screen, owner, my_pick=None, contested=None, my_color=None,
             selections=None, selectable=(), bases=None):
        """owner: {land: player}. selections: {land: player} locked, shown hatched.
        selectable: lands the viewer may click. bases: {land: towers left}."""
        selections = selections or {}
        bases = bases or {}
        screen.blit(self.base, self.area.topleft)
        at = self.map_rect.topleft
        for land, player in owner.items():
            screen.blit(self._wash(land, player), at)
        for land, player in selections.items():
            if land not in owner:
                screen.blit(self._hatch(land, player), at)
        for land in selectable:
            self.outline(screen, land, GOLD, 2)
        if my_pick is not None:
            self.outline(screen, my_pick, my_color or INK, 4)
        if contested is not None:
            t = pygame.time.get_ticks() // 300 % 2
            self.outline(screen, contested, GOLD if t else LAND, 4)
        for land in range(len(self.lands)):
            x, y = self.anchor(land)
            if land in bases:
                draw_castle(screen, (x, y - 4), bases[land], owner.get(land))
                ink_text(screen, self.names[land], (x, y + 20), 15)
            else:
                ink_text(screen, self.names[land], (x, y), 15)


def draw_castle(surface, center, towers, player=None, total=3):
    """An ink-drawn keep with `total` towers; fallen towers are drawn as ruins.
    A pennant in the owner's color flies from the keep."""
    cx, cy = center
    stone, line = (238, 226, 196), INK
    tower_w, gap = 9, 3
    width = total * tower_w + (total - 1) * gap
    left = cx - width // 2
    base_y = cy + 10
    wall = pygame.Rect(left - 2, base_y - 8, width + 4, 8)
    pygame.draw.rect(surface, stone, wall)
    pygame.draw.rect(surface, line, wall, 1)
    for i in range(total):
        x = left + i * (tower_w + gap)
        standing = i < towers
        height = 18 if standing else 8
        body = pygame.Rect(x, base_y - height, tower_w, height)
        pygame.draw.rect(surface, stone if standing else (200, 186, 156), body)
        pygame.draw.rect(surface, line, body, 1)
        if standing:
            for cx2 in (x, x + tower_w - 3):                # crenellations
                merlon = pygame.Rect(cx2, body.y - 3, 3, 3)
                pygame.draw.rect(surface, stone, merlon)
                pygame.draw.rect(surface, line, merlon, 1)
            pygame.draw.line(surface, line, (x + tower_w // 2, body.y + 5),
                             (x + tower_w // 2, body.y + 8), 1)   # arrow slit
        else:                                              # broken top
            pygame.draw.lines(surface, line, False,
                              [(x, body.y), (x + 3, body.y - 3), (x + 5, body.y), (x + tower_w, body.y - 2)], 1)
    if player is not None:
        mast_x = cx
        top = base_y - 30
        pygame.draw.line(surface, line, (mast_x, base_y - 18), (mast_x, top), 1)
        pygame.draw.polygon(surface, WASH[player], [(mast_x, top), (mast_x + 11, top + 3), (mast_x, top + 6)])
        pygame.draw.polygon(surface, line, [(mast_x, top), (mast_x + 11, top + 3), (mast_x, top + 6)], 1)

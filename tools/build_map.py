"""Build data/map.json from Natural Earth data (public domain).

Run once by a developer; the game only reads the generated file and makes no
network calls. Download the two Natural Earth GeoJSON files first:

    ne_10m_admin_1_states_provinces.geojson
    ne_10m_rivers_lake_centerlines.geojson

from https://github.com/nvkelso/natural-earth-vector (geojson/ folder), then:

    python tools/build_map.py ADMIN1.geojson RIVERS.geojson

This groups Romania's 42 counties into the game's lands, projects them to
normalized map coordinates, and precomputes which lands border each other and
where to put each land's label and castle.
"""
import json
import math
import os
import sys
from collections import deque
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402  (used only to rasterize for adjacency)

OUT = Path(__file__).resolve().parent.parent / "data" / "map.json"

# Game lands: neighboring counties merged into historical-style regions.
LANDS = [
    ("Maramureș", ["MM", "SM"]),
    ("Crișana", ["BH", "SJ"]),
    ("Banat", ["TM", "AR"]),
    ("Severin", ["CS", "MH"]),
    ("Hunedoara", ["HD"]),
    ("Alba", ["AB", "SB"]),
    ("Cluj", ["CJ", "BN"]),
    ("Mureș", ["MS", "HR"]),
    ("Țara Bârsei", ["BV", "CV"]),
    ("Bucovina", ["SV", "BT"]),
    ("Iași", ["IS", "VS"]),
    ("Neamț", ["NT", "BC"]),
    ("Vrancea", ["VN", "GL"]),
    ("Dobrogea", ["TL", "CT"]),
    ("Oltenia de Sus", ["GJ", "VL"]),
    ("Oltenia", ["DJ", "OT"]),
    ("Argeș", ["AG", "DB"]),
    ("Prahova", ["PH", "BZ"]),
    ("Bărăgan", ["IL", "CL", "BR"]),
    ("Vlașca", ["B", "IF", "GR", "TR"]),
]

# County names with Romanian diacritics (Natural Earth names are mostly ASCII).
COUNTY_NAMES = {
    "AB": "Alba", "AG": "Argeș", "AR": "Arad", "B": "București", "BC": "Bacău",
    "BH": "Bihor", "BN": "Bistrița-Năsăud", "BR": "Brăila", "BT": "Botoșani",
    "BV": "Brașov", "BZ": "Buzău", "CJ": "Cluj", "CL": "Călărași",
    "CS": "Caraș-Severin", "CT": "Constanța", "CV": "Covasna", "DB": "Dâmbovița",
    "DJ": "Dolj", "GJ": "Gorj", "GL": "Galați", "GR": "Giurgiu", "HD": "Hunedoara",
    "HR": "Harghita", "IF": "Ilfov", "IL": "Ialomița", "IS": "Iași", "MH": "Mehedinți",
    "MM": "Maramureș", "MS": "Mureș", "NT": "Neamț", "OT": "Olt", "PH": "Prahova",
    "SB": "Sibiu", "SJ": "Sălaj", "SM": "Satu Mare", "SV": "Suceava", "TL": "Tulcea",
    "TM": "Timiș", "TR": "Teleorman", "VL": "Vâlcea", "VN": "Vrancea", "VS": "Vaslui",
}

# Rivers drawn on the map (Natural Earth names).
RIVERS = {"Danube", "Prut", "Siret", "Olt", "Mures", "Somes", "Jiu", "Arges", "Ialomita"}

LAT0 = 45.9                          # projection center (equirectangular)
RASTER_W = 1600                      # resolution used for adjacency and labels
MIN_SHARED_PIXELS = 6                # ignore lands that only touch at a corner


def project(lon, lat):
    return lon * math.cos(math.radians(LAT0)), -lat


def rings_of(geometry):
    polys = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
    return [ring for poly in polys for ring in poly]


def main(admin1_path, rivers_path):
    admin = json.load(open(admin1_path, encoding="utf-8"))
    counties = {}
    for f in admin["features"]:
        p = f["properties"]
        if p.get("adm0_a3") != "ROU":
            continue
        code = p["iso_3166_2"].split("-")[1]
        counties[code] = [[project(lon, lat) for lon, lat in ring] for ring in rings_of(f["geometry"])]
    land_of = {c: i for i, (_, codes) in enumerate(LANDS) for c in codes}
    assert set(land_of) == set(counties), set(counties) ^ set(land_of)

    xs = [x for rings in counties.values() for ring in rings for x, _ in ring]
    ys = [y for rings in counties.values() for ring in rings for _, y in ring]
    x0, y0, span = min(xs), min(ys), max(xs) - min(xs)
    aspect = (max(ys) - y0) / span

    def norm(pt):
        return [round((pt[0] - x0) / span, 5), round((pt[1] - y0) / span, 5)]

    # ---- rasterize lands to find borders and label spots ------------------
    w, h = RASTER_W, int(RASTER_W * aspect) + 1
    surf = pygame.Surface((w, h))
    surf.fill((255, 255, 255))
    for code, rings in counties.items():
        land = land_of[code]
        for i, ring in enumerate(rings):
            pts = [((x - x0) / span * (w - 1), (y - y0) / span * (w - 1)) for x, y in ring]
            # Inner rings are holes (Ilfov around Bucharest); Bucharest fills it
            # back in, and both belong to the same land.
            pygame.draw.polygon(surf, (land, 0, 0) if i == 0 else (255, 255, 255), pts)
    grid = [[surf.get_at((x, y))[0] if surf.get_at((x, y))[1] == 0 else -1 for x in range(w)]
            for y in range(h)]

    shared = {}
    for y in range(h):
        row = grid[y]
        for x in range(w):
            a = row[x]
            if a < 0:
                continue
            for dx, dy in ((1, 0), (0, 1), (2, 0), (0, 2)):
                if x + dx < w and y + dy < h:
                    b = grid[y + dy][x + dx]
                    if b >= 0 and b != a:
                        key = (min(a, b), max(a, b))
                        shared[key] = shared.get(key, 0) + 1
    adjacency = {i: set() for i in range(len(LANDS))}
    for (a, b), n in shared.items():
        if n >= MIN_SHARED_PIXELS:
            adjacency[a].add(b)
            adjacency[b].add(a)

    # Label spot: the pixel deepest inside each land (multi-source BFS).
    dist = [[-1] * w for _ in range(h)]
    queue = deque()
    for y in range(h):
        for x in range(w):
            edge = (x in (0, w - 1) or y in (0, h - 1) or
                    any(grid[y + dy][x + dx] != grid[y][x]
                        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))))
            if edge:
                dist[y][x] = 0
                queue.append((x, y))
    while queue:
        x, y = queue.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and dist[ny][nx] < 0 and grid[ny][nx] == grid[y][x]:
                dist[ny][nx] = dist[y][x] + 1
                queue.append((nx, ny))
    best = {}
    for y in range(h):
        for x in range(w):
            land = grid[y][x]
            if land >= 0 and dist[y][x] > best.get(land, (-1,))[0]:
                best[land] = (dist[y][x], x, y)

    # ---- rivers -------------------------------------------------------------
    rivers = []
    margin = 0.03
    for f in json.load(open(rivers_path, encoding="utf-8"))["features"]:
        if f["properties"].get("name") not in RIVERS or not f["geometry"]:
            continue
        g = f["geometry"]
        lines = g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]
        for line in lines:
            part = []
            for lon, lat in line:
                nx, ny = norm(project(lon, lat))
                if -margin <= nx <= 1 + margin and -margin <= ny <= aspect + margin:
                    part.append([nx, ny])
                elif len(part) > 1:
                    rivers.append({"name": f["properties"]["name"], "points": part})
                    part = []
                else:
                    part = []
            if len(part) > 1:
                rivers.append({"name": f["properties"]["name"], "points": part})

    out = {
        "source": "Natural Earth 1:10m admin-1 and rivers (public domain), via tools/build_map.py",
        "aspect": round(aspect, 5),
        # x = (lon * cos(lat0) - x0) / span, y = (-lat - y0) / span
        "projection": {"lat0": LAT0, "x0": x0, "y0": y0, "span": span},
        "lands": [
            {"id": i, "name": name, "counties": codes,
             "neighbors": sorted(adjacency[i]),
             "anchor": [round(best[i][1] / (w - 1), 4), round(best[i][2] / (w - 1), 4)]}
            for i, (name, codes) in enumerate(LANDS)
        ],
        "counties": [
            {"code": code, "name": COUNTY_NAMES[code], "land": land_of[code],
             "rings": [[norm(pt) for pt in ring] for ring in counties[code]]}
            for code in sorted(counties)
        ],
        "rivers": rivers,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB), {len(LANDS)} lands, "
          f"{sum(len(n) for n in adjacency.values()) // 2} borders, {len(rivers)} river lines")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

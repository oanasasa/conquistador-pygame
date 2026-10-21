"""The map as the game rules see it: numbered regions and who borders whom.

The real map is Romania's counties grouped into lands (data/map.json, built by
tools/build_map.py). Tests can use a simple grid board instead.
"""
import json
from functools import lru_cache
from pathlib import Path

MAP_PATH = Path(__file__).resolve().parent.parent / "data" / "map.json"


class Board:
    def __init__(self, neighbors, names=None):
        self._neighbors = [sorted(n) for n in neighbors]
        self.num_regions = len(self._neighbors)
        self.names = names or [str(r + 1) for r in range(self.num_regions)]

    def neighbors(self, region):
        """Regions sharing a border with `region`."""
        return list(self._neighbors[region])

    def frontier(self, owner, player):
        """Regions next to `player`'s land that `player` does not own."""
        mine = {r for r, p in owner.items() if p == player}
        return sorted({n for r in mine for n in self._neighbors[r]} - mine)


def grid_board(cols, rows):
    """A cols x rows grid, numbered row by row, neighbors share an edge."""
    neighbors = []
    for region in range(cols * rows):
        row, col = divmod(region, cols)
        neighbors.append([r * cols + c
                          for r, c in ((row - 1, col), (row + 1, col), (row, col - 1), (row, col + 1))
                          if 0 <= r < rows and 0 <= c < cols])
    return Board(neighbors)


@lru_cache(maxsize=1)
def default_board():
    """The Romania map used in real games."""
    with open(MAP_PATH, encoding="utf-8") as f:
        lands = json.load(f)["lands"]
    return Board([land["neighbors"] for land in lands], [land["name"] for land in lands])

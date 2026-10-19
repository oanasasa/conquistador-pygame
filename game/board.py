"""The map: a 4 x 3 grid of regions numbered 0-11, row by row."""
COLS, ROWS = 4, 3
NUM_REGIONS = COLS * ROWS


def neighbors(region):
    """Regions sharing an edge with `region` (no diagonals)."""
    row, col = divmod(region, COLS)
    result = []
    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        r, c = row + dr, col + dc
        if 0 <= r < ROWS and 0 <= c < COLS:
            result.append(r * COLS + c)
    return result


def frontier(owner, player):
    """Regions next to `player`'s land that `player` does not own."""
    mine = {r for r, p in owner.items() if p == player}
    return sorted({n for r in mine for n in neighbors(r)} - mine)

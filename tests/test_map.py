"""The parchment map must agree with the game rules' map."""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

from game.board import default_board  # noqa: E402


def test_every_land_is_clickable_at_its_label():
    pygame.init()
    from ui.widgets import map_view, region_at
    view = map_view()
    board = default_board()
    assert len(view.lands) == board.num_regions
    for land in range(board.num_regions):
        assert region_at(view.anchor(land)) == land, view.names[land]


def test_clicks_outside_romania_hit_nothing():
    pygame.init()
    from ui.widgets import BOARD_AREA, region_at
    assert region_at((BOARD_AREA.x + 5, BOARD_AREA.y + 5)) is None
    assert region_at((BOARD_AREA.right - 5, BOARD_AREA.bottom - 5)) is None


def test_map_background_has_no_alpha_channel():
    # On macOS a plain Surface can get an alpha channel; layered drawing then
    # left map pixels transparent and the window showed them as black.
    pygame.init()
    from ui.widgets import map_view
    view = map_view()
    assert view.base.get_masks()[3] == 0
    assert view.base.get_at((view.area.w // 2, view.area.h // 2)).a == 255

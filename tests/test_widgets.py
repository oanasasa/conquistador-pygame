import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

from ui.widgets import Dropdown  # noqa: E402


def click(pos):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos)


def test_dropdown_opens_scrolls_and_picks_one():
    pygame.init()
    options = [f"Option {i}" for i in range(20)]
    d = Dropdown((10, 10, 300, 40), options, "Option 0", visible=5)
    assert d.handle(click(d.rect.center)) and d.open
    d.handle(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=-3))        # scroll down 3 rows
    assert d.scroll == 3
    row = d.list_rect()
    assert d.handle(click((row.centerx, row.y + Dropdown.ROW * 1 + 5)))
    assert d.selected == "Option 4" and not d.open


def test_dropdown_click_outside_closes_without_changing():
    pygame.init()
    d = Dropdown((10, 10, 300, 40), ["a", "b"], "a")
    d.handle(click(d.rect.center))
    assert d.handle(click((600, 500))) and not d.open and d.selected == "a"


def test_closed_dropdown_ignores_other_clicks():
    pygame.init()
    d = Dropdown((10, 10, 300, 40), ["a", "b"], "a")
    assert not d.handle(click((600, 500)))

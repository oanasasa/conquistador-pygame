# Conquistador

A game built with Python and [pygame-ce](https://pyga.me/).

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python conquistador.py
```

## Play on a LAN

1. Each player runs `python conquistador.py` and enters a username.
2. One player clicks **Create room**. Others click **Join** on the room in the
   list, or type the host's IP (shown on the host's screen) and click **Join IP**.
3. The host clicks **Start** once 2-3 players are in.

To play alone, click **Play vs bot**, then **Start**. The host can also use **Add bot** in the room to fill empty seats.

To try it on one machine, open several terminals and join `127.0.0.1`.
macOS may ask to allow incoming connections for Python; allow it so others can join.

## Sound

The game plays sounds from `assets/audio/` (see the README there for the file
names): music looping in the menus and halls, a tick each second of a riddle,
a bell when a riddle ends and a horn when it is your turn to choose land.
Missing files are simply silent. Press `M` to mute or unmute.

## Controls

- Mouse: buttons and picking regions
- `1`-`4`: answer a question
- `M`: mute or unmute
- `Esc`: quit

## Map data

The map in `data/map.json` is built from [Natural Earth](https://www.naturalearthdata.com/)
1:10m admin-1 boundaries and rivers (public domain) by `tools/build_map.py`.
The game reads only that file and makes no network calls. To change how
counties are grouped into lands, edit `LANDS` in the script and run it again
(the script's docstring says which files to download).

## Questions

When you raise a hall (create a room), you pick the lore from a list of every
[Open Trivia Database](https://opentdb.com) category, or all of them mixed, and
the rank of trial (difficulty: Any, Squire, Knight or King). The host's game
then fetches matching questions, licensed
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). They are kept
in memory for that room only; nothing is saved. Without internet the game uses
the few built-in questions in `data/questions.json`.

## Tests

```bash
python -m pytest
```

> Note: `pygame-ce` is used instead of `pygame` because the original package has no wheels for Python 3.14. It is imported the same way (`import pygame`).

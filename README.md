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

## Controls

- Mouse: buttons and picking regions
- `1`-`4`: answer a question
- `Esc`: quit

## Map data

The map in `data/map.json` is built from [Natural Earth](https://www.naturalearthdata.com/)
1:10m admin-1 boundaries and rivers (public domain) by `tools/build_map.py`.
The game reads only that file and makes no network calls. To change how
counties are grouped into lands, edit `LANDS` in the script and run it again
(the script's docstring says which files to download).

## Questions

`data/questions.json` holds the question bank. Most questions come from the
[Open Trivia Database](https://opentdb.com) (History, Art and Mythology),
licensed [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
To download a fresh set (your own questions in the file are kept):

```bash
python tools/import_opentdb.py --per-category 50
```

## Tests

```bash
python -m pytest
```

> Note: `pygame-ce` is used instead of `pygame` because the original package has no wheels for Python 3.14. It is imported the same way (`import pygame`).

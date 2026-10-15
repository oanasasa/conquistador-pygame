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

To try it on one machine, open several terminals and join `127.0.0.1`.
macOS may ask to allow incoming connections for Python; allow it so others can join.

## Controls

- Mouse: buttons and picking regions
- `1`-`3`: answer a bonus question
- `Esc`: quit

## Tests

```bash
python -m pytest
```

> Note: `pygame-ce` is used instead of `pygame` because the original package has no wheels for Python 3.14. It is imported the same way (`import pygame`).

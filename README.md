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

## Controls

- `Esc` — quit

> Note: `pygame-ce` is used instead of `pygame` because the original package has no wheels for Python 3.14. It is imported the same way (`import pygame`).

"""Newline-delimited JSON messages over a TCP socket."""
import json

GAME_PORT = 5555
DISCOVERY_PORT = 5556
MAX_PLAYERS = 3
MIN_PLAYERS = 2


def send(sock, msg):
    sock.sendall((json.dumps(msg) + "\n").encode("utf-8"))


def read_messages(sock):
    """Yield decoded messages until the connection closes."""
    buf = b""
    while True:
        try:
            chunk = sock.recv(4096)
        except OSError:
            return
        if not chunk:
            return
        buf += chunk
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            if line.strip():
                try:
                    yield json.loads(line)
                except ValueError:
                    continue

"""Client connection. A background thread puts server messages on a queue
that the pygame loop drains every frame."""
import queue
import socket
import threading

from net import protocol


class GameClient:
    def __init__(self, host, port, name):
        self.sock = socket.create_connection((host, port), timeout=3)
        self.sock.settimeout(None)
        self.inbox = queue.Queue()
        protocol.send(self.sock, {"t": "hello", "name": name})
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        for msg in protocol.read_messages(self.sock):
            self.inbox.put(msg)
        self.inbox.put({"t": "disconnected"})

    def messages(self):
        while True:
            try:
                yield self.inbox.get_nowait()
            except queue.Empty:
                return

    def send(self, msg):
        try:
            protocol.send(self.sock, msg)
        except OSError:
            self.inbox.put({"t": "disconnected"})

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass

"""LAN room discovery over UDP broadcast. LAN only, no internet."""
import json
import socket
import threading
import time

from net import protocol

TAG = "conquistador"
STALE_AFTER = 3.0


class RoomAnnouncer:
    """Host side: broadcasts the room once a second while it is in the lobby."""

    def __init__(self, server):
        self.server = server
        self.running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        while self.running and self.server.running:
            if self.server.in_lobby:
                msg = json.dumps({
                    "tag": TAG, "room": self.server.room_name, "port": self.server.port,
                    "players": self.server.player_count(), "max": protocol.MAX_PLAYERS,
                }).encode("utf-8")
                for addr in ("<broadcast>", "127.0.0.1"):
                    try:
                        sock.sendto(msg, (addr, protocol.DISCOVERY_PORT))
                    except OSError:
                        pass
            time.sleep(1.0)
        sock.close()

    def stop(self):
        self.running = False


class RoomBrowser:
    """Client side: listens for announcements and keeps a list of live rooms."""

    def __init__(self):
        self.rooms = {}          # (ip, port) -> (info, last_seen)
        self.lock = threading.Lock()
        self.running = True
        self.error = None
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        try:
            self.sock.bind(("", protocol.DISCOVERY_PORT))
            self.sock.settimeout(0.5)
            threading.Thread(target=self._loop, daemon=True).start()
        except OSError as e:
            self.error = f"Room discovery unavailable ({e.strerror}); join by IP"
            self.running = False

    def _loop(self):
        while self.running:
            try:
                data, (ip, _) = self.sock.recvfrom(1024)
                info = json.loads(data)
            except (OSError, ValueError):
                continue
            if info.get("tag") != TAG:
                continue
            info["ip"] = ip
            with self.lock:
                self.rooms[(ip, info.get("port"))] = (info, time.monotonic())

    def list_rooms(self):
        now = time.monotonic()
        with self.lock:
            # The same room may be heard via broadcast and loopback; keep one.
            live = {}
            for (ip, port), (info, seen) in self.rooms.items():
                if now - seen < STALE_AFTER:
                    key = (info["room"], port)
                    if key not in live or ip != "127.0.0.1":
                        live[key] = info
            return sorted(live.values(), key=lambda r: r["room"])

    def stop(self):
        self.running = False
        try:
            self.sock.close()
        except OSError:
            pass

"""Conquistador: entry point, main loop and scene switching."""
import socket
import time

import pygame

from net import protocol
from net.client import GameClient
from net.discovery import RoomAnnouncer, RoomBrowser
from net.server import GameServer
from ui import scenes
from ui.widgets import HEIGHT, WIDTH


def guess_local_ip():
    """The LAN address others should use. Connecting a UDP socket sends nothing."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


class App:
    def __init__(self, screen):
        self.screen = screen
        self.name = None
        self.local_ip = guess_local_ip()
        self.browser = None
        self.server = None
        self.announcer = None
        self.client = None
        self.error = None
        self._reset_session()
        self.scene_key = None
        self.scene = None
        self.popup = scenes.ResultPopup(self)

    def _reset_session(self):
        self.you = None
        self.lobby = None
        self.state = None
        self.state_at = 0.0
        self.answered_q = None
        self.answered_choice = None

    # ---- actions used by scenes ----------------------------------------

    def set_name(self, name):
        self.name = name
        self.browser = RoomBrowser()
        self.error = self.browser.error

    def create_room(self, with_bot=False):
        server = GameServer(f"{self.name}'s room")
        try:
            server.start()
        except OSError:
            self.error = f"Can't host: port {protocol.GAME_PORT} is already in use"
            return
        self.server = server
        self.announcer = RoomAnnouncer(server)
        self.join("127.0.0.1", server.port)
        if with_bot:
            self.send({"t": "add_bot"})   # server handles it right after our hello

    def join(self, ip, port):
        self.error = None
        try:
            self.client = GameClient(ip, port, self.name)
        except OSError:
            self.error = f"Could not connect to {ip}"
            self._stop_hosting()

    def leave(self):
        if self.client:
            self.client.close()
        self.client = None
        self._stop_hosting()
        self._reset_session()

    def send(self, msg):
        if self.client:
            self.client.send(msg)

    def question_token(self):
        """Identifies the question on screen, so each one is answered once."""
        st = self.state
        number = st["duel"]["question_no"] if st.get("duel") else st.get("question_no")
        return (st["stage"], number)

    def answer(self, choice):
        self.answered_q = self.question_token()
        self.answered_choice = choice
        self.send({"t": "answer", "choice": choice, "q": self.answered_q[1]})

    def remaining(self):
        if not self.state:
            return 0.0
        return max(0.0, self.state["remaining"] - (time.monotonic() - self.state_at))

    def player_name(self, pid):
        for p in (self.lobby or {}).get("players", []):
            if p["id"] == pid:
                return p["name"]
        return f"Player {pid + 1}"

    # ---- networking ----------------------------------------------------

    def _stop_hosting(self):
        if self.announcer:
            self.announcer.stop()
        if self.server:
            self.server.stop()
        self.announcer = self.server = None

    def poll_network(self):
        if not self.client:
            return
        for msg in self.client.messages():
            kind = msg.get("t")
            if kind == "welcome":
                self.you = msg["you"]
            elif kind == "lobby":
                self.lobby = msg
            elif kind == "state":
                self.state = msg
                self.state_at = time.monotonic()
            elif kind == "error":
                self.error = msg["msg"]
            elif kind == "disconnected":
                error = self.error or "Disconnected from the room"
                self.leave()
                self.error = error
                return

    # ---- scenes --------------------------------------------------------

    def current_key(self):
        if not self.name:
            return "name"
        if not self.client:
            return "lobby"
        if not self.state:
            return "room"
        return self.state["phase"]

    def update_scene(self):
        key = self.current_key()
        if key != self.scene_key:
            self.scene_key = key
            self.scene = {
                "name": scenes.NameEntry, "lobby": scenes.Lobby, "room": scenes.Room,
                "pick": scenes.MapPick, "duel": scenes.Duel, "done": scenes.Done,
                "grab_select": scenes.GrabSelect, "grab_question": scenes.GrabQuestion,
                "war_select": scenes.WarSelect, "war_duel": scenes.WarDuel,
                "over": scenes.GameOver,
            }[key](self)

    def run(self):
        clock = pygame.time.Clock()
        running = True
        while running:
            self.poll_network()
            self.update_scene()
            self.popup.update()
            compact = isinstance(self.scene, scenes.QuestionScene)
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (
                        event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                    running = False
                elif not self.popup.handle(event, compact):
                    self.scene.handle(event)
            self.update_scene()
            self.scene.draw(self.screen)
            self.popup.draw(self.screen, isinstance(self.scene, scenes.QuestionScene))
            pygame.display.flip()
            clock.tick(60)
        self.leave()
        if self.browser:
            self.browser.stop()


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Conquistador")
    App(screen).run()
    pygame.quit()


if __name__ == "__main__":
    main()

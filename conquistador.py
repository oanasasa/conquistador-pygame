"""Conquistador: entry point, main loop and scene switching."""
import socket
import time

import pygame

from net import opentdb, protocol
from net.client import GameClient
from net.discovery import RoomAnnouncer, RoomBrowser
from net.server import GameServer
from ui import scenes
from ui.sound import Sounds
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
        self.settings_for = None     # {"with_bot": bool} while the campaign popup is open
        self.campaign = {"category": opentdb.ALL, "difficulty": "any"}
        self._reset_session()
        self.scene_key = None
        self.scene = None
        self.popup = scenes.ResultPopup(self)
        self.sound = Sounds()

    def _reset_session(self):
        self.you = None
        self.lobby = None
        self.state = None
        self.state_at = 0.0
        self.answered_q = None
        self.answered_choice = None
        self.heard_result = None

    # ---- actions used by scenes ----------------------------------------

    def set_name(self, name):
        self.name = name
        self.browser = RoomBrowser()
        self.error = self.browser.error

    def open_settings(self, with_bot=False):
        """Ask for the question category and difficulty before creating a room."""
        self.error = None
        self.settings_for = {"with_bot": with_bot}

    def close_settings(self):
        self.settings_for = None

    def create_room(self, with_bot=False, category=None, difficulty="any"):
        self.settings_for = None
        server = GameServer(f"{self.name}'s hall", category=category, difficulty=difficulty)
        try:
            server.start()
        except OSError:
            self.error = f"Thou canst not raise a hall: port {protocol.GAME_PORT} is already taken"
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
            self.error = f"No hall answered at {ip}"
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
                self.hear_result(msg.get("stage"), msg.get("last_result"))
            elif kind == "judged":
                self.sound.play("win" if msg.get("correct") else "lose")
            elif kind == "error":
                self.error = msg["msg"]
            elif kind == "disconnected":
                error = self.error or "Thou wast parted from the hall"
                self.leave()
                self.error = error
                return

    def hear_result(self, stage, res):
        """The cannon roars once for every castle tower toppled."""
        if not res or (stage, res.get("no")) == self.heard_result:
            return
        self.heard_result = (stage, res.get("no"))
        if res.get("kind") == "attack" and res.get("base") and res.get("attacker_won"):
            self.sound.play("cannon")

    # ---- scenes --------------------------------------------------------

    def current_key(self):
        if not self.name:
            return "name"
        if not self.client:
            return "settings" if self.settings_for is not None else "lobby"
        if not self.state:
            return "room"
        return self.state["phase"]

    MENU_SCENES = ("name", "lobby", "settings", "room")

    def update_scene(self):
        key = self.current_key()
        if key != self.scene_key:
            self.scene_key = key
            self.scene = {
                "name": scenes.NameEntry, "lobby": scenes.Lobby, "room": scenes.Room,
                "settings": scenes.CampaignSettings,
                "pick": scenes.MapPick, "duel": scenes.Duel, "done": scenes.Done,
                "grab_select": scenes.GrabSelect, "grab_question": scenes.GrabQuestion,
                "war_select": scenes.WarSelect, "war_duel": scenes.WarDuel,
                "over": scenes.GameOver, "interlude": scenes.Interlude,
            }[key](self)

    def run(self):
        clock = pygame.time.Clock()
        running = True
        while running:
            self.poll_network()
            self.update_scene()
            self.popup.update()
            self.sound.lobby_music(self.scene_key in self.MENU_SCENES)
            if not isinstance(self.scene, scenes.QuestionScene):
                self.sound.riddle_clock(False)
            self.sound.update()
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (
                        event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                    running = False
                elif (event.type == pygame.KEYDOWN and event.key == pygame.K_m
                      and not self.scene.typing()):
                    self.sound.toggle_mute()
                else:
                    self.scene.handle(event)
            self.update_scene()
            self.scene.draw(self.screen)
            self.popup.draw(self.screen, isinstance(self.scene, scenes.QuestionScene))
            if self.scene_key in self.MENU_SCENES:
                scenes.draw_mute_hint(self.screen, self.sound.muted)
            pygame.display.flip()
            clock.tick(60)
        self.leave()
        if self.browser:
            self.browser.stop()


def main():
    pygame.mixer.pre_init(44100, -16, 2, 512)    # CD quality for the audio files
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Conquistador")
    App(screen).run()
    pygame.quit()


if __name__ == "__main__":
    main()

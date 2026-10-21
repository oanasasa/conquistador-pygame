"""Music and sound effects, played from files in assets/audio/.

Expected files (any of .ogg, .wav, .mp3; each one is optional):

    lobby        music, looped while players are in the menus and halls
    tick         each second of a riddle
    tick_urgent  each of a riddle's last three seconds (falls back to tick)
    bell         when a riddle ends
    horn         when it is the player's turn to choose land

A missing file just means that sound stays silent, and so does everything if
the computer has no audio device.
"""
from pathlib import Path

import pygame

AUDIO_DIR = Path(__file__).resolve().parent.parent / "assets" / "audio"
EXTENSIONS = ("ogg", "wav", "mp3")
EFFECTS = ("tick", "tick_urgent", "bell", "horn")
MUSIC_VOLUME = 0.45
EFFECT_VOLUME = 0.7


def find(name, folder=AUDIO_DIR):
    """The first assets/audio/<name>.<ext> that exists, or None."""
    for ext in EXTENSIONS:
        path = folder / f"{name}.{ext}"
        if path.exists():
            return path
    return None


class Sounds:
    """Plays the lobby music and effects; silent where a file is missing."""

    def __init__(self, folder=AUDIO_DIR):
        self.effects = {}
        self.music_file = None
        self.want_music = False
        self.playing = False
        self.muted = False
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            self.enabled = True
        except pygame.error:
            self.enabled = False
            return
        self.music_file = find("lobby", folder)
        for name in EFFECTS:
            path = find(name, folder)
            if path is None:
                continue
            try:
                snd = pygame.mixer.Sound(str(path))
            except pygame.error:
                continue                          # unreadable file: stay silent
            snd.set_volume(EFFECT_VOLUME)
            self.effects[name] = snd
        if "tick_urgent" not in self.effects and "tick" in self.effects:
            self.effects["tick_urgent"] = self.effects["tick"]

    def play(self, name):
        if self.enabled and not self.muted and name in self.effects:
            self.effects[name].play()

    def lobby_music(self, on):
        """Keep the lobby music playing while `on`; fade it out otherwise."""
        self.want_music = on
        if not self.enabled or not self.music_file:
            return
        if on and not self.playing and not self.muted:
            try:
                pygame.mixer.music.load(str(self.music_file))
            except pygame.error:
                self.music_file = None            # unreadable file: stay silent
                return
            pygame.mixer.music.set_volume(MUSIC_VOLUME)
            pygame.mixer.music.play(-1, fade_ms=1500)
            self.playing = True
        elif not on and self.playing:
            pygame.mixer.music.fadeout(1000)
            self.playing = False

    def toggle_mute(self):
        self.muted = not self.muted
        if self.muted and self.playing:
            pygame.mixer.music.fadeout(400)
            self.playing = False
        elif not self.muted:
            self.lobby_music(self.want_music)

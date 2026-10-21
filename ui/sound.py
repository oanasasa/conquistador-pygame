"""Music and sound effects, played from files in assets/audio/.

Which file plays for what is set in SOUND_FILES below. Each sound is
optional: a missing or unreadable file just means silence, and so does
everything if the computer has no audio device.
"""
from pathlib import Path

import pygame

AUDIO_DIR = Path(__file__).resolve().parent.parent / "assets" / "audio"

# sound -> file in assets/audio/
SOUND_FILES = {
    "theme": "Woodland Fantasy.mp3",   # loops in the menus and halls
    "clock": "Clock Ticking.ogg",      # loops while a riddle is open
    "win": "win sound 1.wav",          # thine answer was true
    "lose": "Bad Sound 1.wav",         # thine answer was false
    "cannon": "Cannon Hit.ogg",        # a castle tower is toppled
}
EFFECTS = ("win", "lose", "cannon")

THEME_VOLUME = 0.45
CLOCK_VOLUME = 0.35
CLOCK_URGENT_VOLUME = 0.9          # the last three seconds of a riddle
EFFECT_VOLUME = 0.75
WIN_SECONDS = 2.5                  # the win fanfare fades out after this


class Sounds:
    """Plays the theme, the riddle clock and the effects."""

    def __init__(self, folder=AUDIO_DIR, files=SOUND_FILES):
        self.effects = {}
        self.theme_file = None
        self.clock = None
        self.clock_channel = None
        self.win_channel = None
        self.win_fade_at = 0
        self.want_theme = False
        self.playing = False
        self.muted = False
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            self.enabled = True
        except pygame.error:
            self.enabled = False
            return
        path = folder / files.get("theme", "")
        self.theme_file = path if files.get("theme") and path.exists() else None
        self.clock = self._load(folder, files.get("clock"))
        for name in EFFECTS:
            snd = self._load(folder, files.get(name))
            if snd is not None:
                snd.set_volume(EFFECT_VOLUME)
                self.effects[name] = snd

    @staticmethod
    def _load(folder, filename):
        if not filename or not (folder / filename).exists():
            return None
        try:
            return pygame.mixer.Sound(str(folder / filename))
        except pygame.error:
            return None                       # unreadable file: stay silent

    # ---- effects --------------------------------------------------------------

    def play(self, name):
        if not self.enabled or self.muted or name not in self.effects:
            return
        channel = self.effects[name].play()
        if name == "win":                         # long fanfare: fade it in update()
            self.win_channel = channel
            self.win_fade_at = pygame.time.get_ticks() + int(WIN_SECONDS * 1000)

    def update(self):
        """Call once per frame: fades the win fanfare after WIN_SECONDS."""
        if self.win_channel is not None and pygame.time.get_ticks() >= self.win_fade_at:
            self.win_channel.fadeout(600)
            self.win_channel = None

    # ---- the riddle clock -----------------------------------------------------

    def riddle_clock(self, on, urgent=False):
        """Tick while a riddle is open (louder when `urgent`), silent otherwise."""
        if not self.enabled or self.clock is None:
            return
        if on and not self.muted:
            if self.clock_channel is None or not self.clock_channel.get_busy():
                self.clock_channel = self.clock.play(loops=-1)
            if self.clock_channel is not None:
                self.clock_channel.set_volume(CLOCK_URGENT_VOLUME if urgent else CLOCK_VOLUME)
        elif self.clock_channel is not None:
            self.clock_channel.stop()
            self.clock_channel = None

    # ---- the theme -------------------------------------------------------------

    def lobby_music(self, on):
        """Keep the theme playing while `on`; fade it out otherwise."""
        self.want_theme = on
        if not self.enabled or not self.theme_file:
            return
        if on and not self.playing and not self.muted:
            try:
                pygame.mixer.music.load(str(self.theme_file))
            except pygame.error:
                self.theme_file = None            # unreadable file: stay silent
                return
            pygame.mixer.music.set_volume(THEME_VOLUME)
            pygame.mixer.music.play(-1, fade_ms=1500)
            self.playing = True
        elif not on and self.playing:
            pygame.mixer.music.fadeout(1000)
            self.playing = False

    def toggle_mute(self):
        self.muted = not self.muted
        if self.muted:
            if self.playing:
                pygame.mixer.music.fadeout(400)
                self.playing = False
            self.riddle_clock(False)
        else:
            self.lobby_music(self.want_theme)

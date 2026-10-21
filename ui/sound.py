"""Music and sound effects, synthesized in code (no audio files needed).

- Lobby music: "Greensleeves" (a 16th-century tune in the public domain),
  played on a plucked lute (Karplus-Strong synthesis) with a bass line,
  looping while players are in the menus and halls. Put your own track at
  assets/audio/lobby.ogg (or .mp3/.wav) to use it instead.
- Effects: a wood-block tick each second of a riddle (higher and louder in
  the last three), a bell when a riddle ends, and a horn when it is the
  player's turn to choose land.

Everything degrades to silence if the computer has no audio device.
"""
import math
import random
import threading
from array import array
from pathlib import Path

import pygame

AUDIO_DIR = Path(__file__).resolve().parent.parent / "assets" / "audio"
MUSIC_VOLUME = 0.45
EFFECT_VOLUME = 0.7

# ---- the tune -------------------------------------------------------------------
# (note, beats) in 3/4; "-" is a rest. Quarter note = BEAT seconds.
BEAT = 0.42
VERSE = [("A4", 1),
         ("C5", 2), ("D5", 1), ("E5", 1.5), ("F5", .5), ("E5", 1), ("D5", 2), ("B4", 1),
         ("G4", 1.5), ("A4", .5), ("B4", 1), ("C5", 2), ("A4", 1), ("A4", 1.5), ("G#4", .5),
         ("A4", 1), ("B4", 2), ("G#4", 1), ("E4", 2), ("A4", 1),
         ("C5", 2), ("D5", 1), ("E5", 1.5), ("F5", .5), ("E5", 1), ("D5", 2), ("B4", 1),
         ("G4", 1.5), ("A4", .5), ("B4", 1), ("C5", 1.5), ("B4", .5), ("A4", 1),
         ("G#4", 1.5), ("F#4", .5), ("G#4", 1), ("A4", 3), ("-", 3)]
REFRAIN = [("G5", 3), ("G5", 1.5), ("F#5", .5), ("E5", 1), ("D5", 2), ("B4", 1),
           ("G4", 1.5), ("A4", .5), ("B4", 1), ("C5", 2), ("A4", 1), ("A4", 1.5), ("G#4", .5),
           ("A4", 1), ("B4", 2), ("G#4", 1), ("E4", 3),
           ("G5", 3), ("G5", 1.5), ("F#5", .5), ("E5", 1), ("D5", 2), ("B4", 1),
           ("G4", 1.5), ("A4", .5), ("B4", 1), ("C5", 1.5), ("B4", .5), ("A4", 1),
           ("G#4", 1.5), ("F#4", .5), ("G#4", 1), ("A4", 3), ("-", 3)]
# One bass root per bar (3 beats), starting after the one-beat pickup.
BASS = ["A2", "A2", "G2", "E2", "A2", "A2", "E2", "E2",
        "A2", "A2", "G2", "E2", "A2", "E2", "A2", "A2",
        "C3", "C3", "G2", "E2", "A2", "A2", "E2", "E2",
        "C3", "C3", "G2", "E2", "A2", "E2", "A2", "A2"]

_NOTE = {"C": -9, "D": -7, "E": -5, "F": -4, "G": -2, "A": 0, "B": 2}


def note_freq(name):
    """'G#4' -> frequency in Hz (A4 = 440)."""
    letter, rest = name[0], name[1:]
    shift = 0
    while rest and rest[0] in "#b":
        shift += 1 if rest[0] == "#" else -1
        rest = rest[1:]
    semis = _NOTE[letter] + shift + 12 * (int(rest) - 4)
    return 440.0 * 2 ** (semis / 12)


# ---- synthesis -------------------------------------------------------------------

def pluck(freq, seconds, rate, rng, decay=0.996, brightness=0.5):
    """A plucked string (Karplus-Strong): a noise burst through a decaying loop."""
    n = max(2, int(rate / freq))
    buf = [rng.uniform(-1, 1) for _ in range(n)]
    out = []
    keep = brightness
    for i in range(int(seconds * rate)):
        j = i % n
        k = (j + 1) % n
        v = buf[j]
        out.append(v)
        buf[j] = decay * (keep * v + (1 - keep) * buf[k])
    return out


def render_tune(rate, rng):
    melody = VERSE + REFRAIN
    total = sum(b for _, b in melody) * BEAT + 2.0
    mix = [0.0] * int(total * rate)
    cache = {}

    def add(name, start, seconds, gain, decay, brightness=0.5):
        key = (name, round(seconds, 2), decay)
        if key not in cache:
            cache[key] = pluck(note_freq(name), seconds, rate, rng, decay, brightness)
        i0 = int(start * rate)
        for i, v in enumerate(cache[key]):
            if i0 + i < len(mix):
                mix[i0 + i] += gain * v

    t = 0.0
    for name, beats in melody:
        if name != "-":
            add(name, t, min(2.4, beats * BEAT * 1.8), 0.55, 0.996)
        t += beats * BEAT
    bar = 3 * BEAT
    for i, name in enumerate(BASS):
        start = BEAT + i * bar
        add(name, start, bar * 1.1, 0.32, 0.998, 0.6)
        add(name[:-1] + str(int(name[-1]) + 1), start + 2 * BEAT, BEAT * 1.2, 0.14, 0.996)
    loop_len = int((sum(b for _, b in melody) * BEAT) * rate)
    return mix[:loop_len]


def tick(rate, urgent):
    """A wood-block knock; higher and louder when time is short."""
    freq, gain = (1900, 0.9) if urgent else (1300, 0.55)
    rng = random.Random(5)
    out = []
    for i in range(int(0.06 * rate)):
        t = i / rate
        tone = math.sin(2 * math.pi * freq * t) * math.exp(-t * 70)
        knock = rng.uniform(-1, 1) * math.exp(-t * 400) * 0.4
        out.append(gain * (tone + knock))
    return out


def bell(rate):
    """A small bell: inharmonic partials with a long decay."""
    out = []
    partials = [(1.0, 1.0), (2.76, 0.5), (5.4, 0.25), (8.93, 0.12)]
    for i in range(int(1.6 * rate)):
        t = i / rate
        v = sum(a * math.sin(2 * math.pi * 880 * r * t) * math.exp(-t * (2.2 + r)) for r, a in partials)
        out.append(0.35 * v)
    return out


def horn(rate):
    """A two-note hunting horn call."""
    out = []
    for freq, length in ((293.66, 0.22), (440.0, 0.42)):
        n = int(length * rate)
        for i in range(n):
            t = i / rate
            env = min(1.0, t / 0.03) * min(1.0, (length - t) / 0.08)
            vib = 1 + 0.004 * math.sin(2 * math.pi * 5 * t)
            v = sum(math.sin(2 * math.pi * freq * k * vib * t) / k for k in range(1, 7))
            out.append(0.32 * env * v)
    return out


def to_sound(samples, rate, channels, volume):
    peak = max(1e-6, max(abs(v) for v in samples))
    scale = 32000 / max(1.0, peak)
    data = array("h", (int(v * scale) for v in samples))
    if channels == 2:
        stereo = array("h", bytes(len(data) * 4))
        stereo[0::2] = data
        stereo[1::2] = data
        data = stereo
    snd = pygame.mixer.Sound(buffer=data.tobytes())
    snd.set_volume(volume)
    return snd


# ---- the player ------------------------------------------------------------------

class Sounds:
    """Plays the lobby music and effects; silent if there's no audio device."""

    def __init__(self):
        self.effects = {}
        self.tune = None
        self.music_file = next((p for p in (AUDIO_DIR / f"lobby.{ext}" for ext in ("ogg", "mp3", "wav"))
                                if p.exists()), None)
        self.want_music = False
        self.playing = False
        self.muted = False
        self.channel = None
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            self.rate, _, self.channels = pygame.mixer.get_init()
            self.enabled = True
        except pygame.error:
            self.enabled = False
            return
        threading.Thread(target=self._build, daemon=True).start()

    def _build(self):
        rate, ch = self.rate, self.channels
        self.effects = {"tick": to_sound(tick(rate, False), rate, ch, EFFECT_VOLUME * 0.6),
                        "tick_urgent": to_sound(tick(rate, True), rate, ch, EFFECT_VOLUME),
                        "bell": to_sound(bell(rate), rate, ch, EFFECT_VOLUME * 0.8),
                        "horn": to_sound(horn(rate), rate, ch, EFFECT_VOLUME * 0.7)}
        if not self.music_file:
            self.tune = to_sound(render_tune(rate, random.Random(1)), rate, ch, MUSIC_VOLUME)

    def play(self, name):
        if self.enabled and not self.muted and name in self.effects:
            self.effects[name].play()

    def lobby_music(self, on):
        """Keep the lobby music playing while `on`; fade it out otherwise."""
        self.want_music = on
        if not self.enabled:
            return
        if on and not self.playing and not self.muted:
            if self.music_file:
                pygame.mixer.music.load(str(self.music_file))
                pygame.mixer.music.set_volume(MUSIC_VOLUME)
                pygame.mixer.music.play(-1, fade_ms=1500)
                self.playing = True
            elif self.tune is not None:
                self.channel = self.tune.play(loops=-1, fade_ms=1500)
                self.playing = True
        elif not on and self.playing:
            self._stop_music()

    def _stop_music(self):
        if self.music_file:
            pygame.mixer.music.fadeout(1000)
        elif self.channel is not None:
            self.channel.fadeout(1000)
        self.playing = False

    def toggle_mute(self):
        self.muted = not self.muted
        if self.muted and self.playing:
            self._stop_music()
        elif not self.muted:
            self.lobby_music(self.want_music)

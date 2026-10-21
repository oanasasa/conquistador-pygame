import os
import random

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from ui import sound  # noqa: E402


def test_note_frequencies():
    assert sound.note_freq("A4") == 440.0
    assert round(sound.note_freq("A5")) == 880
    assert round(sound.note_freq("G#4"), 1) == 415.3
    assert round(sound.note_freq("C3"), 1) == 130.8


def test_tune_bars_line_up_with_the_bass():
    beats = sum(b for _, b in sound.VERSE + sound.REFRAIN)
    assert beats == 1 + 3 * len(sound.BASS)              # pickup + one bass note per bar


def test_synthesized_sounds_are_audible_and_short():
    rate = 22050
    for samples, longest in ((sound.tick(rate, False), 0.1), (sound.tick(rate, True), 0.1),
                             (sound.bell(rate), 2), (sound.horn(rate), 1)):
        assert 0 < len(samples) <= longest * rate
        assert max(abs(v) for v in samples) > 0.1
    tune = sound.render_tune(rate, random.Random(1))
    assert 30 * rate < len(tune) < 60 * rate


def test_sounds_play_and_mute_without_errors():
    pygame.mixer.init(22050, -16, 1)
    s = sound.Sounds()
    s._build()                                           # build now instead of in the background
    s.lobby_music(True)
    assert s.playing
    s.play("tick")
    s.toggle_mute()
    assert s.muted and not s.playing
    s.toggle_mute()
    assert s.playing
    s.lobby_music(False)
    assert not s.playing

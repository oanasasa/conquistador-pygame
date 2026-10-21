"""Sound playback from files. Tests write tiny silent WAVs to a temp folder;
the real sounds live in assets/audio/."""
import os
import wave

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from ui import sound  # noqa: E402

FILES = {"theme": "theme.wav", "clock": "clock.wav", "win": "win.wav", "lose": "lose.wav",
         "cannon": "cannon.wav"}


def silent_wav(path, seconds=0.05):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\0\0\0\0" * int(44100 * seconds))


def make(tmp_path, names=FILES, seconds=0.5):
    pygame.mixer.init(44100, -16, 2)
    for name in names:
        silent_wav(tmp_path / FILES[name], seconds)
    return sound.Sounds(folder=tmp_path, files=FILES)


def test_the_real_sound_files_are_all_there_and_load():
    pygame.mixer.init(44100, -16, 2)
    s = sound.Sounds()
    assert s.theme_file is not None and s.clock is not None
    assert set(s.effects) == set(sound.EFFECTS)


def test_missing_files_mean_silence_not_errors(tmp_path):
    s = make(tmp_path, names=())
    assert s.effects == {} and s.theme_file is None and s.clock is None
    s.play("win")
    s.riddle_clock(True)
    s.lobby_music(True)
    assert not s.playing


def test_unreadable_file_is_skipped(tmp_path):
    pygame.mixer.init(44100, -16, 2)
    (tmp_path / "cannon.wav").write_bytes(b"not a sound")
    s = sound.Sounds(folder=tmp_path, files=FILES)
    assert "cannon" not in s.effects


def test_theme_plays_mutes_and_stops(tmp_path):
    s = make(tmp_path, seconds=1)
    s.lobby_music(True)
    assert s.playing
    s.toggle_mute()
    assert s.muted and not s.playing
    s.toggle_mute()
    assert s.playing
    s.lobby_music(False)
    assert not s.playing


def test_clock_loops_while_a_riddle_is_open_and_stops_after(tmp_path):
    s = make(tmp_path, seconds=1)
    s.riddle_clock(True)
    assert s.clock_channel is not None
    assert abs(s.clock_channel.get_volume() - sound.CLOCK_VOLUME) < 0.01
    s.riddle_clock(True, urgent=True)
    assert abs(s.clock_channel.get_volume() - sound.CLOCK_URGENT_VOLUME) < 0.01
    s.riddle_clock(False)
    assert s.clock_channel is None


def test_muting_silences_the_clock_and_effects(tmp_path):
    s = make(tmp_path, seconds=1)
    s.riddle_clock(True)
    s.toggle_mute()
    assert s.clock_channel is None
    s.riddle_clock(True)
    assert s.clock_channel is None

"""Sound playback from files. Tests write tiny silent WAVs to a temp folder;
the real sounds live in assets/audio/."""
import os
import wave

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from ui import sound  # noqa: E402


def silent_wav(path, seconds=0.05):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(22050)
        w.writeframes(b"\0\0" * int(22050 * seconds))


def test_missing_files_mean_silence_not_errors(tmp_path):
    pygame.mixer.init(22050, -16, 1)
    s = sound.Sounds(folder=tmp_path)
    assert s.effects == {} and s.music_file is None
    s.play("tick")
    s.lobby_music(True)
    assert not s.playing


def test_files_are_found_and_urgent_tick_falls_back(tmp_path):
    pygame.mixer.init(22050, -16, 1)
    for name in ("lobby", "tick", "bell"):
        silent_wav(tmp_path / f"{name}.wav")
    s = sound.Sounds(folder=tmp_path)
    assert s.music_file == tmp_path / "lobby.wav"
    assert set(s.effects) == {"tick", "tick_urgent", "bell"}
    assert s.effects["tick_urgent"] is s.effects["tick"]


def test_music_plays_mutes_and_stops(tmp_path):
    pygame.mixer.init(22050, -16, 1)
    silent_wav(tmp_path / "lobby.wav", seconds=1)
    s = sound.Sounds(folder=tmp_path)
    s.lobby_music(True)
    assert s.playing
    s.toggle_mute()
    assert s.muted and not s.playing
    s.toggle_mute()
    assert s.playing
    s.lobby_music(False)
    assert not s.playing


def test_unreadable_file_is_skipped(tmp_path):
    pygame.mixer.init(22050, -16, 1)
    (tmp_path / "bell.wav").write_bytes(b"not a sound")
    s = sound.Sounds(folder=tmp_path)
    assert "bell" not in s.effects

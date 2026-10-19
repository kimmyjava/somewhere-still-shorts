"""Fast music tests: pick_track determinism/fallback and mix_command shape (no real ffmpeg)."""
from pathlib import Path

from shorts.music import MUSIC_LUFS, mix_command, pick_track


def make_music_dir(tmp_path, *names):
    d = tmp_path / "music"
    d.mkdir(exist_ok=True)
    for n in names:
        (d / n).write_bytes(b"")
    return d


def test_music_lufs_value():
    assert MUSIC_LUFS == -30


def test_same_slug_picks_same_track(tmp_path):
    d = make_music_dir(tmp_path, "calm-01.mp3", "calm-02.mp3", "calm-03.mp3")
    first = pick_track(d, "calm", "kitchen-table")
    second = pick_track(d, "calm", "kitchen-table")
    assert first == second
    assert first is not None and first.name.startswith("calm-")
    assert pick_track(d, "calm", "kitchen-table") == first


def test_mood_falls_back_to_calm(tmp_path):
    d = make_music_dir(tmp_path, "calm-01.mp3")
    track = pick_track(d, "cozy", "kitchen-table")
    assert track is not None
    assert track.name == "calm-01.mp3"


def test_empty_folder_returns_none(tmp_path):
    d = make_music_dir(tmp_path)
    assert pick_track(d, "calm", "kitchen-table") is None


def test_missing_folder_returns_none(tmp_path):
    assert pick_track(tmp_path / "nope", "calm", "kitchen-table") is None


def test_all_supported_extensions_considered(tmp_path):
    d = make_music_dir(tmp_path, "calm-2.wav", "calm-10.m4a", "calm-1.mp3", "other-1.mp3")
    track = pick_track(d, "calm", "x")
    assert track is not None
    assert track.name in {"calm-1.mp3", "calm-2.wav", "calm-10.m4a"}


def test_mix_command_contents():
    cmd = mix_command(Path("in.mp4"), Path("calm-01.mp3"), Path("out.mp4"), 15.9)
    s = " ".join(cmd)
    assert cmd[0] == "ffmpeg"
    assert cmd[-1] == "out.mp4"
    assert "-stream_loop" in cmd and "-1" in cmd
    assert "atrim=0:15.9" in s
    assert "loudnorm=I=-30:TP=-6:LRA=11" in s
    assert "afade=t=in:d=1.5" in s
    assert "afade=t=out:st=13.4:d=2.5" in s
    assert "sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400" in s
    assert "amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[a]" in s
    assert "-map 0:v -map [a]" in s
    assert "-c:v copy" in s
    assert "-c:a aac -b:a 192k -ar 48000 -shortest" in s

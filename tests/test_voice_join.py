"""Fast tests for joining per-scene voice parts (stdlib wave only, no TTS, no Voicebox)."""
import wave

import pytest

from shorts.tts.join import JoinError, join_parts

RATE = 8000


def write_wav(path, frames, rate=RATE, width=2, channels=1):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(width)
        w.setframerate(rate)
        w.writeframes(frames)


def read_wav(path):
    with wave.open(str(path), "rb") as w:
        return w.getframerate(), w.getsampwidth(), w.getnchannels(), w.readframes(w.getnframes())


def test_parts_joined_in_order_with_pause_between(tmp_path):
    p1 = tmp_path / "s01-places.wav"
    p2 = tmp_path / "s02-memories.wav"
    p3 = tmp_path / "s03-back.wav"
    write_wav(p1, b"\x01\x02" * 100)
    write_wav(p2, b"\x03\x04" * 50)
    write_wav(p3, b"\x05\x06" * 25)
    out = tmp_path / "vo.wav"

    seconds = join_parts([p1, p2, p3], out)

    rate, width, channels, frames = read_wav(out)
    silence = b"\x00" * (int(round(RATE * 0.35)) * 2)
    assert (rate, width, channels) == (RATE, 2, 1)
    assert frames == b"\x01\x02" * 100 + silence + b"\x03\x04" * 50 + silence + b"\x05\x06" * 25
    assert not out.with_suffix(out.suffix + ".part").exists()
    expected_frames = 175 + int(round(RATE * 0.35)) * 2
    assert seconds == pytest.approx(expected_frames / RATE)


def test_single_part_gets_no_pause(tmp_path):
    p1 = tmp_path / "s01.wav"
    write_wav(p1, b"\x01\x02" * 100)
    out = tmp_path / "vo.wav"

    seconds = join_parts([p1], out)

    _rate, _width, _channels, frames = read_wav(out)
    assert frames == b"\x01\x02" * 100
    assert seconds == pytest.approx(100 / RATE)


def test_custom_pause_length(tmp_path):
    p1 = tmp_path / "a.wav"
    p2 = tmp_path / "b.wav"
    write_wav(p1, b"\x01" * 100)
    write_wav(p2, b"\x02" * 100)
    out = tmp_path / "vo.wav"

    join_parts([p1, p2], out, pause_s=0.5)

    _rate, _width, _channels, frames = read_wav(out)
    assert frames == b"\x01" * 100 + b"\x00" * (int(round(RATE * 0.5)) * 2) + b"\x02" * 100


def test_sample_rate_mismatch_raises(tmp_path):
    a = tmp_path / "a.wav"
    b = tmp_path / "b.wav"
    write_wav(a, b"\x00" * 100, rate=24000)
    write_wav(b, b"\x00" * 100, rate=48000)

    with pytest.raises(JoinError, match=r"48000 Hz.*24000 Hz"):
        join_parts([a, b], tmp_path / "vo.wav")


def test_width_and_channel_mismatches_raise(tmp_path):
    a = tmp_path / "a.wav"
    b = tmp_path / "b.wav"
    write_wav(a, b"\x00\x00" * 50)
    write_wav(b, b"\x00\x00\x00\x00" * 50, width=4)

    with pytest.raises(JoinError, match="4 bytes/sample"):
        join_parts([a, b], tmp_path / "vo.wav")

    write_wav(b, b"\x00\x00\x00\x00" * 50, channels=2)

    with pytest.raises(JoinError, match="2 channel"):
        join_parts([a, b], tmp_path / "vo.wav")


def test_no_parts_raises(tmp_path):
    with pytest.raises(JoinError, match="no voice parts"):
        join_parts([], tmp_path / "vo.wav")

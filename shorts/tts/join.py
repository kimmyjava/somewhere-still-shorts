"""Join per-scene voice parts into one narration WAV with a small pause between scenes."""
import wave
from pathlib import Path
from typing import Sequence

PAUSE_S = 0.35


class JoinError(Exception):
    """The voice parts cannot be joined into one WAV."""


def join_parts(parts: Sequence[Path], out_wav: Path, pause_s: float = PAUSE_S) -> float:
    """Concatenate WAV parts, inserting pause_s of silence between them.

    All parts must share sample rate, sample width and channels; otherwise
    JoinError is raised. Returns the joined duration in seconds.
    """
    parts = [Path(p) for p in parts]
    if not parts:
        raise JoinError("no voice parts to join")
    out_wav = Path(out_wav)

    data: list[bytes] = []
    rate = sampwidth = channels = 0
    first = None
    for part in parts:
        with wave.open(str(part), "rb") as w:
            p_rate, p_width, p_channels = w.getframerate(), w.getsampwidth(), w.getnchannels()
            frames = w.readframes(w.getnframes())
        if first is None:
            first, rate, sampwidth, channels = part, p_rate, p_width, p_channels
        elif (p_rate, p_width, p_channels) != (rate, sampwidth, channels):
            raise JoinError(
                f"WAV formats do not match: {part.name} is {p_rate} Hz / {p_width} bytes/sample / "
                f"{p_channels} channel(s) but {first.name} is "
                f"{rate} Hz / {sampwidth} bytes/sample / {channels} channel(s)")
        data.append(frames)

    pause_frames = int(round(rate * pause_s))
    silence = b"\x00" * (pause_frames * channels * sampwidth)
    tmp = out_wav.with_suffix(out_wav.suffix + ".part")
    with wave.open(str(tmp), "wb") as out:
        out.setnchannels(channels)
        out.setsampwidth(sampwidth)
        out.setframerate(rate)
        for i, frames in enumerate(data):
            if i:
                out.writeframes(silence)
            out.writeframes(frames)
    tmp.replace(out_wav)
    total_frames = sum(len(frames) // (channels * sampwidth) for frames in data) \
        + pause_frames * (len(data) - 1)
    return total_frames / rate

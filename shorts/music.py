"""Background music: pick a mood track (stable per slug) and duck it under the voice with ffmpeg."""
import hashlib
from pathlib import Path

MUSIC_LUFS = -30
EXTENSIONS = (".mp3", ".m4a", ".wav")


def _by_mood(music_dir: Path, mood: str) -> list[Path]:
    files: list[Path] = []
    for ext in EXTENSIONS:
        files.extend(music_dir.glob(f"{mood}-*{ext}"))
    return sorted(files)


def pick_track(music_dir: Path, mood: str, slug: str) -> Path | None:
    music_dir = Path(music_dir)
    files = _by_mood(music_dir, mood)
    if not files and mood != "calm":
        files = _by_mood(music_dir, "calm")
    if not files:
        return None
    return files[int(hashlib.sha256(slug.encode()).hexdigest(), 16) % len(files)]


def mix_command(video: Path, track: Path, out: Path, duration: float) -> list[str]:
    d = round(float(duration), 3)
    fade_start = round(d - 2.5, 3)
    filter_complex = (
        f"[1:a]atrim=0:{d},asetpts=N/SR/TB,loudnorm=I={MUSIC_LUFS}:TP=-6:LRA=11,aresample=48000,"
        f"afade=t=in:d=1.5,afade=t=out:st={fade_start}:d=2.5[m];"
        "[0:a]aresample=48000,asplit[v][vk];"
        "[m][vk]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400[md];"
        "[v][md]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[a]"
    )
    return [
        "ffmpeg", "-y", "-i", str(video), "-stream_loop", "-1", "-i", str(track),
        "-filter_complex", filter_complex,
        "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-ar", "48000", "-shortest", str(out),
    ]

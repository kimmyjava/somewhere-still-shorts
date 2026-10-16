"""Word timing: Whisper's word times + the script text -> TimedWords with script spelling."""
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

TRANSCRIBE_SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "vendor" / "kape-explainer" / "skills" / "kape-explainer" / "scripts" / "transcribe.py"
)


class AlignmentError(Exception):
    """Too many script words could not be matched to Whisper words."""


@dataclass
class TimedWord:
    text: str
    start: float
    end: float


def load_whisper_words(path: Path) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [w for seg in data for w in seg["words"]]


def _norm(word: str) -> str:
    return re.sub(r"[^\w]", "", word.lower())


def align(script_text: str, whisper_words: list[dict]) -> list[TimedWord]:
    script_words = script_text.split()
    if not script_words:
        return []
    s_norm = [_norm(w) for w in script_words]
    w_norm = [_norm(w["w"]) for w in whisper_words]
    times: list[tuple[float, float] | None] = [None] * len(script_words)
    sm = SequenceMatcher(None, s_norm, w_norm, autojunk=False)
    for blk in sm.get_matching_blocks():
        for k in range(blk.size):
            times[blk.a + k] = (float(whisper_words[blk.b + k]["s"]), float(whisper_words[blk.b + k]["e"]))

    missing = sum(1 for t in times if t is None)
    if missing * 10 > len(script_words):
        raise AlignmentError(f"{missing} of {len(script_words)} script words unmatched (more than 10%)")

    first_start = float(whisper_words[0]["s"]) if whisper_words else 0.0
    last_end = float(whisper_words[-1]["e"]) if whisper_words else 0.0
    out: list[TimedWord] = []
    prev_end = first_start
    i = 0
    while i < len(script_words):
        if times[i] is not None:
            start, end = times[i]
            out.append(TimedWord(script_words[i], start, end))
            prev_end = end
            i += 1
            continue
        j = i
        while j < len(script_words) and times[j] is None:
            j += 1
        next_start = times[j][0] if j < len(script_words) else last_end
        step = (next_start - prev_end) / ((j - i) + 1)
        for k in range(i, j):
            out.append(TimedWord(script_words[k], prev_end + step * (k - i + 1), prev_end + step * (k - i + 2)))
        prev_end = next_start
        i = j
    return out


def transcribe(wav_path: Path, out_dir: Path, lang: str = "en", model: str = "medium") -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, str(TRANSCRIBE_SCRIPT), str(wav_path), str(out_dir), "--lang", lang, "--model", model]
    subprocess.run(cmd, check=True)
    return out_dir / "vo-words.json"

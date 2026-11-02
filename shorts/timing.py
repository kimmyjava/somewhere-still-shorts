"""Word timing: Whisper's word times + the script text -> TimedWords with script spelling."""
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import wave
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import TYPE_CHECKING, Sequence

from shorts.tts.join import PAUSE_S

if TYPE_CHECKING:
    from shorts.brief import Brief

TRANSCRIBE_SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "vendor" / "kape-explainer" / "skills" / "kape-explainer" / "scripts" / "transcribe.py"
)

HYPERFRAMES_SPEC = "hyperframes@0.8.117"
TRANSCRIBE_TIMEOUT_S = 1800

log = logging.getLogger(__name__)

UNMATCHED_FAIL_SHARE = 4  # fail when unmatched * 4 > total (more than 25%)
UNMATCHED_WARN_SHARE = 10  # warn when unmatched * 10 > total (more than 10%)

_ONES_LIST = ["", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
_TEENS_LIST = ["ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
               "sixteen", "seventeen", "eighteen", "nineteen"]
_TENS_LIST = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
_ONES = {w: i for i, w in enumerate(_ONES_LIST) if w}
_TEENS = {w: 10 + i for i, w in enumerate(_TEENS_LIST)}
_TENS = {w: i * 10 for i, w in enumerate(_TENS_LIST) if w}


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


_MAX_INT = 999_999_999_999
_SCALES = ((1_000_000_000, "billion"), (1_000_000, "million"), (1_000, "thousand"))
_SUFFIX_MULT = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}
_NUM_TOKEN_RE = re.compile(r"^\d{1,3}(,\d{3})*(\.\d+)?[kmb]?$")
_PLURAL_RE = re.compile(r"^(\d{4})s$")


def _hundreds_to_words(n: int) -> list[str]:
    """1..999 as words (empty for 0)."""
    out: list[str] = []
    if n >= 100:
        out += [_ONES_LIST[n // 100], "hundred"]
        n %= 100
    if n >= 20:
        out.append(_TENS_LIST[n // 10])
        if n % 10:
            out.append(_ONES_LIST[n % 10])
    elif n >= 10:
        out.append(_TEENS_LIST[n - 10])
    elif n > 0:
        out.append(_ONES_LIST[n])
    return out


def _int_to_words(n: int) -> list[str] | None:
    """Words for 0..999,999,999,999, or None when out of range."""
    if not 0 <= n <= _MAX_INT:
        return None
    if n == 0:
        return ["zero"]
    out: list[str] = []
    for value, name in _SCALES:
        if n >= value:
            out += _hundreds_to_words(n // value) + [name]
            n %= value
    if n:
        out += _hundreds_to_words(n)
    return out


def _number_to_words(token) -> list[str]:
    """Words for a number-ish token: 26000, "26,000", "26k", "1.5", "1500s".

    Accepts an int or str. It NEVER raises: anything it cannot convert comes
    back unchanged as a single word (or nothing at all for pure punctuation).
    """
    raw = token if isinstance(token, str) else str(token)
    text = raw.strip().lower()
    if _NUM_TOKEN_RE.match(text):
        mult = _SUFFIX_MULT.get(text[-1], 1)
        digits = (text[:-1] if mult > 1 else text).replace(",", "")
        if "." in digits and mult > 1:
            words = _int_to_words(int(round(float(digits) * mult)))
            return words if words is not None else [raw]
        if "." in digits:
            whole, _, frac = digits.partition(".")
            whole_words = _int_to_words(int(whole))
            if whole_words is None:
                return [raw]
            return whole_words + ["point"] + [
                "zero" if d == "0" else _ONES_LIST[int(d)] for d in frac]
        words = _int_to_words(int(digits) * mult)
        return words if words is not None else [raw]
    if _PLURAL_RE.match(text):
        n = int(text[:-1].replace(",", ""))
        if 1000 <= n <= 9999 and n % 100 == 0:
            return _hundreds_to_words(n // 100) + ["hundreds"]
        words = _int_to_words(n)
        if words is None:
            return [raw]
        return words + ["s"]
    plain = re.sub(r"[^\w]", "", raw.strip())
    if plain.isdecimal():
        words = _int_to_words(int(plain))
        if words is not None:
            return words
    return [plain] if plain else []


def _parse_number_words(words: Sequence[str], i: int) -> tuple[int, int] | None:
    """Longest number starting at words[i]; returns (value, word_count) or None.

    Accepts full forms (one thousand nine hundred three) and year forms
    (nineteen oh three, eighteen fifty, fifteen hundred) for the same value.
    """
    n = len(words)
    j = i
    total = 0
    if j < n and words[j] in _ONES and j + 1 < n and words[j + 1] == "thousand":
        total += _ONES[words[j]] * 1000
        j += 2
    if j < n and words[j] in _ONES and j + 1 < n and words[j + 1] == "hundred":
        total += _ONES[words[j]] * 100
        j += 2
    if j < n and words[j] in _TENS:
        total += _TENS[words[j]]
        j += 1
        if j < n and words[j] in _ONES:
            total += _ONES[words[j]]
            j += 1
    elif j < n and (words[j] in _TEENS or words[j] in _ONES):
        total += _TEENS.get(words[j], _ONES.get(words[j], 0))
        j += 1
    elif j == i:
        return None
    if j - i == 1 and 10 <= total <= 99:
        # Year forms: fifteen hundred / nineteen oh three / eighteen fifty.
        if j < n and words[j] == "hundred":
            return total * 100, 2
        if j + 1 < n and words[j] == "oh" and words[j + 1] in _ONES:
            return total * 100 + _ONES[words[j + 1]], 3
        if j < n and words[j] in _TENS:
            return total * 100 + _TENS[words[j]], 2
    return total, j - i


def _merge_digit_fragments(toks: list[tuple[int, str]]) -> list[tuple[int, int, str]]:
    """Join Whisper's split numbers like '1' + ',500' or '1' + '.5', keeping index ranges."""
    out: list[tuple[int, int, str]] = []
    for idx, t in toks:
        if t.startswith(",") and out and re.fullmatch(r"\d{1,3}(,\d{3})*", out[-1][2]):
            first, _, prev = out[-1]
            out[-1] = (first, idx, prev.replace(",", "") + t[1:].replace(",", ""))
        elif t.startswith(".") and out and re.fullmatch(r"\d{1,3}(,\d{3})*", out[-1][2]):
            first, _, prev = out[-1]
            out[-1] = (first, idx, prev + t)
        else:
            out.append((idx, idx, t))
    return out


def _canonical(tokens: Sequence[str]) -> tuple[list[str], list[tuple[int, int]]]:
    """Normalise raw tokens for matching.

    Returns (canonical_words, spans) where spans[k] is the (first, last) index
    of the input tokens behind canonical_words[k]. Lowercase, punctuation
    removed, hyphens split, and every number (digits with commas or decimals,
    k/m/b suffixes, spelled words) mapped to the same full-form words.
    """
    toks = _merge_digit_fragments(
        [(i, str(t).strip()) for i, t in enumerate(tokens) if str(t).strip()]
    )
    atom_words: list[str] = []
    atom_first: list[int] = []
    atom_last: list[int] = []
    for first, last, t in toks:
        for part in re.split(r"[-\u2013\u2014]", t):
            for w in _number_to_words(part.lower()):
                atom_words.append(w)
                atom_first.append(first)
                atom_last.append(last)
    canon: list[str] = []
    spans: list[tuple[int, int]] = []
    i = 0
    while i < len(atom_words):
        parsed = _parse_number_words(atom_words, i)
        if parsed:
            value, size = parsed
            expanded = _number_to_words(value)
            canon.extend(expanded)
            span = (atom_first[i], atom_last[i + size - 1])
            spans.extend([span] * len(expanded))
            i += size
        else:
            canon.append(atom_words[i])
            spans.append((atom_first[i], atom_last[i]))
            i += 1
    return canon, spans


def align(script_text: str, whisper_words: list[dict]) -> list[TimedWord]:
    script_words = script_text.split()
    if not script_words:
        return []
    s_can, s_spans = _canonical(script_words)
    w_can, w_spans = _canonical([w["w"] for w in whisper_words])
    times: list[tuple[float, float] | None] = [None] * len(script_words)
    sm = SequenceMatcher(None, s_can, w_can, autojunk=False)
    for blk in sm.get_matching_blocks():
        k = 0
        while k < blk.size:
            span = s_spans[blk.a + k]
            m = 1
            while k + m < blk.size and s_spans[blk.a + k + m] == span:
                m += 1
            ws = w_spans[blk.b + k][0]
            we = w_spans[blk.b + k + m - 1][1]
            start = float(whisper_words[ws]["s"])
            end = float(whisper_words[we]["e"])
            a, b = span
            count = b - a + 1
            for r in range(count):
                if times[a + r] is None:
                    times[a + r] = (
                        start + (end - start) * r / count,
                        start + (end - start) * (r + 1) / count,
                    )
            k += m

    missing = [i for i, t in enumerate(times) if t is None]
    total = len(script_words)
    if len(missing) * UNMATCHED_FAIL_SHARE > total:
        words = ", ".join(script_words[i] for i in missing)
        raise AlignmentError(
            f"{len(missing)} of {total} script words unmatched (more than 25%): {words}"
        )
    if len(missing) * UNMATCHED_WARN_SHARE > total:
        words = ", ".join(script_words[i] for i in missing)
        log.warning(
            "%d of %d script words unmatched (between 10%% and 25%%): %s",
            len(missing), total, words,
        )

    first_start = float(whisper_words[0]["s"]) if whisper_words else 0.0
    last_end = float(whisper_words[-1]["e"]) if whisper_words else 0.0
    out: list[TimedWord] = []
    prev_end = first_start
    i = 0
    while i < len(script_words):
        found = times[i]
        if found is not None:
            out.append(TimedWord(script_words[i], found[0], found[1]))
            prev_end = found[1]
            i += 1
            continue
        j = i
        while j < len(script_words) and times[j] is None:
            j += 1
        nxt = times[j] if j < len(script_words) else None
        next_start = nxt[0] if nxt is not None else last_end
        step = (next_start - prev_end) / ((j - i) + 1)
        for k in range(i, j):
            out.append(TimedWord(script_words[k], prev_end + step * (k - i + 1), prev_end + step * (k - i + 2)))
        prev_end = next_start
        i = j
    return out


def fallback_timed_words(brief: "Brief", voice_dir: Path) -> list[TimedWord]:
    """Proportional times when alignment fails, so a video never dies on timing.

    Each scene's script words are spread over its own voice part
    <voice_dir>/<scene_id>.wav (duration via the wave module), in proportion to
    word length, with the 0.35 s join pauses between scenes. The last word ends
    at the total joined narration duration.
    """
    out: list[TimedWord] = []
    t = 0.0
    for i, scene in enumerate(brief.scenes):
        if i:
            t += PAUSE_S
        with wave.open(str(Path(voice_dir) / f"{scene.id}.wav"), "rb") as w:
            dur = w.getnframes() / w.getframerate()
        words = scene.narration.split()
        weights = [max(len(word), 1) for word in words]
        total = sum(weights)
        for word, weight in zip(words, weights):
            span = dur * weight / total
            out.append(TimedWord(word, t, t + span))
            t += span
    return out


def transcribe(wav_path: Path, out_dir: Path, lang: str = "en", model: str = "medium") -> Path:
    """vo-words.json for wav_path, via faster-whisper (Windows laptop) or whisper.cpp (server).

    On Windows the path runs the vendor KAPE transcribe.py (faster-whisper) exactly as before.
    Everywhere else - where faster-whisper cannot be installed (no musl wheels) - it runs
    `hyperframes transcribe` (whisper.cpp, pinned hyperframes version) and converts its
    word list into the same vo-words.json segments contract. HYPERFRAMES_BIN overrides the
    hyperframes executable; SHORTS_WHISPER_MODEL overrides the whisper.cpp model (small.en
    on purpose: it is the fastest model that still reads our narration reliably).
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        cmd = [sys.executable, str(TRANSCRIBE_SCRIPT), str(wav_path), str(out_dir),
               "--lang", lang, "--model", model]
        subprocess.run(cmd, check=True)
        return out_dir / "vo-words.json"
    return transcribe_hyperframes(wav_path, out_dir, lang=lang)


def transcribe_hyperframes(wav_path: Path, out_dir: Path, lang: str = "en") -> Path:
    """whisper.cpp word timings via the pinned hyperframes CLI, in vo-words.json shape."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    work = out_dir / ".hf-transcribe"
    work.mkdir(exist_ok=True)
    # transcript.json is written next to the input file: run on a copy inside the workdir.
    local_wav = work / "vo.wav"
    shutil.copyfile(wav_path, local_wav)
    model = os.environ.get("SHORTS_WHISPER_MODEL", "small.en")
    bin_override = os.environ.get("HYPERFRAMES_BIN", "").strip()
    head = [bin_override] if bin_override else ["npx", "--yes", HYPERFRAMES_SPEC]
    cmd = head + ["transcribe", "vo.wav", "--engine", "whisper",
                  "--model", model, "--language", lang, "--json"]
    env = dict(os.environ)
    env.setdefault("HYPERFRAMES_BROWSER_PATH", "/usr/bin/chromium-browser")
    subprocess.run(cmd, check=True, capture_output=True, env=env, cwd=work,
                   timeout=TRANSCRIBE_TIMEOUT_S)
    words = json.loads((work / "transcript.json").read_text(encoding="utf-8"))
    segments = [{"s": round(float(w["start"]), 2), "e": round(float(w["end"]), 2),
                 "text": str(w["text"]), "words": [{"w": str(w["text"]),
                                                    "s": round(float(w["start"]), 2),
                                                    "e": round(float(w["end"]), 2)}]}
                for w in words]
    (out_dir / "vo-words.json").write_text(json.dumps(segments, ensure_ascii=False),
                                           encoding="utf-8")
    return out_dir / "vo-words.json"

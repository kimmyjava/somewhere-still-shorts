"""Word timing: Whisper's word times + the script text -> TimedWords with script spelling."""
import json
import logging
import re
import subprocess
import sys
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Sequence

TRANSCRIBE_SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "vendor" / "kape-explainer" / "skills" / "kape-explainer" / "scripts" / "transcribe.py"
)

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


def _number_to_words(n: int) -> list[str]:
    """Self-written number-to-words for integers 0..9999: 1500 -> one thousand five hundred."""
    if not 0 <= n <= 9999:
        raise ValueError(f"number out of range: {n}")
    if n == 0:
        return ["zero"]
    out: list[str] = []
    if n >= 1000:
        out += [_ONES_LIST[n // 1000], "thousand"]
    n %= 1000
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
    """Join Whisper's split numbers like '1' + ',500' back into '1500', keeping index ranges."""
    out: list[tuple[int, int, str]] = []
    for idx, t in toks:
        if t.startswith(",") and out and re.fullmatch(r"\d{1,3}(,\d{3})*", out[-1][2]):
            first, _, prev = out[-1]
            out[-1] = (first, idx, prev.replace(",", "") + t[1:].replace(",", ""))
        else:
            out.append((idx, idx, t))
    return out


def _canonical(tokens: Sequence[str]) -> tuple[list[str], list[tuple[int, int]]]:
    """Normalise raw tokens for matching.

    Returns (canonical_words, spans) where spans[k] is the (first, last) index
    of the input tokens behind canonical_words[k]. Lowercase, punctuation
    removed, hyphens split, and every number (digits with commas or spelled
    words) mapped to the same full-form words.
    """
    toks = _merge_digit_fragments(
        [(i, str(t).strip()) for i, t in enumerate(tokens) if str(t).strip()]
    )
    atom_words: list[str] = []
    atom_first: list[int] = []
    atom_last: list[int] = []
    for first, last, t in toks:
        for part in re.split(r"[-\u2013\u2014]", t):
            p = re.sub(r"[^\w]", "", part.lower())
            if not p:
                continue
            expanded = _number_to_words(int(p)) if p.isdigit() else [p]
            for w in expanded:
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


def transcribe(wav_path: Path, out_dir: Path, lang: str = "en", model: str = "medium") -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, str(TRANSCRIBE_SCRIPT), str(wav_path), str(out_dir), "--lang", lang, "--model", model]
    subprocess.run(cmd, check=True)
    return out_dir / "vo-words.json"

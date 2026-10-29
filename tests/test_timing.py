"""Fast timing tests on the real rain fixture (no Whisper run)."""
import logging
import sys
from pathlib import Path

import pytest

from shorts.timing import (
    AlignmentError,
    _canonical,
    _number_to_words,
    _parse_number_words,
    align,
    load_whisper_words,
    transcribe,
)

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
SCRIPT = (FIXTURES / "script_rain.txt").read_text(encoding="utf-8")
SCRIPT_WORDS = SCRIPT.split()
FLAT = load_whisper_words(FIXTURES / "words_rain.json")


def test_load_whisper_words_flattens_segments():
    assert len(FLAT) == 56
    assert set(FLAT[0]) == {"w", "s", "e"}
    assert FLAT[0]["w"].strip() == "Do"


def test_exact_alignment_gives_script_spelling_and_whisper_times():
    aligned = align(SCRIPT, FLAT)
    assert len(aligned) == len(SCRIPT_WORDS)
    assert [w.text for w in aligned] == SCRIPT_WORDS
    for a, f in zip(aligned, FLAT):
        assert a.start == pytest.approx(f["s"])
        assert a.end == pytest.approx(f["e"])
    assert aligned[13].text == "little?"
    assert aligned[13].start == pytest.approx(2.92)
    assert aligned[13].end == pytest.approx(3.14)


def test_one_changed_whisper_word_still_aligns():
    flat = [dict(w) for w in FLAT]
    flat[9]["w"] = " roofx"
    aligned = align(SCRIPT, flat)
    assert [w.text for w in aligned] == SCRIPT_WORDS
    roof = aligned[9]
    assert roof.start == pytest.approx(2.28)
    assert roof.end == pytest.approx(2.4)


def test_one_missing_whisper_word_gets_in_between_time():
    flat = [dict(w) for w in FLAT]
    del flat[16]
    aligned = align(SCRIPT, flat)
    assert [w.text for w in aligned] == SCRIPT_WORDS
    slower = aligned[16]
    assert slower.start == pytest.approx(4.6)
    assert slower.end == pytest.approx(4.82)
    assert aligned[15].end == pytest.approx(4.38)
    assert aligned[17].start == pytest.approx(4.82)


def test_too_many_differences_raise_alignment_error():
    with pytest.raises(AlignmentError):
        align("a completely different narration about trains", FLAT)


def test_number_to_words_small_integers():
    assert _number_to_words(1500) == ["one", "thousand", "five", "hundred"]
    assert _number_to_words(1903) == ["one", "thousand", "nine", "hundred", "three"]
    assert _number_to_words(9999) == ["nine", "thousand", "nine", "hundred", "ninety", "nine"]
    assert _number_to_words(0) == ["zero"]
    with pytest.raises(ValueError):
        _number_to_words(10000)


def test_year_form_and_full_form_parse_to_same_value():
    assert _parse_number_words("nineteen oh three".split(), 0) == (1903, 3)
    assert _parse_number_words("one thousand nine hundred three".split(), 0) == (1903, 5)
    assert _parse_number_words("fifteen hundred".split(), 0) == (1500, 2)
    assert _parse_number_words("one thousand five hundred".split(), 0) == (1500, 4)
    assert _parse_number_words("cozy socks".split(), 0) is None


def test_canonical_maps_comma_digits_and_spelled_numbers_alike():
    digits, spans = _canonical(["1,500"])
    assert digits == ["one", "thousand", "five", "hundred"]
    assert spans == [(0, 0), (0, 0), (0, 0), (0, 0)]
    spelled, _ = _canonical("fifteen hundred".split())
    assert spelled == digits


def test_number_words_match_digit_whisper():
    script = "People about fifteen hundred years ago"
    whisper = [
        {"w": " People ", "s": 0.0, "e": 0.3},
        {"w": " about ", "s": 0.3, "e": 0.6},
        {"w": " 1 ", "s": 0.6, "e": 0.9},
        {"w": " ,500 ", "s": 0.9, "e": 1.8},
        {"w": " years ", "s": 1.8, "e": 2.1},
        {"w": " ago ", "s": 2.1, "e": 2.4},
    ]
    aligned = align(script, whisper)
    assert [w.text for w in aligned] == script.split()
    assert aligned[2].start == pytest.approx(0.6)
    assert aligned[2].end == pytest.approx(1.2)
    assert aligned[3].start == pytest.approx(1.2)
    assert aligned[3].end == pytest.approx(1.8)
    assert aligned[4].start == pytest.approx(1.8)


def test_year_digits_match_year_words_both_ways():
    words = [
        {"w": " back ", "s": 0.0, "e": 0.5},
        {"w": " in ", "s": 0.5, "e": 0.8},
        {"w": " nineteen ", "s": 0.8, "e": 1.4},
        {"w": " oh ", "s": 1.4, "e": 1.6},
        {"w": " three ", "s": 1.6, "e": 2.2},
    ]
    aligned = align("back in 1903", words)
    assert [w.text for w in aligned] == ["back", "in", "1903"]
    assert aligned[2].start == pytest.approx(0.8)
    assert aligned[2].end == pytest.approx(2.2)

    digit = [
        {"w": " back ", "s": 0.0, "e": 0.5},
        {"w": " in ", "s": 0.5, "e": 0.8},
        {"w": " 1903 ", "s": 0.8, "e": 2.2},
    ]
    aligned = align("back in one thousand nine hundred three", digit)
    assert [w.text for w in aligned] == "back in one thousand nine hundred three".split()
    assert aligned[2].start == pytest.approx(0.8)
    assert aligned[6].end == pytest.approx(2.2)


def test_hyphenated_words_match():
    script = "a toe-split sock"
    spaced = [
        {"w": " a ", "s": 0.0, "e": 0.4},
        {"w": " toe ", "s": 0.4, "e": 0.8},
        {"w": " split ", "s": 0.8, "e": 1.2},
        {"w": " sock ", "s": 1.2, "e": 1.6},
    ]
    aligned = align(script, spaced)
    assert [w.text for w in aligned] == script.split()
    # "toe-split" spans both spoken parts
    assert aligned[1].start == pytest.approx(0.4)
    assert aligned[1].end == pytest.approx(1.2)
    assert aligned[2].start == pytest.approx(1.2)
    assert aligned[2].end == pytest.approx(1.6)

    joined = [
        {"w": " a ", "s": 0.0, "e": 0.4},
        {"w": " toe-split ", "s": 0.4, "e": 1.2},
        {"w": " sock ", "s": 1.2, "e": 1.6},
    ]
    aligned = align("a toe split sock", joined)
    assert aligned[1].start == pytest.approx(0.4)
    assert aligned[2].end == pytest.approx(1.2)


def test_twenty_percent_unmatched_warns_but_aligns(caplog):
    words = "alpha bravo charlie delta echo foxtrot golf hotel india juliet".split()
    whisper = [
        {"w": f" {w} ", "s": float(i), "e": float(i) + 1.0}
        for i, w in enumerate(words)
        if w not in ("india", "juliet")
    ]
    with caplog.at_level(logging.WARNING, logger="shorts.timing"):
        aligned = align(" ".join(words), whisper)
    assert [w.text for w in aligned] == words
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "india" in warnings[0].getMessage()
    assert "juliet" in warnings[0].getMessage()


def test_thirty_percent_unmatched_raises(caplog):
    words = "alpha bravo charlie delta echo foxtrot golf hotel india juliet".split()
    whisper = [
        {"w": f" {w} ", "s": float(i), "e": float(i) + 1.0}
        for i, w in enumerate(words)
        if w not in ("hotel", "india", "juliet")
    ]
    with caplog.at_level(logging.WARNING, logger="shorts.timing"):
        with pytest.raises(AlignmentError):
            align(" ".join(words), whisper)
    assert not [r for r in caplog.records if r.levelno == logging.WARNING]


def test_transcribe_runs_vendor_script_with_same_python(tmp_path, monkeypatch):
    recorded = {}

    def fake_run(cmd, check):
        recorded["cmd"] = cmd
        Path(cmd[3]).mkdir(parents=True, exist_ok=True)
        (Path(cmd[3]) / "vo-words.json").write_text("[]", encoding="utf-8")

    monkeypatch.setattr("shorts.timing.subprocess.run", fake_run)
    out = transcribe(tmp_path / "vo.wav", tmp_path / "timing", lang="en", model="medium")

    cmd = recorded["cmd"]
    assert cmd[0] == sys.executable
    assert cmd[1].endswith("transcribe.py")
    assert Path(cmd[1]).is_file()
    assert cmd[2] == str(tmp_path / "vo.wav")
    assert cmd[3] == str(tmp_path / "timing")
    assert cmd[4:6] == ["--lang", "en"]
    assert cmd[6:8] == ["--model", "medium"]
    assert out == tmp_path / "timing" / "vo-words.json"
    assert out.exists()

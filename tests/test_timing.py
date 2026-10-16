"""Fast timing tests on the real rain fixture (no Whisper run)."""
import sys
from pathlib import Path

import pytest

from shorts.timing import AlignmentError, align, load_whisper_words, transcribe

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

"""Fast captions tests (chunking, SRT, overlay HTML) - no Whisper, no render."""
from pathlib import Path

import pytest

from shorts.captions import caption_composition, make_chunks, write_srt
from shorts.timing import TimedWord, align, load_whisper_words

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
SCRIPT = (FIXTURES / "script_rain.txt").read_text(encoding="utf-8")
FLAT = load_whisper_words(FIXTURES / "words_rain.json")


def chunk_words():
    return [
        TimedWord("The", 0.0, 0.3),
        TimedWord("rain", 0.3, 0.6),
        TimedWord("falls?", 0.6, 0.9),
        TimedWord("It", 0.9, 1.2),
        TimedWord("never", 1.2, 1.5),
        TimedWord("stops.", 1.5, 1.8),
        TimedWord("Softly", 2.3, 2.6),
    ]


def test_chunks_respect_max_words_punctuation_and_pause():
    chunks = make_chunks(chunk_words(), max_words=3, pause=0.35)
    assert [len(c.words) for c in chunks] == [3, 3, 1]
    assert chunks[0].words[-1].text == "falls?"
    assert chunks[1].words[-1].text == "stops."
    assert chunks[2].words[0].text == "Softly"
    assert chunks[0].start == pytest.approx(0.0)
    assert chunks[0].end == pytest.approx(0.9)
    assert chunks[1].end == pytest.approx(2.3)
    assert chunks[2].end == pytest.approx(3.0)


def test_chunks_never_exceed_max_words():
    words = [TimedWord(f"w{i}", i * 0.2, i * 0.2 + 0.15) for i in range(7)]
    chunks = make_chunks(words, max_words=2, pause=0.35)
    assert all(len(c.words) <= 2 for c in chunks)
    assert [len(c.words) for c in chunks] == [2, 2, 2, 1]


def test_chunk_breaks_on_long_pause():
    words = [TimedWord("one", 0.0, 0.3), TimedWord("two", 1.0, 1.3)]
    chunks = make_chunks(words, max_words=3, pause=0.35)
    assert [c.words[0].text for c in chunks] == ["one", "two"]


def test_make_chunks_sorts_out_of_order_words_monotonic():
    words = [
        TimedWord("stops.", 1.5, 1.2),
        TimedWord("never", 0.9, 1.2),
        TimedWord("It", 0.6, 0.9),
        TimedWord("rain", 0.3, 0.6),
        TimedWord("The", 0.0, 0.3),
    ]
    chunks = make_chunks(words, max_words=3)
    flat = [w for c in chunks for w in c.words]
    assert [w.text for w in flat] == ["The", "rain", "It", "never", "stops."]
    for prev, cur in zip(flat, flat[1:]):
        assert cur.start >= prev.start
    for w in flat:
        assert w.end >= w.start + 0.05


def test_write_srt_format(tmp_path):
    path = write_srt(make_chunks(chunk_words()), tmp_path / "captions.srt")
    blocks = path.read_text(encoding="utf-8").strip().split("\n\n")
    assert len(blocks) == 3
    assert blocks[0] == "1\n00:00:00,000 --> 00:00:00,900\nThe rain falls?"
    assert blocks[1] == "2\n00:00:00,900 --> 00:00:02,300\nIt never stops."
    assert blocks[2] == "3\n00:00:02,300 --> 00:00:03,000\nSoftly"


def test_html_contains_every_script_word_and_no_placeholders():
    aligned = align(SCRIPT, FLAT)
    html = caption_composition(make_chunks(aligned), total_seconds=aligned[-1].end)
    for token in SCRIPT.split():
        assert token in html
    assert "{{" not in html
    assert 'data-composition-id="m-captions"' in html
    assert "var(--" not in html
    assert "#C9824B" in html
    assert "#2B2A28" in html
    assert "window.__timelines['m-captions']" in html


def test_html_chunk_windows_and_word_highlight():
    html = caption_composition(make_chunks(chunk_words()), total_seconds=2.8)
    assert "tl.set('#cc0', {opacity: 1}, 0.0);" in html
    assert "tl.set('#cc0', {opacity: 0}, 0.9);" in html
    assert "tl.set('#cw0-0', {color: '#C9824B'}, 0.0);" in html
    assert "tl.set('#cw0-0', {color: '#2B2A28'}, 0.3);" in html
    assert "tl.set('#cc2', {opacity: 1}, 2.3);" in html
    assert "tl.set('#cc2', {opacity: 0}, 2.8);" in html

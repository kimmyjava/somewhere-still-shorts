"""Fast look tests: cozy scene HTML + captions HTML from CaptionChunk."""
import pytest

from shorts.captions import make_chunks
from shorts.look import PALETTE, cozy_captions_html, cozy_scene_html
from shorts.timing import TimedWord


def chunk_words():
    return [
        TimedWord("The", 0.0, 0.3),
        TimedWord("kettle", 0.3, 0.6),
        TimedWord("hums?", 0.6, 0.9),
        TimedWord("Slowly.", 1.4, 1.8),
    ]


def test_scene_html_contains_bg_path_headline_no_placeholders():
    html = cozy_scene_html("s01-places", 4.95, "Places stay with us", "bg-street")
    assert "assets/bg/bg-street.jpg" in html
    assert "Places stay with us" in html
    assert 'data-composition-id="s01-places"' in html
    assert "{{" not in html
    assert "var(--" not in html
    assert PALETTE["cream"] in html
    assert PALETTE["night"] in html
    assert "Fraunces" in html


def test_captions_html_contains_every_word_and_literal_colours():
    html = cozy_captions_html(make_chunks(chunk_words()), 3.0)
    for word in ("The", "kettle", "hums?", "Slowly."):
        assert word in html
    assert 'data-composition-id="m-captions"' in html
    assert "{{" not in html
    assert "var(--" not in html
    assert PALETTE["accent"] in html
    assert PALETTE["ink"] in html
    assert "Nunito" in html


def test_captions_html_chunk_windows_and_word_highlight():
    html = cozy_captions_html(make_chunks(chunk_words()), 3.0)
    assert "tl.fromTo('#cc0', {opacity:0, y:10}, {opacity:1, y:0, duration:0.18, ease:'power2.out'}, 0.0);" in html
    assert "tl.set('#cc0', {opacity:0}, 1.4);" in html
    assert "tl.set('#cc1', {opacity:0}, 2.2);" in html
    assert "tl.set('#cw0-0', {color:'#9E4A24'}, 0.0);" in html
    assert "tl.set('#cw0-0', {color:'#3B2416'}, 0.3);" in html
    assert "tl.set({}, {}, 3.0);" in html

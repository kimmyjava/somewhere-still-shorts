"""Fast look tests: cozy scene HTML + captions HTML from CaptionChunk."""
import re

import pytest

from shorts.captions import CaptionChunk, make_chunks
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


def test_scene_html_cozy_zoom_starts_at_1():
    html = cozy_scene_html("s01-places", 4.95, "Places stay with us", "bg-street")
    assert "{scale:1.0," in html
    assert "{scale:1.08," in html


def test_scene_html_storybook_zoom_starts_at_1_06():
    html = cozy_scene_html("s01-places", 4.95, "Places stay with us", "bg-street", zoom_start=1.06)
    assert "{scale:1.06," in html
    assert "{scale:1.14," in html
    assert "{scale:1.0," not in html
    assert "{scale:1.08," not in html


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
    assert "tl.set('#cc1', {opacity:0}, 2.3);" in html
    assert "tl.set('#cw0-0', {color:'#9E4A24'}, 0.0);" in html
    assert "tl.set('#cw0-0', {color:'#3B2416'}, 0.3);" in html
    assert "tl.set({}, {}, 3.0);" in html


def _visible_windows(html):
    shows = {int(m.group(1)): float(m.group(2)) for m in re.finditer(
        r"tl\.fromTo\('#cc(\d+)', \{opacity:0, y:10\}, \{opacity:1, y:0, duration:0\.18, ease:'power2\.out'\}, ([0-9.]+)\);", html)}
    hides = {int(m.group(1)): float(m.group(2)) for m in re.finditer(
        r"tl\.set\('#cc(\d+)', \{opacity:0\}, ([0-9.]+)\);", html)}
    return shows, hides


def test_captions_html_same_start_chunks_never_overlap():
    words = [TimedWord("One.", 0.0, 0.3), TimedWord("Two.", 0.05, 0.3), TimedWord("Three.", 0.1, 0.3)]
    html = cozy_captions_html(make_chunks(words, max_words=1), 3.0)
    shows, hides = _visible_windows(html)
    assert shows == {0: 0.0, 1: 0.15, 2: 0.3}
    assert hides == {0: 0.15, 1: 0.3, 2: 0.8}
    for i in range(2):
        assert shows[i] < hides[i] <= shows[i + 1]


def test_captions_html_reversed_chunks_never_overlap():
    chunks = [
        CaptionChunk([TimedWord("Late.", 2.0, 2.3)], 2.0, 2.3),
        CaptionChunk([TimedWord("Mid", 1.0, 1.3)], 1.0, 1.3),
        CaptionChunk([TimedWord("Early", 0.0, 0.3)], 0.0, 0.3),
    ]
    html = cozy_captions_html(chunks, 4.0)
    assert '<div id="cc0" class="cap"><span id="cw0-0">Early</span></div>' in html
    shows, hides = _visible_windows(html)
    assert hides == {0: 1.0, 1: 2.0, 2: 2.8}
    for i in range(2):
        assert shows[i] < hides[i] <= shows[i + 1]

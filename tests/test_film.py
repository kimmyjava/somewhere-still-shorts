"""Fast film-plan tests: scene times, film.json updates, presenter poses."""
import pytest
from pathlib import Path

from shorts.brief import load_brief
from shorts.film import film_updates, presenter_poses, scene_times
from shorts.timing import TimedWord

FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "brief_kitchen.json"


def timed_words():
    words = []
    for k in range(28):
        start = k * 0.5
        words.append(TimedWord(f"w{k}", start, start + 0.4))
    return words


def test_scene_times_midpoints_and_totals():
    brief = load_brief(FIXTURE)
    words = timed_words()
    times = scene_times(brief, words, end_pad=2.0)

    assert [sid for sid, _s, _d in times] == ["s01-places", "s02-memories", "s03-back"]
    assert times[0][1] == pytest.approx(0.0)
    assert times[1][1] == pytest.approx(4.95)
    assert times[2][1] == pytest.approx(10.45)
    total = sum(d for _sid, _s, d in times)
    assert total == pytest.approx(15.9)
    assert times[-1][1] + times[-1][2] == pytest.approx(words[27].end + 2.0)


def test_scene_times_starts_increase_and_sum_is_exact():
    brief = load_brief(FIXTURE)
    times = scene_times(brief, timed_words())
    starts = [s for _sid, s, _d in times]
    assert starts == sorted(starts)
    for (_sid, s, d), next_start in zip(times, starts[1:]):
        assert pytest.approx(s + d) == next_start
    total = sum(d for _sid, _s, d in times)
    assert total == pytest.approx(starts[-1] + times[-1][2])


def test_scene_times_end_pad_parameter():
    brief = load_brief(FIXTURE)
    times = scene_times(brief, timed_words(), end_pad=1.0)
    assert times[-1][1] + times[-1][2] == pytest.approx(13.9 + 1.0)


def test_film_updates_fields():
    brief = load_brief(FIXTURE)
    times = scene_times(brief, timed_words())
    updates = film_updates(times, voice_dur=13.9)

    assert updates["scenes"] == [["s01-places", 4.95], ["s02-memories", 5.5], ["s03-back", 5.45]]
    assert updates["audio"] == [
        {"id": "vo", "src": "assets/audio/vo-master.wav", "dur": 13.9, "volume": 1, "track": 9}]
    assert updates["cues"] == []
    assert [o["id"] for o in updates["overlays"]] == ["m-kape", "m-brand", "m-captions"]
    assert [o["track"] for o in updates["overlays"]] == [2, 3, 4]
    assert [o["z"] for o in updates["overlays"]] == [5, 6, 7]
    assert "bgm" not in updates


def test_presenter_poses_first_at_zero_and_lead_time():
    brief = load_brief(FIXTURE)
    times = scene_times(brief, timed_words())
    poses = presenter_poses(times, brief)

    assert poses == [[0.0, "wave"], [4.85, "present"], [10.35, "point"]]


def test_presenter_poses_strictly_increasing_no_duplicates():
    brief = load_brief(FIXTURE)
    times = [("s01-x", 0.0, 1.0), ("s02-y", 0.05, 1.0), ("s03-z", 0.08, 1.0)]
    poses = presenter_poses(times, brief)

    stamps = [p[0] for p in poses]
    assert stamps[0] == 0.0
    assert stamps == sorted(set(stamps))
    assert len(stamps) == 3

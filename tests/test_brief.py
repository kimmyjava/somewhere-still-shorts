"""Fast brief tests: fixture loading and every BriefError rule."""
import copy
import json
from pathlib import Path

import pytest

from shorts.brief import BriefError, full_narration, load_brief

FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "brief_kitchen.json"


def write_brief(tmp_path, data) -> Path:
    p = tmp_path / "brief.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def good_brief():
    return {
        "slug": "kitchen-table",
        "title": "Places that stay with us",
        "scenes": [
            {"id": "s01-places", "narration": "one two three", "headline": "H1", "bg": "bg-kitchen"},
            {"id": "s02-memories", "narration": "four five six", "headline": "H2", "bg": "bg-street"},
        ],
    }


def test_fixture_loads():
    brief = load_brief(FIXTURE)
    assert brief.slug == "kitchen-table"
    assert brief.title == "Places that stay with us"
    assert brief.cta == "Follow for more"
    assert brief.style == "cozy"
    assert [s.id for s in brief.scenes] == ["s01-places", "s02-memories", "s03-back"]
    assert [s.pose for s in brief.scenes] == ["wave", "present", "point"]
    assert [s.bg for s in brief.scenes] == ["bg-street", "bg-kitchen", "bg-books"]
    assert brief.scenes[1].headline == "Small memories"
    assert brief.scenes[0].narration.startswith("Some places stay with us")


def test_scene_without_bg_and_bg_prompt_rejected(tmp_path):
    d = good_brief()
    del d["scenes"][0]["bg"]
    with pytest.raises(BriefError, match="needs bg or bg_prompt"):
        load_brief(write_brief(tmp_path, d))


def test_bg_prompt_only_is_ok(tmp_path):
    d = good_brief()
    del d["scenes"][0]["bg"]
    d["scenes"][0]["bg_prompt"] = "a rainy cobblestone street at dusk"
    brief = load_brief(write_brief(tmp_path, d))
    assert brief.scenes[0].bg == ""
    assert brief.scenes[0].bg_prompt == "a rainy cobblestone street at dusk"


def test_bg_prompt_longer_than_400_rejected(tmp_path):
    d = good_brief()
    d["scenes"][0]["bg_prompt"] = "x" * 401
    with pytest.raises(BriefError, match="bg_prompt is 401 characters"):
        load_brief(write_brief(tmp_path, d))


def test_bg_prompt_of_400_is_ok(tmp_path):
    d = good_brief()
    del d["scenes"][0]["bg"]
    d["scenes"][0]["bg_prompt"] = "x" * 400
    brief = load_brief(write_brief(tmp_path, d))
    assert brief.scenes[0].bg_prompt == "x" * 400


def test_missing_bg_image_rejected(tmp_path):
    d = good_brief()
    d["scenes"][0]["bg"] = "bg-nope"
    with pytest.raises(BriefError, match="bg-nope.jpg does not exist"):
        load_brief(write_brief(tmp_path, d))


def test_full_narration_joins_with_one_space():
    brief = load_brief(FIXTURE)
    text = full_narration(brief)
    assert text == " ".join(s.narration for s in brief.scenes)
    assert "  " not in text
    assert text.startswith("Some places stay")
    assert text.endswith("for a moment.")


def test_slug_must_be_lowercase_digits_hyphens(tmp_path):
    d = good_brief()
    d["slug"] = "Kitchen Table"
    with pytest.raises(BriefError, match="slug"):
        load_brief(write_brief(tmp_path, d))


def test_zero_scenes_rejected(tmp_path):
    d = good_brief()
    d["scenes"] = []
    with pytest.raises(BriefError, match="0 scenes"):
        load_brief(write_brief(tmp_path, d))


def test_more_than_twenty_scenes_rejected(tmp_path):
    d = good_brief()
    d["scenes"] = [{"id": f"s{i:02d}-x", "narration": "a", "headline": "h"} for i in range(1, 22)]
    with pytest.raises(BriefError, match="21 scenes"):
        load_brief(write_brief(tmp_path, d))


def test_duplicate_scene_ids_rejected(tmp_path):
    d = good_brief()
    d["scenes"][1]["id"] = "s01-places"
    with pytest.raises(BriefError, match="more than once"):
        load_brief(write_brief(tmp_path, d))


@pytest.mark.parametrize("bad_id", ["scene1", "s1-x", "s001-x", "s01-Places", "s01_x"])
def test_bad_scene_id_rejected(tmp_path, bad_id):
    d = good_brief()
    d["scenes"][0]["id"] = bad_id
    with pytest.raises(BriefError, match="id"):
        load_brief(write_brief(tmp_path, d))


def test_empty_narration_rejected(tmp_path):
    d = good_brief()
    d["scenes"][0]["narration"] = "   "
    with pytest.raises(BriefError, match="narration is empty"):
        load_brief(write_brief(tmp_path, d))


def test_headline_longer_than_40_rejected(tmp_path):
    d = good_brief()
    d["scenes"][0]["headline"] = "x" * 41
    with pytest.raises(BriefError, match="headline"):
        load_brief(write_brief(tmp_path, d))


def test_headline_of_40_is_ok(tmp_path):
    d = good_brief()
    d["scenes"][0]["headline"] = "x" * 40
    brief = load_brief(write_brief(tmp_path, d))
    assert brief.scenes[0].headline == "x" * 40


def test_unknown_pose_rejected(tmp_path):
    d = good_brief()
    d["scenes"][0]["pose"] = "dance"
    with pytest.raises(BriefError, match="pose"):
        load_brief(write_brief(tmp_path, d))


def test_pose_default_is_idle(tmp_path):
    d = good_brief()
    brief = load_brief(write_brief(tmp_path, copy.deepcopy(d)))
    assert brief.scenes[0].pose == "idle"


STORYBOOK_FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "brief_storybook.json"


def test_style_storybook_is_kept():
    brief = load_brief(STORYBOOK_FIXTURE)
    assert brief.style == "storybook"
    assert [s.id for s in brief.scenes] == ["s01-places", "s02-memories", "s03-back"]


def test_unknown_style_falls_back_to_cozy_with_warning(tmp_path, capsys):
    d = good_brief()
    d["style"] = "cyberpunk"
    brief = load_brief(write_brief(tmp_path, d))
    assert brief.style == "cozy"
    out = capsys.readouterr().out
    assert "WARNING" in out
    assert "cyberpunk" in out


def test_unknown_extra_top_level_fields_are_allowed(tmp_path):
    d = good_brief()
    d["mood"] = "rainy"
    d["source"] = "n8n"
    brief = load_brief(write_brief(tmp_path, d))
    assert brief.style == "cozy"
    assert brief.slug == "kitchen-table"

"""Video brief: validated JSON in, Brief object out."""
import json
import re
from dataclasses import dataclass
from pathlib import Path

from shorts.images import LIBRARY, STYLE_TEXTS

SLUG_RE = re.compile(r"^[a-z0-9-]+$")
SCENE_ID_RE = re.compile(r"^s\d{2}-[a-z0-9-]+$")
POSES = ("idle", "wave", "point", "present", "think", "thumbs-up", "celebrate", "sit", "walk")
MAX_HEADLINE = 40
MAX_BG_PROMPT = 400
MAX_SCENES = 20
REPO = Path(__file__).resolve().parents[1]


class BriefError(Exception):
    """The brief JSON is not valid."""


@dataclass
class Scene:
    id: str
    narration: str
    headline: str
    bg: str = ""
    pose: str = "idle"
    bg_prompt: str = ""


@dataclass
class Brief:
    slug: str
    title: str
    scenes: list[Scene]
    cta: str = "Follow for more"
    music: str = "calm"
    style: str = "cozy"


def load_brief(path: Path) -> Brief:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    slug = str(data.get("slug", ""))
    if not SLUG_RE.match(slug):
        raise BriefError(f"slug must be lowercase letters, digits and hyphens, got {slug!r}")

    raw_scenes = data.get("scenes")
    if not isinstance(raw_scenes, list):
        raise BriefError("brief needs a 'scenes' list")
    if len(raw_scenes) == 0:
        raise BriefError("brief has 0 scenes")
    if len(raw_scenes) > MAX_SCENES:
        raise BriefError(f"brief has {len(raw_scenes)} scenes (max {MAX_SCENES})")

    scenes: list[Scene] = []
    seen: set[str] = set()
    for i, raw in enumerate(raw_scenes, 1):
        if not isinstance(raw, dict):
            raise BriefError(f"scene {i} is not an object")
        sid = str(raw.get("id", ""))
        if not SCENE_ID_RE.match(sid):
            raise BriefError(f"scene {i}: id {sid!r} does not match s<NN>-<slug> (e.g. s01-places)")
        if sid in seen:
            raise BriefError(f"scene id {sid!r} appears more than once")
        seen.add(sid)
        narration = str(raw.get("narration", ""))
        if not narration.strip():
            raise BriefError(f"scene {sid}: narration is empty")
        headline = str(raw.get("headline", ""))
        if len(headline) > MAX_HEADLINE:
            raise BriefError(f"scene {sid}: headline is {len(headline)} characters (max {MAX_HEADLINE})")
        bg = str(raw.get("bg", ""))
        bg_prompt = str(raw.get("bg_prompt", ""))
        if not bg and not bg_prompt.strip():
            raise BriefError(f"scene {sid}: needs bg or bg_prompt")
        if len(bg_prompt) > MAX_BG_PROMPT:
            raise BriefError(
                f"scene {sid}: bg_prompt is {len(bg_prompt)} characters (max {MAX_BG_PROMPT})")
        if bg and not (REPO / "assets" / "bg" / f"{bg}.jpg").is_file() \
                and not (LIBRARY / f"{bg}.jpg").is_file():
            raise BriefError(f"scene {sid}: assets/bg/{bg}.jpg does not exist in the repo or the library")
        pose = str(raw.get("pose", "idle"))
        if pose not in POSES:
            raise BriefError(f"scene {sid}: pose {pose!r} is not one of {', '.join(POSES)}")
        scenes.append(Scene(id=sid, narration=narration, headline=headline, bg=bg, pose=pose,
                            bg_prompt=bg_prompt))

    style = str(data.get("style", "cozy"))
    if style not in STYLE_TEXTS:
        print(f"WARNING: brief style {style!r} is not one of {', '.join(sorted(STYLE_TEXTS))} "
              f"- using 'cozy'", flush=True)
        style = "cozy"

    return Brief(slug=slug, title=str(data.get("title", "")), scenes=scenes,
                 cta=str(data.get("cta", "Follow for more")), music=str(data.get("music", "calm")),
                 style=style)


def full_narration(brief: Brief) -> str:
    return " ".join(s.narration for s in brief.scenes)

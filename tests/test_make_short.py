"""Fast make_short tests with fakes: no Voicebox, no Whisper, no node, no render, no network."""
import base64
import functools
import importlib.util
import json
import sys
from pathlib import Path

import httpx
import pytest

from shorts import images as shorts_images
from shorts.brief import full_narration, load_brief
from shorts.images import bg_name
from shorts.runner import StepError
from shorts.tts.base import TTSResult

ROOT = Path(__file__).resolve().parents[1]
BRIEF = ROOT / "tests" / "fixtures" / "brief_kitchen.json"
BG_BRIEF = ROOT / "tests" / "fixtures" / "brief_bg_prompts.json"

_spec = importlib.util.spec_from_file_location("make_short", ROOT / "tools" / "make_short.py")
make_short = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(make_short)


class FakeTTS:
    instances = []

    def __init__(self, *a, **k):
        type(self).instances.append(self)

    def health(self):
        return True

    def synthesize(self, text, voice, out_wav):
        Path(out_wav).write_bytes(b"RIFFfake")
        return TTSResult(path=Path(out_wav), duration_s=13.9, seconds_taken=1.2, engine="qwen")


def fake_words(narration):
    words = [{"w": " " + w, "s": k * 0.5, "e": k * 0.5 + 0.4} for k, w in enumerate(narration.split())]
    return [{"s": 0.0, "e": 13.9, "text": narration, "words": words}]


@pytest.fixture()
def env_factory(tmp_path, monkeypatch):
    def make(brief_path):
        narration = full_narration(load_brief(brief_path))
        calls = []

        def fake_run(cmd, cwd=None, log_path=None, timeout_s=600):
            cmd = [str(c) for c in cmd]
            calls.append(cmd)
            log = Path(log_path)
            log.parent.mkdir(parents=True, exist_ok=True)
            log.write_text("fake log\n", encoding="utf-8")
            if cmd[0] == "ffprobe":
                return "13.900000\n"
            if any("new-explainer.mjs" in c for c in cmd):
                film = Path(cmd[2])
                (film / "assets" / "audio").mkdir(parents=True, exist_ok=True)
                (film / "src").mkdir(parents=True, exist_ok=True)
                (film / "assets" / "audio" / "vo.mp3").write_bytes(b"fake")
                (film / "assets" / "kit.css").write_text(
                    ":root { --brand-ink: #3B2416; --brand-accent: #C9824B; --brand-accent-dark: #A0522D; }\n",
                    encoding="utf-8")
                (film / "film.json").write_text(json.dumps({
                    "name": "x",
                    "scenes": [["s01-hook", 7.3]],
                    "bgm": {"src": "b"},
                    "cues": [["s01-hook", 1.0, "pop"]],
                    "audio": [{"id": "vo", "src": "old", "dur": 1, "volume": 1, "track": 9}],
                    "overlays": [{"id": "m-kape", "track": 2, "z": 5}],
                }), encoding="utf-8")
                (film / "src" / "presenter-track.json").write_text(
                    json.dumps({"poses": [], "fx": [{"sprite": "q"}]}), encoding="utf-8")
                (film / "brand.json").write_text(
                    json.dumps({"name": "Somewhere Still", "accent": "#123456", "accent_dark": "#A0522D",
                                "ink": "#2B2A28"}), encoding="utf-8")
                return "scaffolded\n"
            if cmd[0] == "ffmpeg":
                if "-filter_complex" in cmd:
                    Path(cmd[-1]).write_bytes(b"MP4")
                    return "mixed\n"
                master = Path(cwd) / "assets" / "audio" / "vo-master.wav"
                master.parent.mkdir(parents=True, exist_ok=True)
                master.write_bytes(b"fake")
                return "ok\n"
            if "render" in cmd:
                target = Path(cwd) / cmd[cmd.index("-o") + 1]
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"MP4")
                return "rendered\n"
            return "ok\n"

        def fake_transcribe(wav_path, out_dir, lang="en", model="medium"):
            out_dir = Path(out_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            p = out_dir / "vo-words.json"
            p.write_text(json.dumps(fake_words(narration)), encoding="utf-8")
            return p

        monkeypatch.setattr(make_short, "VoiceboxTTS", FakeTTS)
        monkeypatch.setattr(make_short, "transcribe", fake_transcribe)
        monkeypatch.setattr(make_short, "run", fake_run)
        monkeypatch.setattr(make_short, "_find_tool", lambda name: name)
        monkeypatch.delenv("CF_ACCOUNT_ID", raising=False)
        monkeypatch.delenv("CF_API_TOKEN", raising=False)
        music_dir = tmp_path / "music"
        music_dir.mkdir(exist_ok=True)
        for n in ("calm-01.mp3", "calm-02.mp3", "cozy-01.mp3"):
            (music_dir / n).write_bytes(b"")
        return {"calls": calls, "jobs": tmp_path / "jobs", "music": music_dir, "brief": brief_path}
    return make


@pytest.fixture()
def env(env_factory):
    return env_factory(BRIEF)


def run_main(env, *extra):
    return Path(make_short.main(["--brief", str(env["brief"]), "--jobs-root", str(env["jobs"]),
                                 "--music-dir", str(env["music"]), *extra]))


def _read_scene_records(job):
    data = json.loads((job / "images.json").read_text(encoding="utf-8"))
    return data, {s["id"]: s for s in data["scenes"]}


def test_make_short_flow_writes_files_in_order(env):
    job = run_main(env, "--no-render")

    assert (job / "vo.wav").is_file()
    assert (job / "words.json").is_file()
    srt = (job / "captions.srt").read_text(encoding="utf-8")
    assert srt.startswith("1\n00:00:00,000 --> ")

    film = job / "film"
    data = json.loads((film / "film.json").read_text(encoding="utf-8"))
    assert data["scenes"] == [["s01-places", 4.95], ["s02-memories", 5.5], ["s03-back", 5.45]]
    assert data["audio"] == [
        {"id": "vo", "src": "assets/audio/vo-master.wav", "dur": 13.9, "volume": 1, "track": 9}]
    assert data["cues"] == []
    assert [o["id"] for o in data["overlays"]] == ["m-kape", "m-brand", "m-captions"]
    assert "bgm" not in data

    assert data["ground"] == "#1E1A2B"

    track = json.loads((film / "src" / "presenter-track.json").read_text(encoding="utf-8"))
    assert track["poses"] == [[0.0, "wave"], [4.85, "present"], [10.35, "point"]]
    assert track["fx"] == []
    assert track["mirror"] == []
    assert track["scale"] == 0.75

    html1 = (film / "compositions" / "s01-places.html").read_text(encoding="utf-8")
    assert "Places stay with us" in html1
    assert "assets/bg/bg-street.jpg" in html1
    assert 'data-composition-id="s01-places"' in html1
    html3 = (film / "compositions" / "s03-back.html").read_text(encoding="utf-8")
    assert "Let&#x27;s go back" in html3
    assert "assets/bg/bg-books.jpg" in html3
    caps = (film / "compositions" / "m-captions.html").read_text(encoding="utf-8")
    assert "#9E4A24" in caps
    assert "kitchen" in caps

    for name in ("bg-street", "bg-kitchen", "bg-books"):
        assert (film / "assets" / "bg" / f"{name}.jpg").is_file(), name
    for font in ("fraunces-600.woff2", "nunito-800.woff2"):
        assert (film / "assets" / "fonts" / font).is_file(), font
    brand = json.loads((film / "brand.json").read_text(encoding="utf-8"))
    assert brand["accent"] == "#9E4A24"
    assert brand["accent_dark"] == "#6E3218"
    css = (film / "assets" / "kit.css").read_text(encoding="utf-8")
    assert "--brand-accent: #9E4A24;" in css
    assert "--brand-accent-dark: #6E3218;" in css

    for name in ("a-brief", "b-images", "c-voice", "d-timing", "e-scene-times", "f-scaffold",
                 "g-fill-film", "h-build-presenter", "h-build-brand", "h-assemble", "i-check"):
        assert (job / "logs" / f"{name}.log").is_file(), name
    _data, by_id = _read_scene_records(job)
    assert [s["id"] for s in _data["scenes"]] == ["s01-places", "s02-memories", "s03-back"]
    assert by_id["s01-places"] == {"id": "s01-places", "bg": "bg-street", "source": "fallback"}
    assert by_id["s03-back"]["bg"] == "bg-books"

    kinds = [c[0] for c in env["calls"]]
    assert kinds == ["ffprobe", "node", "ffmpeg", sys.executable, sys.executable, sys.executable, "npx"]
    assert "new-explainer.mjs" in env["calls"][1][1]
    assert Path(env["calls"][3][1]).name == "build-presenter.py"
    assert Path(env["calls"][4][1]).name == "build-brand.py"
    assert Path(env["calls"][5][1]).name == "assemble.py"
    assert "check" in env["calls"][6]
    assert not any("render" in c for c in env["calls"][-1])


def test_presenter_track_mirror_is_empty(env):
    job = run_main(env, "--no-render")
    track = json.loads((job / "film" / "src" / "presenter-track.json").read_text(encoding="utf-8"))
    assert track["mirror"] == []


def test_make_short_render_mixes_music(env):
    job = run_main(env)

    assert (job / "kitchen-table-nomusic.mp4").is_file()
    assert (job / "kitchen-table.mp4").is_file()
    assert (job / "music.txt").read_text(encoding="utf-8").startswith("calm-")

    kinds = [c[0] for c in env["calls"]]
    assert kinds[-3:] == ["npx", "ffprobe", "ffmpeg"]
    assert "check" in env["calls"][-4]
    render_call = env["calls"][-3]
    assert "render" in render_call
    assert render_call[render_call.index("-o") + 1] == "renders/kitchen-table.mp4"
    assert "--fps" in render_call and "30" in render_call
    assert "--quality" in render_call and "draft" in render_call
    mix_call = env["calls"][-1]
    assert any("sidechaincompress" in c for c in mix_call)
    assert any("loudnorm=I=-30" in c for c in mix_call)


def test_make_short_no_music_copies_video(env):
    job = run_main(env, "--no-music")

    assert (job / "kitchen-table-nomusic.mp4").is_file()
    assert (job / "kitchen-table.mp4").is_file()
    assert not (job / "music.txt").exists()
    kinds = [c[0] for c in env["calls"]]
    assert kinds[-2:] == ["npx", "npx"]
    assert kinds.count("ffprobe") == 1
    assert not any("filter_complex" in c for c in env["calls"])


def test_existing_voice_is_reused_and_redo_voice_regenerates(env):
    before = len(FakeTTS.instances)
    run_main(env, "--no-render")
    assert len(FakeTTS.instances) == before + 1
    run_main(env, "--no-render")
    assert len(FakeTTS.instances) == before + 1
    run_main(env, "--no-render", "--redo-voice")
    assert len(FakeTTS.instances) == before + 2


def test_unhealthy_voicebox_fails_before_anything_else(tmp_path, monkeypatch):
    class SickTTS(FakeTTS):
        def health(self):
            return False

    def fail_transcribe(*a, **k):
        raise AssertionError("transcribe must not run")

    monkeypatch.setattr(make_short, "VoiceboxTTS", SickTTS)
    monkeypatch.setattr(make_short, "transcribe", fail_transcribe)
    with pytest.raises(StepError, match="Open the Voicebox app first"):
        make_short.main(["--brief", str(BRIEF), "--jobs-root", str(tmp_path / "jobs"), "--redo-voice"])


def _wire_mock_images(monkeypatch, handler, library):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(make_short, "LIBRARY", library)
    monkeypatch.setattr(shorts_images, "LIBRARY", library)
    monkeypatch.setattr(make_short, "get_bg", functools.partial(shorts_images.get_bg, client=client))
    return client


def _cloudflare_ok(request):
    return httpx.Response(200, json={"result": {"image": base64.b64encode(b"genjpg").decode()}})


def test_generated_backgrounds_flow_into_film(env_factory, monkeypatch, tmp_path):
    env = env_factory(BG_BRIEF)
    lib = tmp_path / "lib"
    http_calls = []

    def handler(request):
        http_calls.append(request)
        return _cloudflare_ok(request)

    _wire_mock_images(monkeypatch, handler, lib)
    monkeypatch.setenv("CF_ACCOUNT_ID", "acct-1")
    monkeypatch.setenv("CF_API_TOKEN", "tok-secret-1")
    job = run_main(env, "--no-render")

    assert len(http_calls) == 2
    for request in http_calls:
        assert request.headers["Authorization"] == "Bearer tok-secret-1"
        assert b"name=\"input_image_0\"" in request.read()
    data, by_id = _read_scene_records(job)
    assert data["model"] == shorts_images.MODEL
    gen1, gen2 = by_id["s01-rain"], by_id["s02-tea"]
    assert gen1["source"] == "generated" and gen1["bg"].startswith("gen-")
    assert gen2["source"] == "generated" and gen2["bg"].startswith("gen-")
    assert by_id["s03-books"] == {"id": "s03-books", "bg": "bg-books", "source": "fallback"}

    html1 = (job / "film" / "compositions" / "s01-rain.html").read_text(encoding="utf-8")
    assert f"assets/bg/{gen1['bg']}.jpg" in html1
    html2 = (job / "film" / "compositions" / "s02-tea.html").read_text(encoding="utf-8")
    assert f"assets/bg/{gen2['bg']}.jpg" in html2
    assert (job / "film" / "assets" / "bg" / f"{gen1['bg']}.jpg").read_bytes() == b"genjpg"
    assert (job / "film" / "assets" / "bg" / "bg-books.jpg").is_file()

    index = (lib / "index.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(index) == 2
    entry = json.loads(index[0])
    assert entry["file"] == f"{gen1['bg']}.jpg"
    assert entry["model"] == shorts_images.MODEL
    for log in (job / "logs").glob("*.log"):
        assert "tok-secret-1" not in log.read_text(encoding="utf-8"), log.name
    assert "tok-secret-1" not in (job / "images.json").read_text(encoding="utf-8")


def test_existing_library_pictures_are_reused_without_http(env_factory, monkeypatch, tmp_path):
    env = env_factory(BG_BRIEF)
    lib = tmp_path / "lib"
    lib.mkdir()
    brief = load_brief(BG_BRIEF)
    for scene in brief.scenes:
        if scene.bg_prompt:
            (lib / f"{bg_name(scene.bg_prompt)}.jpg").write_bytes(b"reused")

    def no_http(request):
        raise AssertionError("a library hit must not call the API")

    _wire_mock_images(monkeypatch, no_http, lib)
    monkeypatch.setenv("CF_ACCOUNT_ID", "acct-1")
    monkeypatch.setenv("CF_API_TOKEN", "tok-secret-1")
    job = run_main(env, "--no-render")

    _data, by_id = _read_scene_records(job)
    assert by_id["s01-rain"]["source"] == "reused"
    assert by_id["s01-rain"]["bg"] == bg_name(brief.scenes[0].bg_prompt)
    assert by_id["s02-tea"]["source"] == "reused"
    assert by_id["s03-books"]["source"] == "fallback"
    assert (job / "film" / "assets" / "bg" / f"{by_id['s01-rain']['bg']}.jpg").read_bytes() == b"reused"
    assert not (lib / "index.jsonl").exists()


def test_image_failure_falls_back_and_job_still_succeeds(env_factory, monkeypatch, tmp_path):
    env = env_factory(BG_BRIEF)
    lib = tmp_path / "lib"
    http_calls = []

    def failing(request):
        http_calls.append(1)
        return httpx.Response(500, json={"errors": [{"message": "neurons exhausted"}]})

    _wire_mock_images(monkeypatch, failing, lib)
    monkeypatch.setenv("CF_ACCOUNT_ID", "acct-1")
    monkeypatch.setenv("CF_API_TOKEN", "tok-secret-1")
    job = run_main(env, "--no-render")

    assert len(http_calls) == 4
    _data, by_id = _read_scene_records(job)
    assert by_id["s01-rain"] == {"id": "s01-rain", "bg": "bg-books", "source": "fallback"}
    assert by_id["s02-tea"] == {"id": "s02-tea", "bg": "bg-kitchen", "source": "fallback"}
    html1 = (job / "film" / "compositions" / "s01-rain.html").read_text(encoding="utf-8")
    assert "assets/bg/bg-books.jpg" in html1
    assert (job / "film" / "assets" / "bg" / "bg-books.jpg").is_file()
    log = (job / "logs" / "b-images.log").read_text(encoding="utf-8")
    assert "neurons exhausted" in log
    for log_path in (job / "logs").glob("*.log"):
        assert "tok-secret-1" not in log_path.read_text(encoding="utf-8"), log_path.name


def test_missing_env_falls_back_without_http(env_factory, monkeypatch, tmp_path):
    env = env_factory(BG_BRIEF)
    lib = tmp_path / "lib"

    def no_http(request):
        raise AssertionError("no HTTP call expected without credentials")

    _wire_mock_images(monkeypatch, no_http, lib)
    job = run_main(env, "--no-render")

    _data, by_id = _read_scene_records(job)
    assert all(s["source"] == "fallback" for s in by_id.values())
    assert by_id["s01-rain"]["bg"] == "bg-books"
    log = (job / "logs" / "b-images.log").read_text(encoding="utf-8")
    assert "CF_ACCOUNT_ID" in log


def test_no_images_flag_skips_generation(env_factory, monkeypatch, tmp_path):
    env = env_factory(BG_BRIEF)
    lib = tmp_path / "lib"

    def no_http(request):
        raise AssertionError("no HTTP call expected with --no-images")

    _wire_mock_images(monkeypatch, no_http, lib)
    monkeypatch.setenv("CF_ACCOUNT_ID", "acct-1")
    monkeypatch.setenv("CF_API_TOKEN", "tok-secret-1")
    job = run_main(env, "--no-render", "--no-images")

    _data, by_id = _read_scene_records(job)
    assert all(s["source"] == "fallback" for s in by_id.values())
    assert by_id["s01-rain"]["bg"] == "bg-books"
    assert not (lib / "index.jsonl").exists()

"""Fast make_short tests with fakes: no Voicebox, no Whisper, no node, no render."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from shorts.brief import full_narration, load_brief
from shorts.runner import StepError
from shorts.tts.base import TTSResult

ROOT = Path(__file__).resolve().parents[1]
BRIEF = ROOT / "tests" / "fixtures" / "brief_kitchen.json"

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
def env(tmp_path, monkeypatch):
    narration = full_narration(load_brief(BRIEF))
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
                json.dumps({"name": "Somewhere Still", "accent": "#123456", "ink": "#2B2A28"}), encoding="utf-8")
            return "scaffolded\n"
        if cmd[0] == "ffmpeg":
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
    return {"calls": calls, "jobs": tmp_path / "jobs"}


def run_main(env, *extra):
    return Path(make_short.main(["--brief", str(BRIEF), "--jobs-root", str(env["jobs"]), *extra]))


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

    track = json.loads((film / "src" / "presenter-track.json").read_text(encoding="utf-8"))
    assert track["poses"] == [[0.0, "wave"], [0.0, "wave"], [4.85, "present"], [10.35, "point"]]
    assert track["fx"] == []

    html1 = (film / "compositions" / "s01-places.html").read_text(encoding="utf-8")
    assert "Places stay with us" in html1
    assert 'data-composition-id="s01-places"' in html1
    html3 = (film / "compositions" / "s03-back.html").read_text(encoding="utf-8")
    assert "Let&#x27;s go back" in html3
    caps = (film / "compositions" / "m-captions.html").read_text(encoding="utf-8")
    assert "#123456" in caps
    assert "kitchen" in caps

    for name in ("a-brief", "b-voice", "c-timing", "d-scene-times", "e-scaffold",
                 "f-fill-film", "g-build-presenter", "g-build-brand", "g-assemble", "h-check"):
        assert (job / "logs" / f"{name}.log").is_file(), name

    kinds = [c[0] for c in env["calls"]]
    assert kinds == ["ffprobe", "node", "ffmpeg", sys.executable, sys.executable, sys.executable, "npx"]
    assert "new-explainer.mjs" in env["calls"][1][1]
    assert Path(env["calls"][3][1]).name == "build-presenter.py"
    assert Path(env["calls"][4][1]).name == "build-brand.py"
    assert Path(env["calls"][5][1]).name == "assemble.py"
    assert "check" in env["calls"][6]
    assert not any("render" in c for c in env["calls"][-1])


def test_make_short_render_copies_result(env):
    job = run_main(env)

    assert (job / "kitchen-table.mp4").is_file()
    kinds = [c[0] for c in env["calls"]]
    assert kinds[-2:] == ["npx", "npx"]
    assert "check" in env["calls"][-2]
    assert "render" in env["calls"][-1]
    assert env["calls"][-1][env["calls"][-1].index("-o") + 1] == "renders/kitchen-table.mp4"
    assert "--fps" in env["calls"][-1] and "30" in env["calls"][-1]
    assert "--quality" in env["calls"][-1] and "draft" in env["calls"][-1]


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

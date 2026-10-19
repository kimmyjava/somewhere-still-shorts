"""One command from brief.json to a rendered vertical Short (needs Voicebox, Whisper, node).

usage: C:/shorts/venv/Scripts/python tools/make_short.py --brief brief.json [--jobs-root C:/shorts/jobs]
       [--fps 30] [--quality draft] [--no-render] [--redo-voice]
Per-step logs: <jobs-root>/<slug>/logs/<step>.log. Final video: <jobs-root>/<slug>/<slug>.mp4.
"""
import argparse
import json
import shutil
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from shorts.brief import full_narration, load_brief
from shorts.captions import caption_composition, make_chunks, write_srt
from shorts.film import film_updates, headline_scene_html, presenter_poses, scene_times
from shorts.runner import StepError, run
from shorts.timing import align, load_whisper_words, transcribe
from shorts.tts.base import VoiceSpec
from shorts.tts.voicebox import VoiceboxTTS

DEFAULT_PROFILE_ID = "ac52122c-5b02-4c66-b00d-ba5bb47b65f7"
KAPE = REPO / "vendor" / "kape-explainer" / "skills" / "kape-explainer"
ENGINE = REPO / "vendor" / "kape-explainer" / "skills" / "spatial-film"


def _log_step(logs: Path, name: str, text: str) -> None:
    (logs / f"{name}.log").write_text(text, encoding="utf-8")


def _timed(label: str, fn):
    t0 = time.monotonic()
    value = fn()
    print(f"{label}: {time.monotonic() - t0:.1f}s", flush=True)
    return value


def main(argv=None):
    t_all = time.monotonic()
    ap = argparse.ArgumentParser(description="Build a Somewhere Still Short from a brief.")
    ap.add_argument("--brief", required=True, help="path to the brief JSON")
    ap.add_argument("--jobs-root", default="C:/shorts/jobs", help="folder for all job output")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--quality", default="draft")
    ap.add_argument("--no-render", action="store_true", help="stop after the hyperframes check")
    ap.add_argument("--redo-voice", action="store_true", help="synthesize even if job/vo.wav exists")
    args = ap.parse_args(argv)

    brief = _timed("a-brief", lambda: load_brief(args.brief))
    job = Path(args.jobs_root) / brief.slug
    job.mkdir(parents=True, exist_ok=True)
    logs = job / "logs"
    logs.mkdir(exist_ok=True)
    _log_step(logs, "a-brief", f"slug={brief.slug}\ntitle={brief.title}\nscenes={len(brief.scenes)}")

    vo = job / "vo.wav"

    def voice():
        if vo.exists() and not args.redo_voice:
            return "reused existing vo.wav"
        tts = VoiceboxTTS()
        if not tts.health():
            raise StepError("Open the Voicebox app first")
        result = tts.synthesize(full_narration(brief), VoiceSpec(profile_id=DEFAULT_PROFILE_ID), vo)
        return f"synthesized {result.duration_s:.2f}s in {result.seconds_taken:.1f}s ({result.engine})"

    _log_step(logs, "b-voice", _timed("b-voice", voice))

    def timing():
        flat = load_whisper_words(transcribe(vo, job / "timing"))
        timed_words = align(full_narration(brief), flat)
        chunks = make_chunks(timed_words)
        (job / "words.json").write_text(
            json.dumps([asdict(w) for w in timed_words], ensure_ascii=False), encoding="utf-8")
        write_srt(chunks, job / "captions.srt")
        probe = run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(vo)],
            cwd=job, log_path=logs / "c-ffprobe.log")
        voice_dur = float(probe.strip().splitlines()[-1])
        _log_step(logs, "c-timing", f"words={len(timed_words)} chunks={len(chunks)} voice={voice_dur:.2f}s")
        return timed_words, chunks, voice_dur

    timed_words, chunks, voice_dur = _timed("c-timing", timing)

    def plan():
        times = scene_times(brief, timed_words)
        _log_step(logs, "d-scene-times", "\n".join(f"{sid} {s:.2f} +{d:.2f}" for sid, s, d in times))
        return times

    times = _timed("d-scene-times", plan)

    film = job / "film"

    def scaffold():
        if film.exists():
            shutil.rmtree(film)
        run(["node", str(KAPE / "scripts" / "new-explainer.mjs"), str(film), "--name", brief.slug,
             "--format", "9x16", "--mp3", str(vo)],
            cwd=job, log_path=logs / "e-scaffold.log", timeout_s=900)

    _timed("e-scaffold", scaffold)

    def fill():
        run(["ffmpeg", "-v", "error", "-y", "-i", "assets/audio/vo.mp3",
             "-af", "loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000", "-ar", "48000",
             "assets/audio/vo-master.wav"],
            cwd=film, log_path=logs / "f-vo-master.log", timeout_s=900)
        film_json = film / "film.json"
        data = json.loads(film_json.read_text(encoding="utf-8"))
        data.update(film_updates(times, voice_dur))
        data.pop("bgm", None)
        film_json.write_text(json.dumps(data, indent=1), encoding="utf-8")
        track_path = film / "src" / "presenter-track.json"
        track = json.loads(track_path.read_text(encoding="utf-8"))
        track["poses"] = presenter_poses(times, brief)
        track["fx"] = []
        track["mirror"] = []
        track_path.write_text(json.dumps(track, indent=1), encoding="utf-8")
        brand = json.loads((film / "brand.json").read_text(encoding="utf-8"))
        accent = brand.get("accent", "#C9824B")
        comp = film / "compositions"
        comp.mkdir(exist_ok=True)
        for scene in brief.scenes:
            dur = next(d for sid, _s, d in times if sid == scene.id)
            (comp / f"{scene.id}.html").write_text(
                headline_scene_html(scene.id, dur, scene.headline), encoding="utf-8")
        total = sum(d for _sid, _s, d in times)
        (comp / "m-captions.html").write_text(
            caption_composition(chunks, total, accent=accent), encoding="utf-8")
        return f"scenes={len(brief.scenes)} chunks={len(chunks)} voice={voice_dur:.2f}s total={total:.2f}s accent={accent}"

    _log_step(logs, "f-fill-film", _timed("f-fill-film", fill))

    def builders():
        for name, script in (
            ("g-build-presenter", ENGINE / "scripts" / "build-presenter.py"),
            ("g-build-brand", KAPE / "scripts" / "build-brand.py"),
            ("g-assemble", ENGINE / "scripts" / "assemble.py"),
        ):
            run([sys.executable, str(script)], cwd=film, log_path=logs / f"{name}.log", timeout_s=900)
        return "build-presenter, build-brand, assemble"

    _timed("g-builders", builders)

    def check():
        run(["npx", "--yes", "hyperframes@0.8.117", "check"],
            cwd=film, log_path=logs / "h-check.log", timeout_s=900)
        return "check passed"

    _timed("h-check", check)

    if args.no_render:
        print(f"done (no render): {job} (total {time.monotonic() - t_all:.1f}s)")
        return job

    def render():
        run(["npx", "--yes", "hyperframes@0.8.117", "render", "--fps", str(args.fps),
             "--quality", args.quality, "-o", f"renders/{brief.slug}.mp4"],
            cwd=film, log_path=logs / "i-render.log", timeout_s=3600)
        final = job / f"{brief.slug}.mp4"
        shutil.copy2(film / "renders" / f"{brief.slug}.mp4", final)
        return final

    final = _timed("i-render", render)
    print(f"done: {final} (total {time.monotonic() - t_all:.1f}s)")
    return job


if __name__ == "__main__":
    main()

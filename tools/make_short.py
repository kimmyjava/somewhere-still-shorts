"""One command from brief.json to a rendered vertical Short (needs Voicebox, Whisper, node).

usage: python tools/make_short.py --brief brief.json [--jobs-root <dir>] [--fps 30]
       [--quality draft] [--no-images] [--no-render] [--redo-voice]
       [--redo-scene SCENE_ID ...]
Per-step logs: <jobs-root>/<slug>/logs/<step>.log. Final video: <jobs-root>/<slug>/<slug>.mp4.
Defaults come from SHORTS_DATA_ROOT (jobs/, music/ under it) so the same command runs on the
laptop (C:/shorts) and the server (/workspace/shorts-data). AI backgrounds need CF_ACCOUNT_ID and
CF_API_TOKEN in the environment; without them (or with --no-images, or when a picture fails)
scenes fall back to their fixed bg and the job still runs.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from shorts.brief import full_narration, load_brief
from shorts.captions import make_chunks, write_srt
from shorts.film import film_updates, presenter_poses, scene_times
from shorts.images import (ImageError, LIBRARY, MODEL, USE_STYLE_REF, bg_name, data_root, get_bg,
                           library_ref)
from shorts.look import PALETTE, cozy_captions_html, cozy_scene_html
from shorts.music import mix_command, pick_track
from shorts.runner import StepError, run
from shorts.timing import align, fallback_timed_words, load_whisper_words, transcribe
from shorts.tts.base import VoiceSpec
from shorts.tts.join import join_parts
from shorts.tts.voicebox import VoiceboxTTS, env_base_url, env_engine, env_model_size

DEFAULT_PROFILE_ID = "ac52122c-5b02-4c66-b00d-ba5bb47b65f7"
SEED = 42
KAPE = REPO / "vendor" / "kape-explainer" / "skills" / "kape-explainer"
ENGINE = REPO / "vendor" / "kape-explainer" / "skills" / "spatial-film"


def voice_profile_id() -> str:
    """The Voicebox profile to speak with (cloned "Kim" by default; server presets override)."""
    return os.environ.get("SHORTS_VOICE_PROFILE_ID", "").strip() or DEFAULT_PROFILE_ID


def _log_step(logs: Path, name: str, text: str) -> None:
    (logs / f"{name}.log").write_text(text, encoding="utf-8")


def _find_tool(name: str) -> str:
    found = shutil.which(name)
    if not found:
        raise StepError(f"{name} not found in PATH - install ffmpeg first (winget install Gyan.FFmpeg)")
    return found


def _timed(label: str, fn):
    t0 = time.monotonic()
    value = fn()
    print(f"{label}: {time.monotonic() - t0:.1f}s", flush=True)
    return value


def main(argv=None):
    t_all = time.monotonic()
    ap = argparse.ArgumentParser(description="Build a Somewhere Still Short from a brief.")
    ap.add_argument("--brief", required=True, help="path to the brief JSON")
    ap.add_argument("--jobs-root", default=str(data_root() / "jobs"), help="folder for all job output")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--quality", default="draft")
    ap.add_argument("--no-images", action="store_true",
                    help="skip AI backgrounds; use the fixed bg library only")
    ap.add_argument("--no-render", action="store_true", help="stop after the hyperframes check")
    ap.add_argument("--redo-voice", action="store_true",
                    help="regenerate every scene's voice part even if cached")
    ap.add_argument("--redo-scene", action="append", default=[], metavar="SCENE_ID",
                    dest="redo_scenes",
                    help="regenerate one scene's voice part with seed + 1 (a different take); repeatable")
    ap.add_argument("--music-dir", default=str(data_root() / "music"), help="folder with <mood>-NN.mp3 tracks")
    ap.add_argument("--no-music", action="store_true", help="skip the music mix")
    args = ap.parse_args(argv)

    brief = _timed("a-brief", lambda: load_brief(args.brief))
    job = Path(args.jobs_root) / brief.slug
    job.mkdir(parents=True, exist_ok=True)
    logs = job / "logs"
    logs.mkdir(exist_ok=True)
    _log_step(logs, "a-brief", f"slug={brief.slug}\ntitle={brief.title}\nstyle={brief.style}\n"
                               f"scenes={len(brief.scenes)}")

    def images():
        account = os.environ.get("CF_ACCOUNT_ID", "")
        token = os.environ.get("CF_API_TOKEN", "")
        picks: dict[str, dict] = {}
        notes: list[str] = []
        env_warned = False
        for index, scene in enumerate(brief.scenes):
            name = scene.bg or "bg-books"
            source = "fallback"
            record = {"bg": name, "style": brief.style, "source": source}
            if scene.bg_prompt and not args.no_images:
                if not (account and token):
                    if not env_warned:
                        note = "CF_ACCOUNT_ID / CF_API_TOKEN not set - using fixed backgrounds"
                        print(f"WARNING: {note}", flush=True)
                        notes.append(note)
                        env_warned = True
                else:
                    hash_ref = library_ref(scene.bg_prompt, index)
                    try:
                        reused = (LIBRARY / f"{bg_name(scene.bg_prompt, hash_ref, brief.style)}.jpg").is_file()
                        name = get_bg(scene.bg_prompt, account, token, index=index, style=brief.style)
                        record = {"bg": name, "style": brief.style, "source": "reused" if reused else "generated",
                                  "ref": hash_ref if USE_STYLE_REF else None}
                    except ImageError as exc:
                        note = f"scene {scene.id}: background failed ({exc}) - using {name}"
                        print(f"WARNING: {note}", flush=True)
                        notes.append(note)
            picks[scene.id] = record
        (job / "images.json").write_text(json.dumps(
            {"model": MODEL, "scenes": [dict(id=sid, **picks[sid]) for sid in picks]}, indent=1),
            encoding="utf-8")
        notes.extend(f"{sid} {picks[sid]['bg']} {picks[sid]['source']}" for sid in picks)
        _log_step(logs, "b-images", "\n".join(notes))
        return picks

    picks: dict[str, dict] = _timed("b-images", images)

    vo = job / "vo.wav"

    def voice():
        voice_dir = job / "voice"
        voice_dir.mkdir(exist_ok=True)
        redo = set(args.redo_scenes)
        unknown = sorted(redo - {scene.id for scene in brief.scenes})
        if unknown:
            raise StepError(f"--redo-scene: no scene(s) named {', '.join(unknown)}")
        parts = [voice_dir / f"{scene.id}.wav" for scene in brief.scenes]
        if args.redo_voice:
            for part in parts:
                part.unlink(missing_ok=True)
        for sid in redo:
            (voice_dir / f"{sid}.wav").unlink(missing_ok=True)
        todo = [scene for scene, part in zip(brief.scenes, parts) if not part.exists()]
        notes = []
        if todo:
            tts = VoiceboxTTS()
            if not tts.health():
                raise StepError(f"Voicebox is not healthy at {env_base_url()} - start it first")
            engine = env_engine()
            model_size = env_model_size()
            profile = voice_profile_id()
            for scene in todo:
                seed = SEED + 1 if scene.id in redo else SEED
                result = tts.synthesize(
                    scene.narration,
                    VoiceSpec(profile_id=profile, seed=seed, engine=engine, model_size=model_size),
                    voice_dir / f"{scene.id}.wav")
                notes.append(f"{scene.id} {result.duration_s:.2f}s seed={seed}")
        seconds = join_parts(parts, vo)
        detail = "; ".join(notes) if notes else "reused all cached parts"
        return f"joined {len(parts)} parts into {seconds:.2f}s ({detail})"

    _log_step(logs, "c-voice", _timed("c-voice", voice))

    def timing():
        alignment = "whisper"
        try:
            flat = load_whisper_words(transcribe(vo, job / "timing"))
            timed_words = align(full_narration(brief), flat)
        except Exception as exc:
            alignment = "fallback"
            note = f"word alignment failed ({exc}) - using proportional timing from the voice parts"
            print(f"WARNING: {note}", flush=True)
            timed_words = fallback_timed_words(brief, job / "voice")
        (job / "timing" / "alignment.json").write_text(
            json.dumps({"alignment": alignment}), encoding="utf-8")
        chunks = make_chunks(timed_words)
        (job / "words.json").write_text(
            json.dumps([asdict(w) for w in timed_words], ensure_ascii=False), encoding="utf-8")
        write_srt(chunks, job / "captions.srt")
        probe = run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(vo)],
            cwd=job, log_path=logs / "d-ffprobe.log")
        voice_dur = float(probe.strip().splitlines()[-1])
        _log_step(logs, "d-timing",
                  f"alignment={alignment} words={len(timed_words)} chunks={len(chunks)} "
                  f"voice={voice_dur:.2f}s")
        return timed_words, chunks, voice_dur

    timed_words, chunks, voice_dur = _timed("d-timing", timing)

    def plan():
        times = scene_times(brief, timed_words)
        _log_step(logs, "e-scene-times", "\n".join(f"{sid} {s:.2f} +{d:.2f}" for sid, s, d in times))
        return times

    times = _timed("e-scene-times", plan)

    film = job / "film"

    def scaffold():
        if film.exists():
            shutil.rmtree(film)
        run(["node", str(KAPE / "scripts" / "new-explainer.mjs"), str(film), "--name", brief.slug,
             "--format", "9x16", "--mp3", str(vo)],
            cwd=job, log_path=logs / "f-scaffold.log", timeout_s=900)

    _timed("f-scaffold", scaffold)

    def sfx():
        """KAPE's assemble.py exits when a film.json SFX file is missing. Our films ship cues=[]
        (no SFX is ever mixed), so a silent placeholder keeps the builder happy without audio impact."""
        sfx_dir = film / "assets" / "audio" / "sfx"
        film_json = json.loads((film / "film.json").read_text(encoding="utf-8"))
        needed = sorted({file_name for file_name, _vol in film_json.get("sfx", {}).values()})
        made = 0
        for name in needed:
            path = sfx_dir / name
            if path.is_file():
                continue
            sfx_dir.mkdir(parents=True, exist_ok=True)
            run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono",
                 "-t", "0.3", "-c:a", "libmp3lame", "-q:a", "9", str(path)],
                cwd=film, log_path=logs / "f-sfx.log", timeout_s=120)
            made += 1
        return f"{made} silent placeholder(s) for missing sfx"

    _timed("f-sfx", sfx)

    def fill():
        run(["ffmpeg", "-v", "error", "-y", "-i", "assets/audio/vo.mp3",
             "-af", "loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000", "-ar", "48000",
             "assets/audio/vo-master.wav"],
            cwd=film, log_path=logs / "g-vo-master.log", timeout_s=900)
        bg_dir = film / "assets" / "bg"
        bg_dir.mkdir(parents=True, exist_ok=True)
        for name in sorted({picks[s.id]["bg"] for s in brief.scenes}):
            src = REPO / "assets" / "bg" / f"{name}.jpg"
            if not src.is_file():
                src = LIBRARY / f"{name}.jpg"
            shutil.copy2(src, bg_dir / f"{name}.jpg")
        fonts_dir = film / "assets" / "fonts"
        fonts_dir.mkdir(parents=True, exist_ok=True)
        for font in ("fraunces-600.woff2", "nunito-800.woff2"):
            shutil.copy2(REPO / "assets" / "fonts" / font, fonts_dir / font)
        film_json = film / "film.json"
        data = json.loads(film_json.read_text(encoding="utf-8"))
        data.update(film_updates(times, voice_dur))
        data["ground"] = PALETTE["night"]
        data.pop("bgm", None)
        film_json.write_text(json.dumps(data, indent=1), encoding="utf-8")
        track_path = film / "src" / "presenter-track.json"
        track = json.loads(track_path.read_text(encoding="utf-8"))
        track["scale"] = 0.75
        track["poses"] = presenter_poses(times, brief)
        track["fx"] = []
        track["mirror"] = []
        track_path.write_text(json.dumps(track, indent=1), encoding="utf-8")
        brand_path = film / "brand.json"
        brand = json.loads(brand_path.read_text(encoding="utf-8"))
        brand["accent"] = PALETTE["accent"]
        brand["accent_dark"] = "#6E3218"
        brand_path.write_text(json.dumps(brand, indent=1), encoding="utf-8")
        kit = film / "assets" / "kit.css"
        css = kit.read_text(encoding="utf-8")
        css = re.sub(r"--brand-accent:\s*[^;]+;", f"--brand-accent: {PALETTE['accent']};", css)
        css = re.sub(r"--brand-accent-dark:\s*[^;]+;", "--brand-accent-dark: #6E3218;", css)
        kit.write_text(css, encoding="utf-8")
        comp = film / "compositions"
        comp.mkdir(exist_ok=True)
        zoom_start = 1.06 if brief.style == "storybook" else 1.0
        for scene in brief.scenes:
            dur = next(d for sid, _s, d in times if sid == scene.id)
            (comp / f"{scene.id}.html").write_text(
                cozy_scene_html(scene.id, dur, scene.headline, picks[scene.id]["bg"],
                                zoom_start=zoom_start), encoding="utf-8")
        total = sum(d for _sid, _s, d in times)
        (comp / "m-captions.html").write_text(
            cozy_captions_html(chunks, total), encoding="utf-8")
        return f"scenes={len(brief.scenes)} chunks={len(chunks)} voice={voice_dur:.2f}s total={total:.2f}s accent={PALETTE['accent']}"

    _log_step(logs, "g-fill-film", _timed("g-fill-film", fill))

    def builders():
        for name, script in (
            ("h-build-presenter", ENGINE / "scripts" / "build-presenter.py"),
            ("h-build-brand", KAPE / "scripts" / "build-brand.py"),
            ("h-assemble", ENGINE / "scripts" / "assemble.py"),
        ):
            run([sys.executable, str(script)], cwd=film, log_path=logs / f"{name}.log", timeout_s=900)
        return "build-presenter, build-brand, assemble"

    _timed("h-builders", builders)

    def check():
        run(["npx", "--yes", "hyperframes@0.8.117", "check"],
            cwd=film, log_path=logs / "i-check.log", timeout_s=900)
        return "check passed"

    _timed("i-check", check)

    if args.no_render:
        print(f"done (no render): {job} (total {time.monotonic() - t_all:.1f}s)")
        return job

    def render():
        run(["npx", "--yes", "hyperframes@0.8.117", "render", "--fps", str(args.fps),
             "--quality", args.quality, "-o", f"renders/{brief.slug}.mp4"],
            cwd=film, log_path=logs / "j-render.log", timeout_s=3600)
        no_music = job / f"{brief.slug}-nomusic.mp4"
        shutil.move(str(film / "renders" / f"{brief.slug}.mp4"), str(no_music))
        return no_music

    no_music_video = _timed("j-render", render)

    def music():
        final = job / f"{brief.slug}.mp4"
        if args.no_music:
            note = "--no-music given - using the video without music"
            print(f"WARNING: {note}", flush=True)
            _log_step(logs, "k-music", note)
            shutil.copy2(no_music_video, final)
            return final
        track = pick_track(args.music_dir, brief.music, brief.slug)
        if track is None:
            note = f"no music in {args.music_dir} for mood {brief.music!r} (or calm) - using the video without music"
            print(f"WARNING: {note}", flush=True)
            _log_step(logs, "k-music", note)
            shutil.copy2(no_music_video, final)
            return final
        probe = run([_find_tool("ffprobe"), "-v", "error", "-show_entries", "format=duration",
                     "-of", "default=noprint_wrappers=1:nokey=1", str(no_music_video)],
                    cwd=job, log_path=logs / "k-ffprobe.log")
        duration = float(probe.strip().splitlines()[-1])
        mix = mix_command(no_music_video, track, final, duration)
        mix[0] = _find_tool("ffmpeg")
        run(mix, cwd=job, log_path=logs / "k-mix.log", timeout_s=1800)
        (job / "music.txt").write_text(track.name, encoding="utf-8")
        _log_step(logs, "k-music", f"track={track.name} duration={duration:.2f}s")
        return final

    final = _timed("k-music", music)
    print(f"done: {final} (total {time.monotonic() - t_all:.1f}s)")
    return job


if __name__ == "__main__":
    main()

r"""Milestone 1 vertical demo: KAPE 9:16 film with 2 template scenes, the mascot, the brand logo and word-timed captions,
written from DATA with no LLM in the loop. Proof of concept only - not the production scene writer.

usage (run from a film folder made by new-explainer.mjs --format 9x16):
    python m1_vertical_demo.py --kape <...\skills\kape-explainer> --engine <...\skills\spatial-film>
then render:  npx --yes hyperframes@0.8.117 render --fps 30 --quality draft -o renders/demo.mp4
- s01-hook: "headline" scene type   - s02-point: "steps" scene type (cards land on cue words)
- m-captions: word-timed caption overlay (2-4 word chunks, active word highlighted)
"""
import json, sys
from html import escape
from pathlib import Path

FONT = """@font-face { font-family: 'Poppins'; font-weight: 500; src: url('assets/fonts/poppins-500.woff2') format('woff2'); }
@font-face { font-family: 'Poppins'; font-weight: 700; src: url('assets/fonts/poppins-700.woff2') format('woff2'); }"""


def scene(sid, dur, body, script):
    return f"""<template>
<link rel="stylesheet" href="assets/kit.css">
<style>
{FONT}
#root {{ position: absolute; inset: 0; width: 1080px; height: 1920px; overflow: hidden; font-family: 'Poppins', sans-serif; }}
.{sid}-layer {{ position: absolute; inset: 0; transform-style: preserve-3d; }}
</style>
<div id="root" data-composition-id="{sid}" data-width="1080" data-height="1920">
  <div id="{sid}-ground" class="clip kit-ground" data-start="0" data-duration="{dur}" data-track-index="0"></div>
  <div id="{sid}-stage" class="clip" data-start="0" data-duration="{dur}" data-track-index="1" style="position:absolute; inset:0; perspective:1866px;">
    <div id="{sid}-drift" class="{sid}-layer"><div id="{sid}-cam" class="{sid}-layer"><div class="kit-floor"></div></div></div>
  </div>
{body}
  <div id="{sid}-grain" class="clip kit-grain" data-start="0" data-duration="{dur}" data-track-index="9"></div>
</div>
<script>
(function () {{
  var D = {dur}; var tl = gsap.timeline({{ paused: true }});
  tl.fromTo('#{sid}-drift', {{ scale: 1 }}, {{ scale: 1.02, duration: D / 2, ease: 'sine.inOut' }}, 0);
  tl.fromTo('#{sid}-drift', {{ scale: 1.02 }}, {{ scale: 1, duration: D / 2, ease: 'sine.inOut', immediateRender: false }}, D / 2);
{script}
  window.__timelines = window.__timelines || {{}}; window.__timelines['{sid}'] = tl;
}})();
</script>
</template>
"""


def headline(sid, dur, d):
    body = (f'  <div id="{sid}-k" class="kit-kicker" style="position:absolute; left:0; right:0; top:230px; text-align:center;">{escape(d["kicker"])}</div>\n'
            f'  <div id="{sid}-h" class="kit-label" style="position:absolute; left:0; right:0; top:300px; text-align:center;">{escape(d["headline"])}</div>\n'
            f'  <div id="{sid}-t" class="kit-tile wh" style="position:absolute; left:50%; top:640px; transform:translateX(-50%);">{escape(d["tile"])}</div>')
    js = (f"  tl.fromTo('#{sid}-k', {{opacity:0, y:30}}, {{opacity:1, y:0, duration:.5, ease:'expo.out'}}, {d['at'][0]});\n"
          f"  tl.fromTo('#{sid}-h', {{opacity:0, y:40}}, {{opacity:1, y:0, duration:.6, ease:'expo.out'}}, {d['at'][1]});\n"
          f"  tl.fromTo('#{sid}-t', {{opacity:0, scale:.6}}, {{opacity:1, scale:1, duration:.7, ease:'back.out(1.6)'}}, {d['at'][2]});\n"
          f"  tl.to(['#{sid}-k','#{sid}-h','#{sid}-t'], {{opacity:0, duration:.35, ease:'power2.in'}}, D - .45);")
    return scene(sid, dur, body, js)


def steps(sid, dur, d):
    cards = "".join(
        f'  <div id="{sid}-c{i}" class="kit-card" style="position:absolute; left:120px; right:120px; top:{500 + i * 170}px; '
        f'padding:26px 36px; font:700 48px Poppins; color:var(--ink);">{i + 1}. {escape(t)}</div>\n'
        for i, t in enumerate(d["steps"]))
    body = f'  <div id="{sid}-h" class="kit-label sm" style="position:absolute; left:0; right:0; top:260px; text-align:center;">{escape(d["headline"])}</div>\n' + cards
    js = f"  tl.fromTo('#{sid}-h', {{opacity:0, y:40}}, {{opacity:1, y:0, duration:.6, ease:'expo.out'}}, 0.1);\n"
    js += "".join(f"  tl.fromTo('#{sid}-c{i}', {{opacity:0, x:120}}, {{opacity:1, x:0, duration:.55, ease:'back.out(1.4)'}}, {t});\n"
                  for i, t in enumerate(d["at"]))
    js += f"  tl.to('#{sid} [id^={sid}-]', {{opacity:0, duration:.35, ease:'power2.in'}}, D - .45);"
    return scene(sid, dur, body, js)


def captions(words, total, per=3, ink='#0B1E3F', accent='#0F9F8F'):
    """Chunk words into groups of <= per words (break on pauses > .35s); highlight the spoken word."""
    flat = [w for s in words for w in s["words"]]
    chunks, cur = [], []
    for w in flat:
        if cur and (len(cur) >= per or w["s"] - cur[-1]["e"] > 0.35):
            chunks.append(cur); cur = []
        cur.append(w)
    if cur: chunks.append(cur)
    html, js = [], []
    for ci, ch in enumerate(chunks):
        spans = "".join(f'<span id="cw{ci}-{wi}">{escape(w["w"].strip())}</span> ' for wi, w in enumerate(ch))
        html.append(f'<div id="cc{ci}" class="cap">{spans.strip()}</div>')
        end = chunks[ci + 1][0]["s"] if ci + 1 < len(chunks) else min(ch[-1]["e"] + 0.4, total)
        js.append(f"tl.set('#cc{ci}', {{opacity:1}}, {ch[0]['s']}); tl.set('#cc{ci}', {{opacity:0}}, {round(end, 3)});")
        for wi, w in enumerate(ch):
            js.append(f"tl.set('#cw{ci}-{wi}', {{color:'{accent}'}}, {w['s']}); tl.set('#cw{ci}-{wi}', {{color:'{ink}'}}, {w['e']});")
    return f"""<template>
<link rel="stylesheet" href="assets/kit.css">
<style>
{FONT}
#root {{ position: absolute; inset: 0; width: 1080px; height: 1920px; overflow: hidden; }}
/* caption band: right of the presenter (x 500-1000), above the Shorts UI (y < 1500) */
.cap {{ position: absolute; left: 500px; right: 80px; top: 1180px; opacity: 0; text-align: center;
  font: 700 60px/1.15 'Poppins', sans-serif; color: {ink}; background: rgba(255,255,255,.9);
  border-radius: 24px; padding: 14px 22px; }}
</style>
<div id="root" data-composition-id="m-captions" data-width="1080" data-height="1920">
{chr(10).join(html)}
</div>
<script>
(function () {{ var tl = gsap.timeline({{ paused: true }});
{chr(10).join(js)}
tl.set({{}}, {{}}, {total});
window.__timelines = window.__timelines || {{}}; window.__timelines['m-captions'] = tl; }})();
</script>
</template>
"""


import argparse, subprocess


def run(*cmd):
    print(">", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--kape", required=True); ap.add_argument("--engine", required=True)
    a = ap.parse_args()
    if not Path("film.json").exists():
        sys.exit("run this from the film folder (film.json not found)")
    py = sys.executable
    # 1) timing: 2 scenes, 8.8 s, no music, 2 sound effects
    film = json.loads(Path("film.json").read_text(encoding="utf-8"))
    film["scenes"] = [["s01-hook", 4.0], ["s02-point", 4.8]]
    film["audio"][0]["dur"] = 8.0
    film.pop("bgm", None)
    film["cues"] = [["s01-hook", 0.5, "pop"], ["s02-point", 0.4, "whoosh"]]
    if not any(o["id"] == "m-captions" for o in film["overlays"]):
        film["overlays"].append({"id": "m-captions", "track": 4, "z": 7})
    Path("film.json").write_text(json.dumps(film, indent=1), encoding="utf-8")
    t = json.loads(Path("src/presenter-track.json").read_text(encoding="utf-8"))
    t["poses"] = [[0.0, "wave"], [2.2, "idle"], [4.2, "point"], [6.4, "thumbs-up"]]
    t["fx"] = []
    Path("src/presenter-track.json").write_text(json.dumps(t, indent=1), encoding="utf-8")
    # 2) fake word timings (M3 replaces these with real ones from transcribe.py)
    ws = "Why do tiny habits win? Because small steps are easy to repeat. Start tiny, stack it, track it.".split()
    cur, rows = 0.3, []
    for w in ws:
        rows.append({"w": " " + w, "s": round(cur, 2), "e": round(cur + 0.32, 2)})
        cur += 0.75 if w.endswith(("?", ".", ",")) else 0.42
    words = [{"s": 0.3, "e": round(cur, 2), "text": " ".join(ws), "words": rows}]
    Path("src/timing").mkdir(parents=True, exist_ok=True)
    Path("src/timing/demo-words.json").write_text(json.dumps(words), encoding="utf-8")
    # 3) voice master (loudnorm only - master-audio.py needs a music bed)
    run("ffmpeg", "-v", "error", "-y", "-i", "assets/audio/vo.mp3", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000",
        "-ar", "48000", "assets/audio/vo-master.wav")
    # 4) scenes + captions from data
    total = sum(s[1] for s in film["scenes"])
    accent = json.loads(Path("brand.json").read_text(encoding="utf-8"))["accent"]
    Path("compositions/s01-hook.html").write_text(headline("s01-hook", 4.0, {
        "kicker": "Somewhere Still", "headline": "Why tiny habits win", "tile": "1%", "at": [0.2, 0.6, 1.4]}), encoding="utf-8")
    Path("compositions/s02-point.html").write_text(steps("s02-point", 4.8, {
        "headline": "Three small steps", "steps": ["Start tiny", "Stack it", "Track it"], "at": [0.5, 1.5, 2.5]}), encoding="utf-8")
    Path("compositions/m-captions.html").write_text(captions(words, total, accent=accent), encoding="utf-8")
    # 5) KAPE's own builders: mascot overlay, logo overlay, index.html
    run(py, Path(a.engine) / "scripts" / "build-presenter.py")
    run(py, Path(a.kape) / "scripts" / "build-brand.py")
    run(py, Path(a.engine) / "scripts" / "assemble.py")
    print("\nnext: npx --yes hyperframes@0.8.117 check   then   npx --yes hyperframes@0.8.117 render --fps 30 --quality draft -o renders/demo.mp4")

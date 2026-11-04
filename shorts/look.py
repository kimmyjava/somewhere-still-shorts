"""Somewhere Still cozy look v1 - production copy of docs/reference/cozy.py (tested with HyperFrames 0.8.117).

cozy_scene_html(scene_id, dur, headline, bg, zoom_start=1.0) -> one full-screen scene: illustrated
                                                      background with a slow Ken Burns push from
                                                      zoom_start to zoom_start + 0.08, warm vignette,
                                                      floating light motes, headline.
cozy_captions_html(chunks, total)                 -> word-timed captions overlay "m-captions" from CaptionChunk.
Assets expected in the film folder:
  assets/bg/<name>.jpg                (vertical illustrations, about 9:16)
  assets/fonts/fraunces-600.woff2     (headline, SIL OFL)
  assets/fonts/nunito-800.woff2       (captions, SIL OFL)
Colours (all text contrast-checked >= 4.5:1 on its own background):
  cream text #FFF4E6 on dark gradient; caption ink #3B2416 on #FFF6EA; caption accent #9E4A24.
"""
from html import escape

PALETTE = {"cream": "#FFF4E6", "ink": "#3B2416", "paper": "#FFF6EA", "accent": "#9E4A24", "night": "#1E1A2B"}

FONTS = """@font-face { font-family: 'Fraunces'; font-weight: 600; src: url('assets/fonts/fraunces-600.woff2') format('woff2'); }
@font-face { font-family: 'Nunito'; font-weight: 800; src: url('assets/fonts/nunito-800.woff2') format('woff2'); }"""

# fixed (not random) positions for the floating light motes: (x %, y %, size px, drift seconds offset)
MOTES = [(12, 30, 10, 0.0), (78, 22, 7, 0.7), (64, 48, 9, 1.3), (30, 58, 6, 0.4), (88, 64, 8, 1.9),
         (46, 36, 5, 2.4), (20, 74, 7, 1.1), (70, 80, 6, 0.2)]


def cozy_scene_html(sid, dur, headline, bg, zoom_start=1.0):
    push = round(zoom_start + 0.08, 2)
    motes = "".join(
        f'  <div id="{sid}-m{i}" class="{sid}-mote" style="left:{x}%; top:{y}%; width:{s}px; height:{s}px;"></div>\n'
        for i, (x, y, s, _) in enumerate(MOTES))
    js_motes = "".join(
        f"  tl.fromTo('#{sid}-m{i}', {{y:0, opacity:0}}, {{y:-120, opacity:0.85, duration:D*0.5, ease:'sine.inOut'}}, {round(o % 1.5, 2)});\n"
        f"  tl.to('#{sid}-m{i}', {{y:-220, opacity:0, duration:D*0.5, ease:'sine.inOut'}}, {round(o % 1.5, 2)} + D*0.5);\n"
        for i, (_, _, _, o) in enumerate(MOTES))
    return f"""<template>
<style>
{FONTS}
#root {{ position: absolute; inset: 0; width: 1080px; height: 1920px; overflow: hidden; background: {PALETTE['night']}; }}
#{sid}-bg {{ position: absolute; inset: 0; width: 1080px; height: 1920px; object-fit: cover; transform-origin: 50% 60%; }}
#{sid}-shade {{ position: absolute; inset: 0;
  background: linear-gradient(to bottom, rgba(20,14,10,.70) 0%, rgba(20,14,10,.15) 26%, rgba(20,14,10,0) 45%, rgba(20,14,10,.10) 70%, rgba(20,14,10,.55) 100%),
              radial-gradient(ellipse at 50% 45%, rgba(0,0,0,0) 55%, rgba(20,10,5,.45) 100%); }}
.{sid}-mote {{ position: absolute; border-radius: 50%; background: radial-gradient(circle, rgba(255,226,170,.95) 0%, rgba(255,210,140,0) 70%); opacity: 0; }}
#{sid}-h {{ position: absolute; left: 80px; right: 80px; top: 210px; text-align: center; opacity: 0;
  font: 600 78px/1.12 'Fraunces', serif; color: {PALETTE['cream']}; letter-spacing: -0.01em;
  text-shadow: 0 3px 18px rgba(20,10,5,.55); }}
#{sid}-veil {{ position: absolute; inset: 0; background: {PALETTE['night']}; }}
</style>
<div id="root" data-composition-id="{sid}" data-width="1080" data-height="1920">
  <img id="{sid}-bg" class="clip" src="assets/bg/{bg}.jpg" alt="" data-start="0" data-duration="{dur}" data-track-index="0">
  <div id="{sid}-shade" class="clip" data-start="0" data-duration="{dur}" data-track-index="1"></div>
{motes}  <div id="{sid}-h" class="clip" data-start="0" data-duration="{dur}" data-track-index="3">{escape(headline)}</div>
  <div id="{sid}-veil" class="clip" data-start="0" data-duration="{dur}" data-track-index="4"></div>
</div>
<script>
(function () {{
  var D = {dur}; var tl = gsap.timeline({{ paused: true }});
  // slow Ken Burns push across the whole scene
  tl.fromTo('#{sid}-bg', {{scale:{zoom_start}, x:0}}, {{scale:{push}, x:-18, duration:D, ease:'none'}}, 0);
  // soft fade in from night, soft fade out to night (scene-to-scene dip)
  tl.fromTo('#{sid}-veil', {{opacity:1}}, {{opacity:0, duration:0.6, ease:'sine.out'}}, 0);
  tl.fromTo('#{sid}-veil', {{opacity:0}}, {{opacity:1, duration:0.45, ease:'sine.in', immediateRender:false}}, D - 0.45);
  // headline drifts up gently
  tl.fromTo('#{sid}-h', {{opacity:0, y:24}}, {{opacity:1, y:0, duration:0.9, ease:'power2.out'}}, 0.35);
{js_motes}  window.__timelines = window.__timelines || {{}}; window.__timelines['{sid}'] = tl;
}})();
</script>
</template>
"""


def cozy_captions_html(chunks, total, top=1250, left=470, right=70):
    """chunks: list of CaptionChunk (TimedWord .text/.start/.end). Shows each chunk from its start to the next chunk; spoken word in accent.
    Windows never overlap: chunks are ordered by start, every chunk hides before the next one shows
    (each stays on screen at least 0.2 s - longer than the 0.18 s entrance tween, so the hide can
    never land inside it and stick the caption visible; the next chunk's start is shifted if needed),
    and the last chunk hides at min(last word end + 0.5, total)."""
    ordered = sorted(chunks, key=lambda c: c.start)
    starts = [c.start for c in ordered]
    html, js = [], []
    for ci, ch in enumerate(ordered):
        if ci + 1 < len(ordered):
            hide = starts[ci + 1]
            if hide < starts[ci] + 0.2:
                hide = starts[ci] + 0.2
                starts[ci + 1] = hide
        else:
            hide = min(ch.words[-1].end + 0.5, total)
        spans = " ".join(f'<span id="cw{ci}-{wi}">{escape(w.text)}</span>' for wi, w in enumerate(ch.words))
        html.append(f'<div id="cc{ci}" class="cap">{spans}</div>')
        js.append(f"tl.fromTo('#cc{ci}', {{opacity:0, y:10}}, {{opacity:1, y:0, duration:0.18, ease:'power2.out'}}, {round(starts[ci], 3)});"
                  f" tl.set('#cc{ci}', {{opacity:0}}, {round(hide, 3)});")
        for wi, w in enumerate(ch.words):
            js.append(f"tl.set('#cw{ci}-{wi}', {{color:'{PALETTE['accent']}'}}, {round(w.start, 3)}); tl.set('#cw{ci}-{wi}', {{color:'{PALETTE['ink']}'}}, {round(w.end, 3)});")
    return f"""<template>
<style>
{FONTS}
#root {{ position: absolute; inset: 0; width: 1080px; height: 1920px; overflow: hidden; }}
.cap {{ position: absolute; left: {left}px; right: {right}px; top: {top}px; opacity: 0; text-align: center;
  font: 800 56px/1.18 'Nunito', sans-serif; color: {PALETTE['ink']}; background: rgba(255,246,234,.94);
  border-radius: 34px; padding: 18px 28px; box-shadow: 0 8px 24px rgba(20,10,5,.30); }}
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

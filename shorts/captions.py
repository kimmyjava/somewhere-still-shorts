"""Captions: TimedWords -> chunks -> SRT and the m-captions HyperFrames overlay."""
from dataclasses import dataclass
from html import escape
from pathlib import Path

from shorts.timing import TimedWord


@dataclass
class CaptionChunk:
    words: list[TimedWord]
    start: float
    end: float


def make_chunks(timed_words: list[TimedWord], max_words: int = 3, pause: float = 0.35) -> list[CaptionChunk]:
    groups: list[list[TimedWord]] = []
    cur: list[TimedWord] = []
    for w in timed_words:
        if cur and (len(cur) >= max_words or w.start - cur[-1].end > pause):
            groups.append(cur)
            cur = []
        cur.append(w)
        if cur[-1].text.rstrip().endswith((".", "?", "!")):
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)

    chunks: list[CaptionChunk] = []
    for i, g in enumerate(groups):
        end = groups[i + 1][0].start if i + 1 < len(groups) else g[-1].end + 0.4
        chunks.append(CaptionChunk(words=g, start=g[0].start, end=end))
    return chunks


def _srt_time(t: float) -> str:
    ms = max(0, int(round(t * 1000)))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(chunks: list[CaptionChunk], path: Path) -> Path:
    blocks = [
        f"{i}\n{_srt_time(c.start)} --> {_srt_time(c.end)}\n{' '.join(w.text for w in c.words)}"
        for i, c in enumerate(chunks, 1)
    ]
    text = "\n\n".join(blocks) + ("\n" if blocks else "")
    Path(path).write_text(text, encoding="utf-8")
    return Path(path)


def caption_composition(
    chunks: list[CaptionChunk],
    total_seconds: float,
    ink: str = "#2B2A28",
    accent: str = "#C9824B",
    font: str = "Poppins",
    top: int = 1180,
    left: int = 500,
    right: int = 80,
) -> str:
    total = round(float(total_seconds), 3)
    divs: list[str] = []
    js: list[str] = []
    for ci, c in enumerate(chunks):
        spans = " ".join(f'<span id="cw{ci}-{wi}">{escape(w.text)}</span>' for wi, w in enumerate(c.words))
        divs.append(f'  <div id="cc{ci}" class="cap">{spans}</div>')
        show_end = min(round(c.end, 3), total)
        js.append(
            f"  tl.set('#cc{ci}', {{opacity: 1}}, {round(c.start, 3)});"
            f" tl.set('#cc{ci}', {{opacity: 0}}, {show_end});")
        for wi, w in enumerate(c.words):
            js.append(
                f"  tl.set('#cw{ci}-{wi}', {{color: '{accent}'}}, {round(w.start, 3)});"
                f" tl.set('#cw{ci}-{wi}', {{color: '{ink}'}}, {round(w.end, 3)});")
    return f"""<template>
<link rel="stylesheet" href="assets/kit.css">
<style>
#root {{ position: absolute; inset: 0; width: 1080px; height: 1920px; overflow: hidden; }}
.cap {{ position: absolute; left: {left}px; right: {right}px; top: {top}px; opacity: 0; text-align: center;
  font: 700 60px/1.15 '{font}', sans-serif; color: {ink}; background: rgba(255,255,255,.9);
  border-radius: 24px; padding: 14px 22px; }}
</style>
<div id="root" data-composition-id="m-captions" data-width="1080" data-height="1920">
{chr(10).join(divs)}
</div>
<script>
(function () {{ var tl = gsap.timeline({{ paused: true }});
{chr(10).join(js)}
tl.set({{}}, {{}}, {total});
window.__timelines = window.__timelines || {{}}; window.__timelines['m-captions'] = tl; }})();
</script>
</template>
"""

"""Film plan: brief + timed words -> scene times, film.json updates, poses, placeholder scene HTML."""
from html import escape

from shorts.brief import Brief


def scene_times(brief: Brief, timed_words, end_pad: float = 2.0) -> list[tuple[str, float, float]]:
    if not timed_words:
        raise ValueError("timed_words is empty - run the timing step first")
    counts = [len(s.narration.split()) for s in brief.scenes]
    total_words = sum(counts)
    if total_words > len(timed_words):
        raise ValueError(f"brief needs {total_words} timed words, got {len(timed_words)}")

    spans: list[list] = []
    idx = 0
    for n in counts:
        spans.append(list(timed_words[idx:idx + n]))
        idx += n

    bounds = [0.0]
    for prev, cur in zip(spans, spans[1:]):
        bounds.append((prev[-1].end + cur[0].start) / 2)
    bounds.append(spans[-1][-1].end + end_pad)

    rounded = [round(b, 2) for b in bounds]
    return [
        (scene.id, rounded[i], round(rounded[i + 1] - rounded[i], 2))
        for i, scene in enumerate(brief.scenes)
    ]


def film_updates(scene_times: list[tuple[str, float, float]], voice_dur: float) -> dict:
    return {
        "scenes": [[sid, dur] for sid, _start, dur in scene_times],
        "audio": [{"id": "vo", "src": "assets/audio/vo-master.wav", "dur": voice_dur, "volume": 1, "track": 9}],
        "cues": [],
        "overlays": [
            {"id": "m-kape", "track": 2, "z": 5},
            {"id": "m-brand", "track": 3, "z": 6},
            {"id": "m-captions", "track": 4, "z": 7},
        ],
    }


def presenter_poses(scene_times: list[tuple[str, float, float]], brief: Brief) -> list[list]:
    poses = [[0.0, "wave"]]
    for (sid, start, _dur), scene in zip(scene_times, brief.scenes):
        poses.append([max(0.0, round(start - 0.1, 2)), scene.pose])
    return poses


def headline_scene_html(scene_id: str, dur: float, headline: str, kicker: str = "Somewhere Still") -> str:
    d = round(float(dur), 3)
    out_at = round(max(0.0, d - 0.45), 3)
    return f"""<template>
<style>
#root {{ position: absolute; inset: 0; width: 1080px; height: 1920px; overflow: hidden;
  background: #F6F2EA; font-family: 'Poppins', sans-serif; }}
#{scene_id}-k {{ position: absolute; left: 0; right: 0; top: 230px; text-align: center; opacity: 0;
  font: 500 40px/1.2 'Poppins', sans-serif; color: #7A4A1E; }}
#{scene_id}-h {{ position: absolute; left: 120px; right: 120px; top: 300px; text-align: center; opacity: 0;
  font: 700 88px/1.1 'Poppins', sans-serif; color: #2B2A28; }}
</style>
<div id="root" data-composition-id="{scene_id}" data-width="1080" data-height="1920">
  <div id="{scene_id}-clip" class="clip" data-start="0" data-duration="{d}" data-track-index="1">
    <div id="{scene_id}-k">{escape(kicker)}</div>
    <div id="{scene_id}-h">{escape(headline)}</div>
  </div>
</div>
<script>
(function () {{
  var tl = gsap.timeline({{ paused: true }});
  tl.fromTo('#{scene_id}-k', {{opacity: 0, y: 30}}, {{opacity: 1, y: 0, duration: 0.5, ease: 'expo.out'}}, 0.2);
  tl.fromTo('#{scene_id}-h', {{opacity: 0, y: 40}}, {{opacity: 1, y: 0, duration: 0.6, ease: 'expo.out'}}, 0.6);
  tl.to(['#{scene_id}-k', '#{scene_id}-h'], {{opacity: 0, duration: 0.35, ease: 'power2.in'}}, {out_at});
  window.__timelines = window.__timelines || {{}}; window.__timelines['{scene_id}'] = tl;
}})();
</script>
</template>
"""

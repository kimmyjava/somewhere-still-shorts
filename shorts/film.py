"""Film plan: brief + timed words -> scene times, film.json updates, presenter poses."""
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
    poses: list[list] = []
    last = -1.0
    for (_sid, start, _dur), scene in zip(scene_times, brief.scenes):
        t = max(0.0, round(start - 0.1, 2))
        if poses and t <= last:
            t = round(last + 0.01, 2)
        poses.append([t, scene.pose])
        last = t
    return poses

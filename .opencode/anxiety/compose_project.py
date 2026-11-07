"""Compose project.json for the anxiety short from cached voice parts.

Pipeline: join parts -> whisper.cpp timings -> script alignment -> captions +
shots -> project.json. Output 1080x1920; design plane 1280 x 2275.56
(renderer's fixed 1280-unit width; captions center at x=640, caption band is
the bottom 110 design units).
Assets are pre-cropped to ink; assets/manifest.json gives each file's content
box, so place() positions drawings by their true size.
Deterministic; re-run overwrites.
"""
import json
import sys
import wave
from pathlib import Path

sys.path.insert(0, "/workspace/video-generation")
from shorts.timing import align, transcribe  # noqa: E402
from shorts.tts.join import join_parts  # noqa: E402

from narration import PARTS, VOICE_DIR  # noqa: E402

HERE = Path(__file__).resolve().parent
A = "assets"
LEAD = 0.15
TAIL = 1.0
PAUSE = 0.35
RED, GREEN, NAVY = "#EC4338", "#3F9142", "#2B3A67"


def wav_seconds(p: Path) -> float:
    with wave.open(str(p), "rb") as w:
        return w.getnframes() / w.getframerate()


def find_word(words, text):
    key = "".join(c for c in text.lower() if c.isalpha())
    for i, w in enumerate(words):
        if "".join(c for c in w.text.lower() if c.isalpha()) == key:
            return i
    raise KeyError(f"anchor word not found: {text}")


def group_cues(words, texts):
    cues = []
    cur = []
    for i, (w, txt) in enumerate(zip(words, texts)):
        cur.append((w, txt))
        gap = (words[i + 1].start - w.end) if i + 1 < len(words) else 0
        chars = sum(len(t) + 1 for _, t in cur)
        if (txt and txt[-1] in ",.:!?") or chars > 52 or (gap and gap > 0.6):
            cues.append((cur[0][0].start, w.end, " ".join(t.strip() for _, t in cur)))
            cur = []
    if cur:
        cues.append((cur[0][0].start, cur[-1][0].end, " ".join(t.strip() for _, t in cur)))
    return [(round(s + LEAD, 3), round(max(e, s + 0.35) + LEAD, 3), t) for s, e, t in cues]


def main() -> None:
    parts_paths = [VOICE_DIR / f"{pid}.wav" for pid, _ in PARTS]
    missing = [p.name for p in parts_paths if not p.exists()]
    if missing:
        raise SystemExit(f"missing voice parts: {missing}")
    vo = HERE / "vo.wav"
    dur_join = join_parts(parts_paths, vo, pause_s=PAUSE)

    durs = [wav_seconds(p) for p in parts_paths]
    offs = []
    t = 0.0
    for d in durs:
        offs.append(t)
        t += d + PAUSE

    words_file = transcribe(vo, HERE)
    data = json.loads(words_file.read_text())
    whisper_words = [w for seg in data for w in seg["words"]]

    part_words = []
    for k, (pid, text) in enumerate(PARTS):
        lo, hi = offs[k] - 0.30, offs[k] + durs[k] + 0.30
        chunk = [w for w in whisper_words if lo <= w["s"] <= hi]
        part_words.append(align(text, chunk))

    all_words, all_texts = [], []
    for (pid, text), tw in zip(PARTS, part_words):
        all_words.extend(tw)
        all_texts.extend(text.split())
    for i in range(len(all_words) - 1):
        nxt = all_words[i + 1].start
        if all_words[i].end > nxt:
            all_words[i].end = max(nxt - 0.01, all_words[i].start + 0.05)

    joined = []
    for s, e, t in group_cues(all_words, all_texts):
        if joined and (s < joined[-1][1] or s - joined[-1][0] < 0.25) and len(joined[-1][2]) + len(t) + 1 <= 52:
            joined[-1][1] = max(joined[-1][1], e)
            joined[-1][2] += " " + t
        else:
            joined.append([s, e, t])
    caps = []
    for i, (s, e, t) in enumerate(joined):
        hold_end = max(e, s + 0.3)
        if i + 1 < len(joined):
            hold_end = min(hold_end, round(joined[i + 1][0], 3) - 0.02)
        caps.append({"start": round(max(0.05, s), 3), "end": round(max(hold_end, s + 0.1), 3), "text": t})
    captions = caps

    def a(k, word):
        return part_words[k][find_word(part_words[k], word)].start

    anchors = {
        "suddenly": a(0, "suddenly"), "disaster": a(0, "disaster"),
        "alarm": a(1, "alarm"), "protective": a(2, "protective"),
        "replaying": a(3, "replaying"), "racing": a(3, "racing"),
        "avoiding": a(3, "avoiding"), "tiny": a(3, "tiny"),
        "second": a(4, "second"), "name": a(5, "name"), "fact": a(5, "fact"),
        "ground": a(6, "ground"), "five": a(6, "five"), "breath": a(7, "breath"),
        "remember": a(8, "remember"), "professional": a(9, "professional"),
        "tell": a(9, "tell"), "drop": a(9, "drop"),
    }

    MAN = json.loads((HERE / A / "manifest.json").read_text())
    L = LEAD
    shots, sfx = [], []
    cursor = 0.0

    def S(start, end, layers):
        nonlocal cursor
        start = round(start + L, 3)
        if start < cursor or start - cursor <= 0.5:
            start = cursor
        end = round(end + L, 3)
        if end <= start:
            raise SystemExit(f"empty shot: {start}->{end}")
        shots.append({"start": start, "end": end, "layers": layers})
        cursor = end
        return start

    def place(name, cx, cy, w=None, h=None):
        mw, mh = MAN[name]["w"], MAN[name]["h"]
        if w is None:
            w = round(h * mw / mh)
        if h is None:
            h = round(w * mh / mw)
        return {"type": "image", "path": f"{A}/{name}", "w": w,
                "x": round(cx - w / 2), "y": round(cy - h / 2)}

    def keys(seq):
        return [{"t": round(t_, 3), **props} for t_, props in seq]

    def txt(text, cx, y, size, bold=False, color=None, frm=None, to=None, seq=None):
        layer = {"type": "text", "text": text, "x": round(cx), "y": round(y), "size": size}
        if bold:
            layer["bold"] = True
        if color:
            layer["color"] = color
        if frm is not None:
            layer["from"] = round(frm, 3)
        if to is not None:
            layer["to"] = round(to, 3)
        if seq:
            layer["keys"] = keys(seq)
        return layer

    def img(name, cx, cy, w=None, h=None, frm=None, to=None, seq=None):
        layer = place(name, cx, cy, w, h)
        if frm is not None:
            layer["from"] = round(frm, 3)
        if to is not None:
            layer["to"] = round(to, 3)
        if seq:
            layer["keys"] = keys(seq)
        return layer

    def hero(name, cx, cy, h, frm=None, seq=None):
        return img(f"{name}.png", cx, cy, h=h, frm=frm, seq=seq)

    # ---- S1a: hook - phone slides in ---------------------------------------
    p1_end = offs[1]
    S(-LEAD, anchors["suddenly"], [
        img("phone-notification.png", 640, 640, w=680,
            seq=[(0, {"y": 1300, "alpha": 0}), (0.45, {"y": 640, "alpha": 1})]),
        txt("Can we talk tomorrow?", 450, 900, 42, bold=True,
            seq=[(0.55, {"alpha": 0}), (0.85, {"alpha": 1})]),
    ])
    sfx.append({"time": round(0.55 + L, 3), "kind": "pop", "gain": 0.05})

    # ---- S1b: bed -> shock + thought stack ----------------------------------
    S(anchors["suddenly"], p1_end, [
        hero("hero-lying", 560, 940, h=210, seq=[(0, {"alpha": 1}), (0.1, {"alpha": 1}), (0.12, {"alpha": 0})]),
        hero("hero-lying-shock", 560, 940, h=210, seq=[(0.12, {"alpha": 0}), (0.18, {"alpha": 1})]),
        img("bed-blanket.png", 387, 1180, w=900),
        txt("YOUR BRAIN:", 100, 300, 56, bold=True, frm=0.15),
        txt("Am I in trouble?", 130, 420, 40, bold=True, frm=0.4),
        txt("Did I do something wrong?", 130, 510, 40, bold=True, frm=0.75),
        txt("What if something bad happens?", 130, 600, 40, bold=True, frm=1.0),
        txt("WHAT DID I DO?!", 130, 700, 58, bold=True, color=RED, frm=1.25),
    ])

    # ---- S2a: alarm guard at the console ------------------------------------
    p2_end = offs[2] + durs[2]
    S(offs[1] + 0.15, anchors["alarm"] - 0.05, [
        txt("YOUR ALARM SYSTEM", 360, 180, 60, bold=True, frm=0.35),
        img("alarm-panel.png", 640, 1780, w=1050),
        hero("guard-panic", 640, 1180, h=730, seq=[(0, {"alpha": 0, "y": 1120}), (0.5, {"alpha": 1, "y": 1180})]),
        img("alarm-light-off.png", 1020, 380, w=260),
    ])

    # ---- S2b: alarm blinks, guard jitters ------------------------------------
    S(anchors["alarm"], p2_end, [
        txt("JUST DOING ITS JOB", 420, 180, 50, bold=True, color=GREEN,
            frm=max(0, anchors["protective"] - anchors["alarm"] - 0.15)),
        img("alarm-panel.png", 640, 1780, w=1050),
        hero("guard-panic", 640, 1180, h=730,
             seq=[(0, {"x": 640}), (0.22, {"x": 662}), (0.44, {"x": 640}), (0.66, {"x": 660}), (0.88, {"x": 640})]),
        img("alarm-light-on.png", 1020, 380, w=300,
            seq=[(0, {"alpha": 1}), (0.18, {"alpha": 0}), (0.36, {"alpha": 1}), (0.54, {"alpha": 0}),
                 (0.72, {"alpha": 1}), (0.9, {"alpha": 0}), (1.08, {"alpha": 1})]),
    ])
    sfx.append({"time": round(anchors["alarm"] + L, 3), "kind": "tap", "gain": 0.05})
    sfx.append({"time": round(anchors["alarm"] + L + 0.36, 3), "kind": "tap", "gain": 0.04})

    # ---- S3: four situations grid (quadrants) --------------------------------
    p3_start = offs[3]
    cells = [
        ("hero-overthink.png", "1. OVERTHINKING", 320, 880),
        ("hero-chest.png", "2. IN THE BODY", 960, 880),
        ("hero-avoid.png", "3. AVOIDING", 320, 1720),
        ("tiny-problem.png", "4. WORST CASE", 960, 1720),
    ]
    grid_layers = []
    for i, (im, label, cx, cy) in enumerate(cells):
        grid_layers.append(img(im, cx, cy - 60, h=430, frm=i * 0.35,
                               seq=[(i * 0.35, {"alpha": 0, "y": cy - 110}), (i * 0.35 + 0.3, {"alpha": 1, "y": cy - 60})]))
        grid_layers.append(txt(label, cx - 180, cy + 220, 42, bold=True, frm=i * 0.35 + 0.2))
    t_m = max(0.1, anchors["tiny"] - anchors["replaying"] - 0.15)
    grid_layers.append(img("monster-question.png", 960, 1660, h=520, frm=t_m,
                           seq=[(t_m, {"alpha": 0}), (t_m + 0.25, {"alpha": 1})]))
    grid_layers[6]["to"] = round(t_m, 3)  # hide tiny-problem once the monster is up
    S(p3_start + 0.1, anchors["second"] - 0.25, grid_layers)
    sfx.append({"time": round(anchors["tiny"] + L, 3), "kind": "pop", "gain": 0.06})

    # ---- S3b: interactive pause ---------------------------------------------
    p4_end = offs[5]
    S(anchors["second"] - 0.25, p4_end + 1.2, [
        img("bubble-empty.png", 640, 800, w=1000, seq=[(0, {"alpha": 0}), (0.35, {"alpha": 1})]),
        txt("WHICH ONE SOUNDS", 360, 730, 58, bold=True, frm=0.45),
        txt("MOST FAMILIAR?", 360, 810, 58, bold=True, frm=0.7),
        txt("(take a second)", 360, 905, 42, frm=0.9),
    ])

    # ---- S4a: technique 1 - name it ------------------------------------------
    p5_start = offs[5]
    t1_end = anchors["ground"] - 0.1
    n1 = anchors["name"] - p5_start
    f1 = anchors["fact"] - p5_start
    S(p5_start + 0.1, t1_end, [
        hero("hero-explain", 300, 1580, h=860, seq=[(0, {"alpha": 0, "x": 360}), (0.4, {"alpha": 1, "x": 300})]),
        img("bubble-empty.png", 700, 560, h=430, seq=[(0.5, {"alpha": 0}), (0.8, {"alpha": 1})]),
        txt('"SOMETHING TERRIBLE', 420, 510, 38, frm=0.9, to=n1 + 0.6),
        txt('WILL HAPPEN!"', 420, 575, 38, frm=1.05, to=n1 + 0.6),
        txt("a feeling is not", 420, 510, 40, bold=True, frm=max(0.1, f1 - 0.9)),
        txt("automatically a fact.", 420, 575, 40, bold=True, color=GREEN, frm=max(0.1, f1 - 0.6)),
        txt("NAME IT.", 300, 250, 68, bold=True, color=GREEN, frm=max(0.1, n1 - 0.1)),
    ])
    sfx.append({"time": round(p5_start + L + 0.2, 3), "kind": "chime", "gain": 0.04})

    # ---- S4b: technique 2 - ground (5-4-3) -----------------------------------
    t2_start = t1_end + 0.1
    t2_end = anchors["breath"] - 0.15
    f5 = anchors["five"] - t2_start
    t2_layers = [txt("GROUND YOURSELF.", 320, 200, 60, bold=True, color=NAVY)]
    for i, (im, label, cy) in enumerate([
            ("icon-eye.png", "5 things you can SEE", 700),
            ("icon-hand.png", "4 things you can FEEL", 1250),
            ("icon-ear.png", "3 things you can HEAR", 1780)]):
        f_i = max(0.1, f5 - 0.2 + i * 0.55)
        t2_layers.append(img(im, 400, cy, h=280, frm=f_i,
                             seq=[(f_i, {"alpha": 0, "y": cy + 50}), (f_i + 0.3, {"alpha": 1, "y": cy})]))
        t2_layers.append(txt(label, 620, cy - 40, 48, bold=True, frm=f_i + 0.35))
    S(t2_start, t2_end, t2_layers)

    # ---- S4c: technique 3 - breathe -------------------------------------------
    t3_start = t2_end + 0.1
    t3_end = offs[8]
    t3_dur = max(4.0, t3_end - t3_start)
    ring_seq = []
    for j, frac in enumerate([0.04, 0.32, 0.58, 0.84]):
        tt = round(frac * (t3_dur - 0.3), 3)
        ring_seq.append((tt, {"w": 560 if j % 2 else 360}))
    S(t3_start, t3_end, [
        txt("SLOW DOWN.", 320, 200, 60, bold=True, color=GREEN),
        img("breath-ring.png", 420, 1160, w=360, seq=ring_seq),
        hero("hero-breathe", 420, 1580, h=920),
    ])

    # ---- S5: callback / resolve ----------------------------------------------
    p8_start = offs[8]
    s5 = S(p8_start + 0.1, offs[9] + 0.3, [
        hero("hero-sit-calm", 380, 1420, h=760, seq=[(0, {"alpha": 0}), (0.4, {"alpha": 1})]),
    ])
    r = max(0.05, anchors["remember"] - (s5 - L))
    shots[-1]["layers"] += [
        txt("the same message.", 780, 500, 40, bold=True, frm=r, to=r + 1.4),
        img("phone-notification.png", 900, 860, h=520,
            seq=[(r + 1.4, {"alpha": 0}), (r + 1.7, {"alpha": 1})]),
        txt("don't believe", 200, 330, 52, bold=True, frm=r + 2.2),
        txt("every scary story.", 200, 400, 52, bold=True, color=RED, frm=r + 2.5),
    ]

    # ---- S5b: disclaimer beat --------------------------------------------------
    d_start = offs[9] + 0.3
    dp = anchors["professional"] - d_start
    S(d_start, anchors["tell"] - 0.15, [
        hero("hero-explain", 380, 1560, h=880),
        txt("IF ANXIETY RUNS YOUR LIFE,", 90, 330, 46, bold=True,
            frm=max(0.1, dp - 0.5), to=dp + 2.4),
        txt("TALKING TO A PRO IS STRENGTH.", 90, 400, 46, bold=True, color=GREEN,
            frm=max(0.1, dp - 0.1), to=dp + 2.4),
    ])

    # ---- S6: interactive ending -------------------------------------------------
    e_start = anchors["tell"] - 0.15
    e_end = dur_join + TAIL
    ed = max(0.1, anchors["drop"] - e_start)
    e_layers = [
        hero("hero-point", 460, 1400, h=920, seq=[(0, {"alpha": 0, "y": 1450}), (0.35, {"alpha": 1, "y": 1400})]),
        txt("YOUR TURN:", 120, 280, 64, bold=True, color=NAVY, frm=max(0.1, ed - 0.3)),
    ]
    for i, (t_, oy) in enumerate([("A. replaying old conversations", 560),
                                  ("B. imagining the worst", 660),
                                  ("C. worrying about the future", 760),
                                  ("D. literally ALL of them", 860)]):
        e_layers.append(txt(t_, 150, oy, 44, bold=(i == 3), color=(RED if i == 3 else None),
                            frm=max(0.1, ed + 0.1 + i * 0.35)))
    e_layers.append(txt("DROP YOUR ANSWER", 300, 2000, 54, bold=True, frm=max(0.1, ed + 1.7)))
    e_layers.append(txt("IN THE COMMENTS.", 300, 2075, 54, bold=True, frm=max(0.1, ed + 2.0)))
    S(e_start, e_end, e_layers)
    sfx.append({"time": round(anchors["drop"] + L + 1.8, 3), "kind": "pop", "gain": 0.05})

    project = {
        "version": 1,
        "style": "B1",
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "captionSize": 40,
        "voice": {"path": "vo.wav", "lead": LEAD, "tail": TAIL},
        "captions": captions,
        "shots": shots,
        "sfx": sfx,
        "music": {"path": "music-bed.m4a", "gain": 0.06},
    }
    (HERE / "project.json").write_text(json.dumps(project, indent=2))
    print(f"voice {dur_join:.2f}s, film {dur_join + LEAD + TAIL:.2f}s, "
          f"{len(shots)} shots, {len(captions)} captions, {len(sfx)} sfx")


if __name__ == "__main__":
    main()

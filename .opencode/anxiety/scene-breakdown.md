# Scene-by-scene breakdown
## "Your Brain Is Not Your Enemy: Understanding Anxiety" (89.5 s, 1080×1920)

12 shots, contiguous. All times are final film time (voice + 0.15 s lead).
Assets are procedurally drawn PNGs (`assets/`), placed by ink bounding box
(`assets/manifest.json`). Trigger times are word-anchored to the narration via
whisper.cpp + `shorts.timing.align` (100% word match).

| # | Film time | Story beat | Picture | Key motion / triggers |
|---|---|---|---|---|
| 1 | 0.00–4.68 | **Hook: the message** | Phone with notification banner slides up; "Can we talk tomorrow?" fades onto the banner | `pop` sfx at 0.70; phone slides 0→0.45s |
| 2 | 4.68–9.30 | **Imagination spiral** | Hero lying on the bed → shock swap at "suddenly"; thought stack types in: "Am I in trouble?" → "Did I do something wrong?" → "What if something bad happens?" → red "WHAT DID I DO?!" | eyes-open shock at anchor `suddenly`; lines at +0.4/0.75/1.0/1.25s |
| 3 | 9.30–12.39 | **Meet the alarm guard** | Tiny guard slides down to a big button console; "YOUR ALARM SYSTEM" title; warning light off | guard drop-in 0→0.5s |
| 4 | 12.39–24.69 | **Alarm = doing its job** | Light blinks red 3×, guard jitters left/right; green "JUST DOING ITS JOB" at "protective" (P3) | `tap` sfx ×2 at alarm; blink keys 0–1.08s |
| 5 | 24.69–42.44 | **Four faces grid** | 2×2 quadrants: 1 OVERTHINKING, 2 IN THE BODY, 3 AVOIDING, 4 WORST CASE; cell 4's tiny scribble swaps to the red question-mark monster at "tiny" | cells cascade +0.35s each; `pop` at monster |
| 6 | 42.44–45.26 | **Interactive pause** | Big bubble: "WHICH ONE SOUNDS MOST FAMILIAR? (take a second)" | deliberate ~2.4s quiet beat |
| 7 | 45.26–52.96 | **Technique 1 — NAME IT** | Hero gestures; bubble shows "SOMETHING TERRIBLE WILL HAPPEN!" → replaced by "a feeling is not automatically a fact." at `fact`; green NAME IT. | `chime` at section start; swap at word `fact` |
| 8 | 52.96–64.24 | **Technique 2 — GROUND YOURSELF** | Eye / hand / ear icons cascade in with "5 things you can SEE / 4 … FEEL / 3 … HEAR" | icons at `five`−0.2 + i×0.55s |
| 9 | 64.24–69.35 | **Technique 3 — SLOW DOWN** | Hero breathing with a pulsing breath ring (2 breath cycles, ~3s each) | ring scales 360↔560 on 4 keys |
| 10 | 69.35–76.16 | **Callback / resolve** | Hero sits calmly; "the same message." then the notification returns at `remember`+1.4 — but the hero stays calm; "don't believe every scary story." | notification re-entry at `remember` |
| 11 | 76.16–82.89 | **Disclaimer beat** | Hero explaining pose; "IF ANXIETY RUNS YOUR LIFE, TALKING TO A PRO IS STRENGTH." (green) | in at `professional`−0.5, out at `professional`+2.4 |
| 12 | 82.89–89.50 | **Interactive ending** | Hero points at camera; "YOUR TURN:" + options A–D ("D. literally ALL of them" in red); "DROP YOUR ANSWER IN THE COMMENTS." | options +0.35s each; `pop` near end; music tail to 89.5 |

## Sound spotting
- Music bed: uneasy A-minor pulse (0–34s) → warm A-major pad (34s+), −24 LUFS,
  gain 0.06 under voice throughout; tail carries the ending.
- SFX (procedural, all ≤0.06 gain): pop ×3 (message, monster, comment prompt),
  tap ×2 (alarm blink), chime ×1 (techniques section start). The breathing
  shot (9) is deliberately accent-free — the quiet is the point.

## Continuity notes
- One protagonist design throughout (head r≈46 proportions, same ink weight);
  15 pose/expression variants from one drawing function.
- Palette constant: ink #191916 on paper #FDFDFC, accents red #EC4338 /
  green #3F9142 / navy #2B3A67 only.
- Captions: 44 cues, word-timed to the synthesized script spelling, single
  line, centered in the bottom band; verified non-overlapping and in-band.

# Sound script — "Your Brain Is Not Your Enemy" (B1, 9:16, ~88 s)

Voice: server Voicebox "Kim Natural Voice" (cloned profile 8da2dcf2, qwen 0.6B,
seed 42), one generation per part, joined with 0.35 s pauses. Deliberate
substitution for the B1 default (Gemini Bodi — no key on this server); recorded
in project.json voice metadata. 1x rate, no retuning.

## Environment bed / music
- 0.0–34: uneasy low pulse (A2/C4/E, 0.8 Hz tremolo) — the "alarm world". Quiet,
  -24 LUFS bed, gain 0.06 under voice. No sudden levels.
- ~34–88: warm A-major pad (crossfade 6 s inside the bed file) — the "calm
  world", timed to the transition into the techniques section (p06).
- Music loops via renderer music.gain 0.06 (max 0.2 allowed; kept low).

## Spotting (procedural accents, all below voice)
| t (approx, final after align) | cue | why |
|---|---|---|
| phone-notification reveal (S1) | pop (gain .05) | notification arrival; the story's inciting device |
| alarm light turns red (S2) | tap (gain .05, x3 spaced) | alarm blinking; mechanical click material, not a horror hit |
| monster appears (S3) | paper→pop swap: pop (gain .06) | exaggerated "bloom" accent for the imagination payoff |
| scene transitions (S2->S3, S3->S4, S4->S5) | chime (gain .04) | soft boundary marker; light, not musical stinger |
| breathing shot (S4) | (none) | the quiet is the point; deliberate near-silence under voice |
| ending point-at-camera (S6) | pop (gain .05) | playful "your turn" accent |

## Hierarchy
Voice always front. Bed is continuous; accents are single transients, never
stacked with each other. The S4 section deliberately thins accents to carry the
"slow down" meaning. No jump scares, no riser, no horror palette.

## Rights
All audio generated locally: music bed = ffmpeg aevalsrc synthesis (original),
accents = renderer built-in procedural kinds (original). No third-party assets,
nothing to clear. Manifest: this file + project.json sfx/music entries.

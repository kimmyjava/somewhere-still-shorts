# Decisions and measurements (keep this file up to date)

## Content
- Channel: Somewhere Still. Mood: cozy, nostalgic, calm, gentle motion, soft fades.
- Length: 60 seconds to 3 minutes, vertical 1080x1920.
- Mascot: our own curly-haired girl with round glasses, cream cable-knit sweater, brown plaid pants, bear slippers. Prepared files in assets/mascot (copy installed in ~/.kape-explainer/profile/mascot). Poses: idle, point, wave, present, think, thumbs-up, celebrate, sit, rest. Expressions (not used yet) in assets/mascot/expressions. Point is not mirrored. Blinks off for now.
- Captions: on, word-timed, script spelling (not Whisper spelling).

## Voice (tested 2026-10-16)
- Voicebox v0.5.0, local API http://127.0.0.1:17493 (no auth; never expose it).
- Profile "Kim - Natural Voice", id ac52122c-5b02-4c66-b00d-ba5bb47b65f7 (cloned).
- engine "qwen", model_size "1.7B", language "en", seed 42. Always send engine explicitly.
- Flow: POST /generate -> poll GET /history/{id} until completed/failed -> GET /audio/{id} (WAV).
- Speed on this laptop (CPU only): 17.4 s of audio took 221 s (first run, incl. model load).
- Voicebox has no Tagalog. English narration only for now.

## Word timings (tested 2026-10-16)
- vendor KAPE scripts/transcribe.py, faster-whisper "medium", --lang en.
- 17.4 s audio transcribed in 13 s. All words correct.
- REQUIRES av==18.1.0 (av 19 breaks faster-whisper 1.2.1: unexpected 'metadata_errors').

## Rendering (tested 2026-10-16)
- HyperFrames 0.8.117, hardware GPU path works (Intel Iris Xe).
- 16:9 self-test 8.7 s @60fps: 42.8 s. 9:16 demo with mascot+captions 8.8 s @30fps draft: 35.1 s.
- Use npx.cmd (not npx) when typing commands in PowerShell.

## Images
- Hand-made library first (Gemini app, same style words every time).
- Automatic: Cloudflare Workers AI free tier (10,000 neurons/day), FLUX models.
- Gemini API images are paid only (no free tier). Optional test later.

## Music
- Library of 15-20 tracks downloaded once (YouTube Audio Library first), tagged by mood.
- Worker picks by mood, cuts to length, ducks under the voice (KAPE bgm-cut.py / master-audio idea).

## Not decided yet
- Final colours and fonts. Scene template list for the cozy style.

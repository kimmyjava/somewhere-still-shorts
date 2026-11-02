# Decisions and measurements (keep this file up to date)

## Content
- Channel: Somewhere Still. Mood: cozy, nostalgic, calm, gentle motion, soft fades.
- Length: 40 to 60 seconds, vertical 1080x1920.
- Mascot: our own curly-haired girl with round glasses, cream cable-knit sweater, brown plaid pants, bear slippers. Prepared files in assets/mascot (copy installed in ~/.kape-explainer/profile/mascot). Poses: idle, point, wave, present, think, thumbs-up, celebrate, sit, rest. Expressions (not used yet) in assets/mascot/expressions. Point is not mirrored. Blinks off for now.
- Captions: on, word-timed, script spelling (not Whisper spelling).

## Voice (tested 2026-10-16)
- Voicebox v0.5.0, local API http://127.0.0.1:17493 (no auth; never expose it).
- Profile "Kim - Natural Voice", id ac52122c-5b02-4c66-b00d-ba5bb47b65f7 (cloned).
- engine "qwen", model_size "1.7B", language "en", seed 42. Always send engine explicitly.
- Flow: POST /generate -> poll GET /history/{id} until completed/failed -> GET /audio/{id} (WAV).
- Speed on this laptop (CPU only): 17.4 s of audio took 221 s (first run, incl. model load).
- Voicebox has no Tagalog. English narration only for now.
- Per-scene voice (2026-10-25): each scene's narration is generated separately (same profile,
  engine and seed 42) and cached as <job>/voice/<scene_id>.wav; parts are reused when they exist
  unless --redo-voice. Parts are joined into <job>/vo.wav with 0.35 s of silence between scenes
  (stdlib wave, shorts/tts/join.py); all parts must share sample rate, sample width and channels.
- --redo-scene <scene_id> (repeatable) deletes only that scene's cached part and regenerates it
  with seed + 1 (a different take), then rejoins vo.wav and reruns timing, film and render.

### Server voice (2026-11)
- TrueNAS Voicebox Docker v0.6.0, reached via SHORTS_VOICEBOX_URL (host-local, never exposed).
- Profile: kokoro preset "Heart", id 65c29b06-04b5-4df7-8af9-2e44c2239630, engine "kokoro",
  model_size must be null (kokoro has no size axis). Env-driven: SHORTS_VOICEBOX_URL,
  SHORTS_VOICE_PROFILE_ID, SHORTS_VOICE_ENGINE, SHORTS_VOICE_MODEL_SIZE (server values in
  /workspace/shorts-data/env.sh); unset falls back to the laptop's Kim/qwen values above.
- The cloned "Kim" profile exists only on the laptop; importing it to the server is a later
  env-only change (kokoro may not accept cloned profiles - test before switching).

## Word timings (tested 2026-10-16)
- Laptop: vendor KAPE scripts/transcribe.py, faster-whisper "medium", --lang en.
- 17.4 s audio transcribed in 13 s. All words correct.
- REQUIRES av==18.1.0 (av 19 breaks faster-whisper 1.2.1: unexpected 'metadata_errors').
- Off-Windows (2026-11): faster-whisper is not installable on musl (no ctranslate2/
  onnxruntime/torch wheels), so shorts/timing.py dispatches on platform: win32 keeps the
  vendor script untouched; everywhere else transcribe_hyperframes() runs whisper.cpp
  through the pinned npx hyperframes@0.8.117 CLI (SHORTS_WHISPER_MODEL, default small.en;
  model cached in /config/.cache/hyperframes on the server). Validated on the server
  2026-11-02: word timings land correctly end-to-end (alignment: "whisper").

## Rendering (tested 2026-10-16)
- HyperFrames 0.8.117, hardware GPU path works (Intel Iris Xe).
- 16:9 self-test 8.7 s @60fps: 42.8 s. 9:16 demo with mascot+captions 8.8 s @30fps draft: 35.1 s.
- Use npx.cmd (not npx) when typing commands in PowerShell.

## Images
- Hand-made library first (Gemini app, same style words every time).
- Automatic: Cloudflare Workers AI free tier (10,000 neurons/day), FLUX models.
- Gemini API images are paid only (no free tier). Optional test later.

## Backgrounds (2026-10-20, tasks 08-09; refs off 2026-10-25 task 13, unit-tested offline)
- Model: Cloudflare Workers AI @cf/black-forest-labs/flux-2-klein-4b, 768x1344 JPG (shorts/images.py).
- Style refs are OFF (USE_STYLE_REF = False, 2026-10-25): the model copied the reference pictures'
  buildings and furniture into every scene, so no input_image_0 is sent any more. The look comes
  from STYLE_TEXT only ("Cozy hand-painted storybook illustration ... calm and dreamy"), then
  STYLE_SUFFIX (full vertical composition, empty scene, no people/animals/text).
  pick_style_ref and the three refs in assets/bg/ stay in the code, unused, for later.
- Refs as they worked when they were on (kept for later): one ref per scene as image 0;
  kitchen words (kitchen, stove, kettle, table, mug, cafe) -> kitchen ref; street/outside words
  (street, outside, road, town, garden, porch, sky, park, car) -> street ref; otherwise rotate
  books -> kitchen -> street by scene index.
- Cost: about 160 neurons per picture; free 10,000 neurons/day = about 60 pictures.
- Library: C:/shorts/bg-library (outside the repo). One picture per prompt+ref-name pair,
  name gen-<12 hex> = sha256 of normalized prompt + ref name; with refs off the name is "noref",
  so old ref-based pictures are never reused. index.jsonl logs file, prompt, model, style_ref
  ("noref"), created. images.json records "ref": null when no reference was sent.
- Never fail a job for a picture: missing CF_ACCOUNT_ID / CF_API_TOKEN, --no-images or an API error
  (one retry on timeout / 5xx) falls back to the scene's fixed bg (or bg-books). Per-scene record
  with bg, style, ref, generated / reused / fallback in <job>/images.json.
- Two picture styles (2026-10-29, task 16): the brief's top-level "style" picks "cozy" (default)
  or "storybook"; n8n chooses per video. An unknown style logs a warning and falls back to cozy.
  The style text is STYLE_TEXTS[style] in shorts/images.py (storybook = vintage picture-book
  watercolour, ends "no border, no frame, no paper edges"), the library hash includes the style
  (bg_name covers prompt + ref + style) and index.jsonl logs it. Storybook scenes start the Ken
  Burns push at zoom 1.06 (cozy 1.0) so thin paper edges never show.

## Music
- Library of 15-20 tracks downloaded once (YouTube Audio Library first), tagged by mood.
- Worker picks by mood, cuts to length, ducks under the voice (KAPE bgm-cut.py / master-audio idea).
- Note (2026-10-19): royalty-free tracks from Pixabay / YouTube Audio Library, no attribution
  required. Files live in C:/shorts/music named <mood>-NN.mp3 (not in git). The worker picks by
  slug hash (shorts/music.py, own ffmpeg mix - vendor master-audio.py is NOT used), normalises the
  track to -30 LUFS, sidechain-ducks it under the voice, final mix -14 LUFS.

## Gateway
- Local job gateway: FastAPI (tools/gateway.py); auth: X-API-Key header compared against the
  SHORTS_API_KEY env var (>= 32 chars, never logged or returned). One worker thread, one job at
  a time; status in <job>/status.json.
- Laptop: bound to 127.0.0.1:8787 ONLY; n8n reaches it through a Tailscale Funnel (https), never
  an open port. Voicebox stays on 127.0.0.1:17493 and is never exposed; /health only reports its
  up/down.
- TrueNAS server (2026-11): `python -m tools.gateway --host 0.0.0.0 --port 8787` behind a
  published Docker port (8787:8787) - LAN-only, still key-gated. n8n (same host, 192.168.8.184)
  posts briefs to http://192.168.8.184:8787/jobs. SHORTS_API_KEY lives in
  /config/opencode/shorts-gateway.env (chmod 600, outside the repo); source it plus
  /workspace/shorts-data/env.sh before starting. Gateway health: /health (no key needed).

## Server validation (2026-11-02)
- First full end-to-end run on the TrueNAS server, driven by n8n: topic -> Groq script ->
  Gemini brief -> validation -> gateway job -> render -> Telegram delivery. Job
  bakery-cat-quiet-20261102-092827: done in ~4 min, 1080x1920 h264, 33.6 s, 5 scenes,
  kokoro "Heart" voice, whisper.cpp timings.
- Expected gaps on the server: no CF_ACCOUNT_ID/CF_API_TOKEN yet (images.json shows
  source: "fallback", fixed backgrounds used) and no music library yet (video ships
  without music). Both degrade gracefully by design.
- n8n (self-hosted, same host) is rewired to the server gateway: all five HTTP nodes use
  http://192.168.8.184:8787, credential "Shorts gateway key" (X-API-Key) on the four job
  routes; n8n's SSRF allowlist needs 192.168.8.184/32 (N8N_SSRF_ALLOWED_IP_RANGES).
  Pre-rewire backup: /workspace/shorts-data/tmp/workflow-backup-6OJOrTk7H5gvZpJp.json.
- Gateway restart after any opencode container restart/recreate:
  docker exec opencode sh /workspace/shorts-data/start-gateway.sh

## Not decided yet
- Final colours and fonts. Scene template list for the cozy style.

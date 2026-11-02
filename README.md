# Somewhere Still - shorts-worker

## 1. What it is

**Somewhere Still** is an automated pipeline that turns a topic into a cozy, nostalgic
40 to 60 second YouTube Short. It uses my own cloned voice, my own mascot, AI-generated
backgrounds and royalty-free music. Before anything is uploaded, a human (me) approves
the video on Telegram. The heavy work happens at home - originally on my Windows laptop,
now on the TrueNAS server in Docker (the laptop still works as a fallback) - so it stays
calm, private and almost free.

## 2. How it works

One run of the pipeline looks like this:

1. **n8n (self-hosted on the same TrueNAS host):** Gemini writes the script, Groq turns it
   into a structured brief (JSON), then a check step validates the brief.
2. **Job gateway (FastAPI):** the brief arrives here and the worker starts one job:
   - Cloudflare Workers AI (FLUX) paints the AI backgrounds in the cozy style (falls back
     to built-in fixed backgrounds if Cloudflare is not configured).
   - Voicebox (local Docker) speaks the narration with my cloned voice.
   - Word timings: faster-whisper on Windows; whisper.cpp (via the pinned hyperframes CLI)
     everywhere else.
   - HyperFrames + GSAP render the vertical video (1080x1920) with mascot and captions.
   - FFmpeg mixes in music, ducked under the voice (no music yet on the server - it ships
     without music until the music library is set up).
3. **Telegram:** the finished preview is sent for approval. Only after I say yes does
   it go to YouTube upload.
4. **Google Sheet calendar + a daily 8 PM timer** in n8n decide when the next Short
   gets made.

First validated on the server 2026-11-02: brief -> voice -> timing -> render ran
end-to-end through n8n and the gateway (job `bakery-cat-quiet-20261102-092827`,
1080x1920 h264, whisper.cpp timings).

## 3. Tools

| Tool | What it does | Cost |
| --- | --- | --- |
| n8n | Self-hosted automation: script, brief, calendar, Telegram, upload | Software free; Docker on the TrueNAS host |
| Gemini API | Writes the first draft of the script | Free tier |
| Groq | Turns the script into a structured JSON brief | Free tier |
| Cloudflare Workers AI | FLUX image models for the AI backgrounds | Free tier (about 60 pictures/day) |
| Voicebox | Voice narration: my cloned voice on the laptop, kokoro "Heart" preset on the server | Free, runs at home |
| faster-whisper / whisper.cpp | Word-level timings from the voice audio (whisper.cpp off-Windows) | Free, runs on CPU |
| HyperFrames + GSAP | Renders the final HTML/JS video, frame by frame | Free |
| FFmpeg | Cuts and mixes the music under the voice | Free |
| Pixabay / YouTube Audio Library | Royalty-free music, no attribution needed | Free |
| Tailscale Funnel | Lets n8n reach the laptop gateway without an open port (laptop mode only) | Free tier |
| FastAPI | The local job gateway that accepts one job at a time | Free |
| Telegram | Sends the video for approval | Free |
| Google Sheets | Content calendar | Free |
| YouTube Data API | Uploads after approval | Free |
| Nano Banana / Google AI Plus | Designed the mascot and the first backgrounds | Existing paid subscription |
| OpenCode + GLM on the Z.AI Coding Plan | AI coding helper that wrote the code with me | Paid subscription, only for building, not needed to run |

Running the pipeline costs nothing extra: every service it uses is free or free-tier.
Building it used two subscriptions I already had (Z.AI Coding Plan and Google AI Plus),
and n8n runs at home on the TrueNAS host.

## 4. Inspiration

The process flow (script, then scenes, then voice, then render) was inspired by the
open **KAPE explainer toolkit**, which lives in `vendor/` as the blueprint and engine.
The look, the scripts, the mascot and the voice are entirely my own - the cozy
"Somewhere Still" style is deliberately different from KAPE's explainer style.

KAPE explainer toolkit by Kenneth Villar (BrewedOps), MIT License - see
vendor/kape-explainer/LICENSE. The KAPE mascot artwork is not used and is not covered
by MIT.

## 5. Running it

Two homes run the same code. Defaults keep the laptop working; the server only needs
environment variables.

### Laptop (Windows, the original home)

What must be open before a run:

- **Voicebox** running locally (localhost only, never exposed).
- **The gateway**: `C:/shorts/venv/Scripts/python -m tools.gateway`

One command makes a Short from a brief:

```
C:/shorts/venv/Scripts/python -m tools.make_short --brief brief.json
```

### TrueNAS server (2026-11, the daily driver)

The worker lives in the opencode container; Voicebox is the Voicebox Docker container
on the same host. Gateway secrets and server paths live outside the repo.

```sh
# one-time / after any container restart: start the gateway (key-gated, LAN-exposed)
sh /workspace/shorts-data/start-gateway.sh

# from the host, after the opencode stack restarts:
docker exec opencode sh /workspace/shorts-data/start-gateway.sh
```

Server env lives in `/workspace/shorts-data/env.sh` (Voicebox URL, voice profile,
HyperFrames browser path). The gateway key lives in
`/config/opencode/shorts-gateway.env` (chmod 600, never in the repo).

Environment variables (names only - values live in your environment, never in code or
logs; all have laptop-compatible defaults):

| Variable | Purpose | Laptop default (unset behaviour) |
| --- | --- | --- |
| `SHORTS_API_KEY` | key the gateway checks on every request (>= 32 chars) | required to start the gateway |
| `CF_ACCOUNT_ID` / `CF_API_TOKEN` | Cloudflare, for AI backgrounds | missing = fixed-background fallback |
| `SHORTS_VOICEBOX_URL` | Voicebox API base | `http://127.0.0.1:17493` |
| `SHORTS_VOICE_PROFILE_ID` | voice profile id | the cloned "Kim" profile id |
| `SHORTS_VOICE_ENGINE` | Voicebox engine | `qwen` (server uses `kokoro`) |
| `SHORTS_VOICE_MODEL_SIZE` | engine model size | `1.7B` (kokoro needs it empty/null) |
| `SHORTS_DATA_ROOT` | root for `jobs/`, `music/`, bg library | `C:/shorts` |
| `SHORTS_WHISPER_MODEL` | whisper.cpp model (off-Windows timing) | `small.en` |
| `HYPERFRAMES_BIN` / `HYPERFRAMES_BROWSER_PATH` | pinned hyperframes CLI / Chromium path | npx `hyperframes@0.8.117` / default |

Run the fast tests (no voice, no render):

```
C:/shorts/venv/Scripts/python -m pytest -q -m "not slow"    # laptop
.venv/bin/python -m pytest -q -m "not slow"                 # server (/workspace/video-generation/.venv)
```

## 6. Safety

- Secrets live only in environment variables and n8n credentials - never in code,
  logs or tests.
- Voicebox stays on localhost and is never exposed to the internet; the health check
  only reports whether it is up.
- The gateway always requires an API key. Laptop: bound to localhost only, reached
  through a tunnel. Server: published on the LAN (8787) but still key-gated; n8n
  reaches it from the same host over the LAN.
- Every video needs human approval on Telegram before it is uploaded. Nothing goes to
  YouTube by itself.

## 7. Project layout

- `shorts/` - the pipeline code (brief, voice, timing, scenes, images, music, render, QA).
- `tools/` - command-line tools: `make_short` (one brief to one video) and `gateway` (the local job server).
- `tests/` - fast and slow tests.
- `assets/` - mascot, fonts, style references and fixed backgrounds.
- `docs/` - decisions and references.
- `vendor/` - the KAPE toolkit, kept untouched.

Server-only (outside the repo, on TrueNAS): `/workspace/shorts-data/` holds `env.sh`,
`start-gateway.sh` and the jobs root; `/config/opencode/shorts-gateway.env` holds the
gateway API key.

## 8. What's next

- A Telegram `/short` command to start a Short from chat.
- A monthly AI topic planner for the content calendar.
- Cloudflare credentials on the server for AI backgrounds (falls back to fixed
  backgrounds until then) and a music library at `/workspace/shorts-data/music`.
- Importing the cloned "Kim" voice profile from the laptop to the server Voicebox
  (an env change: `SHORTS_VOICE_PROFILE_ID`/`SHORTS_VOICE_ENGINE`).
- The gateway starting automatically with the stack (own compose service) instead of
  `start-gateway.sh` after restarts.
- Real Telegram approve buttons.

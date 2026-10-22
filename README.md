# Somewhere Still - shorts-worker

## 1. What it is

**Somewhere Still** is an automated pipeline that turns a topic into a cozy, nostalgic
40 to 60 second YouTube Short. It uses my own cloned voice, my own mascot, AI-generated
backgrounds and royalty-free music. Before anything is uploaded, a human (me) approves
the video on Telegram. The heavy work happens on my own Windows laptop, so it stays
calm, private and almost free.

## 2. How it works

One run of the pipeline looks like this:

1. **n8n (cloud):** Gemini writes the script, Groq turns it into a structured brief
   (JSON), then a check step validates the brief.
2. **Laptop gateway (FastAPI):** the brief arrives here and the worker starts one job:
   - Cloudflare Workers AI (FLUX) paints the AI backgrounds in the cozy style.
   - Voicebox (local) speaks the narration with my cloned voice.
   - faster-whisper times every word, so captions and scenes land on the voice.
   - HyperFrames + GSAP render the vertical video (1080x1920) with mascot and captions.
   - FFmpeg mixes in music, ducked under the voice.
3. **Telegram:** the finished preview is sent for approval. Only after I say yes does
   it go to YouTube upload.
4. **Google Sheet calendar + a daily 8 PM timer** in n8n decide when the next Short
   gets made.

## 3. Tools

| Tool | What it does | Cost |
| --- | --- | --- |
| n8n | Cloud automation: script, brief, calendar, Telegram, upload | Software free; runs on a shared Hostinger server |
| Gemini API | Writes the first draft of the script | Free tier |
| Groq | Turns the script into a structured JSON brief | Free tier |
| Cloudflare Workers AI | FLUX image models for the AI backgrounds | Free tier (about 60 pictures/day) |
| Voicebox | Local cloned voice narration on this laptop | Free, runs at home |
| faster-whisper | Word-level timings from the voice audio | Free, runs on CPU |
| HyperFrames + GSAP | Renders the final HTML/JS video, frame by frame | Free |
| FFmpeg | Cuts and mixes the music under the voice | Free |
| Pixabay / YouTube Audio Library | Royalty-free music, no attribution needed | Free |
| Tailscale Funnel | Lets n8n reach the laptop gateway without an open port | Free tier |
| FastAPI | The local job gateway that accepts one job at a time | Free |
| Telegram | Sends the video for approval | Free |
| Google Sheets | Content calendar | Free |
| YouTube Data API | Uploads after approval | Free |
| Nano Banana / Google AI Plus | Designed the mascot and the first backgrounds | Existing paid subscription |
| OpenCode + GLM on the Z.AI Coding Plan | AI coding helper that wrote the code with me | Paid subscription, only for building, not needed to run |

Running the pipeline costs nothing extra: every service it uses is free or free-tier.
Building it used two subscriptions I already had (Z.AI Coding Plan and Google AI Plus),
and n8n runs on a shared server.

## 4. Inspiration

The process flow (script, then scenes, then voice, then render) was inspired by the
open **KAPE explainer toolkit**, which lives in `vendor/` as the blueprint and engine.
The look, the scripts, the mascot and the voice are entirely my own - the cozy
"Somewhere Still" style is deliberately different from KAPE's explainer style.

KAPE explainer toolkit by Kenneth Villar (BrewedOps), MIT License - see
vendor/kape-explainer/LICENSE. The KAPE mascot artwork is not used and is not covered
by MIT.

## 5. Running it

What must be open before a run:

- **Voicebox** running locally (localhost only, never exposed).
- **The gateway**: `C:/shorts/venv/Scripts/python -m tools.gateway`

Environment variables needed (names only - values live in your environment, never in
code or logs):

- `SHORTS_API_KEY` - key the gateway checks on every request (at least 32 characters)
- `CF_ACCOUNT_ID` - Cloudflare account, for AI backgrounds
- `CF_API_TOKEN` - Cloudflare token, for AI backgrounds

One command makes a Short from a brief:

```
C:/shorts/venv/Scripts/python -m tools.make_short --brief brief.json
```

Run the fast tests (no voice, no render):

```
C:/shorts/venv/Scripts/python -m pytest -q -m "not slow"
```

## 6. Safety

- Secrets live only in environment variables and n8n credentials - never in code,
  logs or tests.
- Voicebox stays on localhost and is never exposed to the internet; the health check
  only reports whether it is up.
- The gateway binds to localhost only and is reached through a tunnel with an API key.
- Every video needs human approval on Telegram before it is uploaded. Nothing goes to
  YouTube by itself.

## 7. Project layout

- `shorts/` - the pipeline code (brief, voice, timing, scenes, images, music, render, QA).
- `tools/` - command-line tools: `make_short` (one brief to one video) and `gateway` (the local job server).
- `tests/` - fast and slow tests.
- `assets/` - mascot, fonts, style references and fixed backgrounds.
- `docs/` - decisions and references.
- `n8n/` - exported n8n workflow.
- `vendor/` - the KAPE toolkit, kept untouched.

## 8. What's next

- A Telegram `/short` command to start a Short from chat.
- A monthly AI topic planner for the content calendar.
- The gateway and Voicebox starting automatically with Windows.
- Real Telegram approve buttons.

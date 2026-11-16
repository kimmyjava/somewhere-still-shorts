# shorts-worker - rules for coding agents (GLM in OpenCode, Kimi for reviews)

## What this project is
A worker that turns a validated video brief (JSON) into a finished vertical YouTube
Short (1080x1920 MP4, 40 to 60 seconds) for the channel "Somewhere Still"
(cozy, nostalgic, calm). It runs in two homes with the same code:
- Laptop (Windows): the original home, still a working fallback. Python at
  C:\shorts\venv, Voicebox on localhost.
- TrueNAS server (2026-11, the daily driver): inside the opencode Docker container,
  Python at /workspace/video-generation/.venv, Voicebox as a Docker container on the
  same host. n8n on the same host submits jobs over the LAN.
Read docs/decisions.md before every task. It lists what is already decided and measured.

## The pipeline (one job = one Short)
brief.json -> voice (Voicebox, local) -> word timings (faster-whisper on Windows,
whisper.cpp via pinned hyperframes CLI everywhere else) -> scene timing
-> scene HTML from templates -> mascot overlay -> captions overlay -> music + mix
-> HyperFrames render -> QA checks -> preview.mp4 for human review.
Scripts are written by n8n (remote) BEFORE the job reaches this worker.

## Hard rules
- Never edit anything in vendor/. It is the KAPE toolkit, kept unchanged.
  Call its scripts as subprocesses, or copy logic into shorts/ and adapt it there.
- KAPE is the BLUEPRINT and ENGINE, not the look. Do not copy KAPE's explainer style,
  colours, mascot or words into new templates. Our look is Somewhere Still (docs/decisions.md).
- Before writing code, read the files the task lists and say what you will reuse.
- One task = one small change + its tests. Stop when the task's "Done when" is met.
- The worker must never call an LLM or a coding agent at runtime.
- Windows first: pathlib everywhere, subprocess with argument lists, shell=False
  (except npx, which needs shell=True on Windows, as vendor scripts do).
  Server (Linux/musl) second: no Windows-only calls outside a sys.platform == "win32"
  branch; off-Windows timing uses whisper.cpp through the pinned hyperframes CLI.
- Kill timed-out renders with: taskkill /T /F /PID <pid> (Windows).
- No secrets in code, logs or tests. Read them from environment variables.
  Server secrets live in /config/opencode/shorts-gateway.env (outside the repo).
- Voicebox stays on loopback (127.0.0.1:17493 on the laptop; the server container
  resolves it through SHORTS_VOICEBOX_URL, still host-local). Never add code that
  exposes it.
- Pinned versions: hyperframes 0.8.117 (never upgrade), gsap 3.14.2, av==18.1.0.
- Never create or edit files outside this repository. Tools may write job output only into the --jobs-root folder.

## Paths
Laptop (Windows):
- Python: C:\shorts\venv\Scripts\python.exe (use it for everything)
- KAPE skill:   vendor\kape-explainer\skills\kape-explainer
- KAPE engine:  vendor\kape-explainer\skills\spatial-film
- Voicebox API description: docs\voicebox-openapi.json

Server (TrueNAS, Linux/musl):
- Python: /workspace/video-generation/.venv/bin/python
- KAPE home: /workspace/video-generation/vendor/kape-explainer (KAPE_EXPLAINER_HOME
  set by /workspace/shorts-data/env.sh)
- Server env: source /workspace/shorts-data/env.sh (Voicebox URL, kokoro "Heart"
  profile, HyperFrames browser path, data root /workspace/shorts-data)
- Gateway: `python -m tools.gateway --host 0.0.0.0 --port 8787`; restart with
  `sh /workspace/shorts-data/start-gateway.sh` after any container restart.
  SHORTS_API_KEY lives in /config/opencode/shorts-gateway.env (chmod 600).

## Shell
Laptop: OpenCode runs commands in Git Bash on Windows. Always use forward slashes in paths, for example C:/shorts/venv/Scripts/python. Backslash paths fail in Git Bash.
Server: plain Linux shell (BusyBox tools); paths as written above.

## Tests
- Fast:   python -m pytest -q -m "not slow"   (no Voicebox, no render, < 30 s)
          laptop: C:/shorts/venv/Scripts/python   server: .venv/bin/python
- Slow:   python -m pytest -q -m slow          (the human runs these)
- Every new function gets a fast test. Fixtures live in tests/fixtures/.

## Server runbook (2026-11, in the opencode container)
- Source /workspace/shorts-data/env.sh before any pipeline or gateway command.
- Gateway restart after any Dockge restart/recreate of the opencode stack:
  `sh /workspace/shorts-data/start-gateway.sh` (idempotent, health-checks itself).
- Timing off-Windows needs npx (hyperframes@0.8.117); the whisper.cpp model is cached
  in /config/.cache/hyperframes. /tmp is wiped on container recreate - anything
  installed there must be re-created or replaced by env paths in env.sh.
- n8n workflow "Somewhere Still - Make a Short (core)" posts briefs to
  http://<server-host>:8787/jobs with the "Shorts gateway key" credential.
  n8n's SSRF allowlist must include <server-host>/32 (N8N_SSRF_ALLOWED_IP_RANGES).
- n8n executions debugging (verified 2026-11-02):
  - Test/MCP-triggered webhook runs ARE saved and listed by the API (mode "webhook"/
    "manual"). If executions seem missing, the usual cause is that the probe workflow
    was deleted first: deleting a workflow cascade-deletes its executions. Inspect
    executions BEFORE deleting any test workflow.
  - n8n_test_workflow method "trigger" fires the PRODUCTION webhook URL, so the
    workflow must be active - and activation registers the webhook asynchronously.
    The first fire right after activation can 404 ("webhook not registered") while
    the tool still reports success:true; wait a few seconds after activating and
    check the response body before trusting "success".
  - Manual editor runs save per workflow setting "Save manual executions" (default
    on in this instance; env EXECUTIONS_DATA_SAVE_MANUAL_EXECUTIONS).

## Planned layout
shorts/brief.py     shorts/tts/        shorts/timing.py   shorts/captions.py
shorts/scenes/      shorts/film.py     shorts/runner.py   shorts/qa.py
shorts/images.py    shorts/music.py    shorts/jobs.py     shorts/api.py
tools/make_short.py

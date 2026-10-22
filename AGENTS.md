# shorts-worker - rules for coding agents (GLM in OpenCode, Kimi for reviews)

## What this project is
A local worker on a Windows laptop that turns a validated video brief (JSON) into a
finished vertical YouTube Short (1080x1920 MP4, 40 to 60 seconds) for the
channel "Somewhere Still" (cozy, nostalgic, calm).
Read docs/decisions.md before every task. It lists what is already decided and measured.

## The pipeline (one job = one Short)
brief.json -> voice (Voicebox, local) -> word timings (faster-whisper) -> scene timing
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
- Kill timed-out renders with: taskkill /T /F /PID <pid>.
- No secrets in code, logs or tests. Read them from environment variables.
- Voicebox stays on 127.0.0.1:17493. Never add code that exposes it.
- Pinned versions: hyperframes 0.8.117 (never upgrade), gsap 3.14.2, av==18.1.0.
- Never create or edit files outside this repository. Tools may write job output only into the --jobs-root folder.

## Paths on this laptop
- Python: C:\shorts\venv\Scripts\python.exe (use it for everything)
- KAPE skill:   vendor\kape-explainer\skills\kape-explainer
- KAPE engine:  vendor\kape-explainer\skills\spatial-film
- Voicebox API description: docs\voicebox-openapi.json

## Shell
OpenCode runs commands in Git Bash on Windows. Always use forward slashes in paths, for example C:/shorts/venv/Scripts/python. Backslash paths fail in Git Bash.

## Tests
- Fast: C:/shorts/venv/Scripts/python -m pytest -q -m "not slow"   (no Voicebox, no render, < 30 s)
- Slow: C:/shorts/venv/Scripts/python -m pytest -q -m slow          (the human runs these)
- Every new function gets a fast test. Fixtures live in tests/fixtures/.

## Planned layout
shorts/brief.py     shorts/tts/        shorts/timing.py   shorts/captions.py
shorts/scenes/      shorts/film.py     shorts/runner.py   shorts/qa.py
shorts/images.py    shorts/music.py    shorts/jobs.py     shorts/api.py
tools/make_short.py

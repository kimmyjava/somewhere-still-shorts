"""Generate all narration parts via the server Voicebox. Cached; safe to re-run."""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, "/workspace/video-generation")
from shorts.tts.voicebox import VoiceboxTTS  # noqa: E402
from shorts.tts.base import VoiceSpec  # noqa: E402

from narration import PARTS, VOICE_DIR  # noqa: E402


def main() -> None:
    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    tts = VoiceboxTTS()
    if not tts.health():
        raise SystemExit("Voicebox not healthy")
    spec = VoiceSpec(
        profile_id=os.environ["SHORTS_VOICE_PROFILE_ID"],
        engine=os.environ.get("SHORTS_VOICE_ENGINE", "qwen"),
        model_size=os.environ.get("SHORTS_VOICE_MODEL_SIZE") or "1.7B",
        language="en",
        seed=42,
    )
    for pid, text in PARTS:
        out = VOICE_DIR / f"{pid}.wav"
        if out.exists() and out.stat().st_size > 1000:
            print(f"{pid}: cached", flush=True)
            continue
        for attempt in (1, 2, 3):
            try:
                if not tts.health():
                    print(f"{pid}: worker down, waiting 30s (attempt {attempt})", flush=True)
                    time.sleep(30)
                    if not tts.health():
                        continue
                t0 = time.time()
                r = tts.synthesize(text, spec, out)
                print(f"{pid}: {r.duration_s:.2f}s audio in {r.seconds_taken:.0f}s", flush=True)
                break
            except Exception as e:
                print(f"{pid}: attempt {attempt} failed: {type(e).__name__}", flush=True)
                time.sleep(20)
        else:
            raise SystemExit(f"{pid}: failed after 3 attempts")


if __name__ == "__main__":
    main()

"""Make a narration WAV with the local Voicebox.

usage: python tools/make_voice.py --text-file script.txt --out out/vo.wav [--profile-id <id>]
Prints audio length and seconds taken. Needs Voicebox (SHORTS_VOICEBOX_URL or 127.0.0.1:17493).
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shorts.tts.base import VoiceSpec
from shorts.tts.voicebox import DEFAULT_BASE_URL, VoiceboxTTS, env_base_url, env_engine, env_model_size

DEFAULT_PROFILE_ID = "ac52122c-5b02-4c66-b00d-ba5bb47b65f7"


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate a narration WAV with the local Voicebox.")
    ap.add_argument("--text-file", required=True, help="UTF-8 text file with the narration")
    ap.add_argument("--out", required=True, help="output WAV path")
    ap.add_argument("--profile-id", default=os.environ.get("SHORTS_VOICE_PROFILE_ID", "").strip()
                    or DEFAULT_PROFILE_ID, help="Voicebox voice profile id")
    a = ap.parse_args()

    text = Path(a.text_file).read_text(encoding="utf-8").strip()
    tts = VoiceboxTTS()
    if not tts.health():
        raise SystemExit(f"Voicebox not healthy at {env_base_url()}")
    result = tts.synthesize(text, VoiceSpec(profile_id=a.profile_id, engine=env_engine(),
                                            model_size=env_model_size()), Path(a.out))
    print(f"audio {result.duration_s:.1f}s took {result.seconds_taken:.1f}s -> {result.path}")


if __name__ == "__main__":
    main()

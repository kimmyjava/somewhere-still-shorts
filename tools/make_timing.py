"""Make word timings and captions for a narration WAV (runs Whisper - slow).

usage: C:/shorts/venv/Scripts/python tools/make_timing.py --wav assets/audio/vo.wav
       --script-file script.txt --out-dir src/timing
Writes words.json (aligned TimedWords), captions.srt and m-captions.html into --out-dir.
"""
import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shorts.captions import caption_composition, make_chunks, write_srt
from shorts.timing import align, load_whisper_words, transcribe


def main() -> None:
    ap = argparse.ArgumentParser(description="Word timings + captions from a narration WAV and its script.")
    ap.add_argument("--wav", required=True, help="narration audio (wav/mp3)")
    ap.add_argument("--script-file", required=True, help="UTF-8 script the narration was read from")
    ap.add_argument("--out-dir", required=True, help="folder for words.json, captions.srt, m-captions.html")
    a = ap.parse_args()

    out_dir = Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    script = Path(a.script_file).read_text(encoding="utf-8")

    words_json = transcribe(Path(a.wav), out_dir)
    timed = align(script, load_whisper_words(words_json))
    chunks = make_chunks(timed)
    total = timed[-1].end if timed else 0.0

    (out_dir / "words.json").write_text(
        json.dumps([asdict(w) for w in timed], ensure_ascii=False), encoding="utf-8")
    write_srt(chunks, out_dir / "captions.srt")
    (out_dir / "m-captions.html").write_text(caption_composition(chunks, total), encoding="utf-8")
    print(f"{len(timed)} words, {len(chunks)} chunks, {total:.2f}s total -> {out_dir}")


if __name__ == "__main__":
    main()

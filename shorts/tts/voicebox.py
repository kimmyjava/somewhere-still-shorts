"""Local Voicebox v0.5.0 client (http://127.0.0.1:17493 - never expose it).

Flow per docs/decisions.md: POST /generate, poll GET /history/{id} until
completed/failed, then GET /audio/{id} (WAV). Engine is always sent explicitly.
"""
import io
import time
import wave
from pathlib import Path

import httpx

from shorts.tts.base import TTSResult, VoiceSpec

DEFAULT_BASE_URL = "http://127.0.0.1:17493"


class VoiceboxError(Exception):
    """A Voicebox generation failed or timed out."""


class VoiceboxTTS:
    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        poll_every: float = 3.0,
        timeout_s: float = 1800.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._poll_every = poll_every
        self._timeout_s = timeout_s
        self._client = client or httpx.Client(base_url=self._base_url, timeout=30.0)

    def health(self) -> bool:
        try:
            r = self._client.get("/health")
        except httpx.HTTPError:
            return False
        if not r.is_success:
            return False
        try:
            return r.json().get("status") == "healthy"
        except ValueError:
            return False

    def synthesize(self, text: str, voice: VoiceSpec, out_wav: Path) -> TTSResult:
        out_wav = Path(out_wav)
        started = time.monotonic()
        r = self._client.post("/generate", json={
            "profile_id": voice.profile_id,
            "text": text,
            "language": voice.language,
            "engine": voice.engine,
            "model_size": voice.model_size,
            "seed": voice.seed,
        })
        r.raise_for_status()
        gen_id = r.json().get("id")
        if not gen_id:
            raise VoiceboxError("Voicebox /generate returned no id")

        deadline = started + self._timeout_s
        duration = None
        while True:
            r = self._client.get(f"/history/{gen_id}")
            r.raise_for_status()
            info = r.json()
            status = info.get("status")
            if status == "completed":
                duration = info.get("duration")
                break
            if status == "failed":
                raise VoiceboxError(info.get("error") or "Voicebox generation failed")
            if time.monotonic() >= deadline:
                raise VoiceboxError(
                    f"Voicebox generation {gen_id} timed out after {self._timeout_s:g}s (last status: {status!r})")
            time.sleep(self._poll_every)

        r = self._client.get(f"/audio/{gen_id}")
        r.raise_for_status()
        audio = r.content
        if duration is None:
            duration = _wav_seconds(audio)
        tmp = out_wav.with_suffix(out_wav.suffix + ".part")
        tmp.write_bytes(audio)
        tmp.replace(out_wav)
        return TTSResult(
            path=out_wav,
            duration_s=float(duration or 0.0),
            seconds_taken=time.monotonic() - started,
            engine=voice.engine,
        )


def _wav_seconds(data: bytes) -> float:
    try:
        with wave.open(io.BytesIO(data)) as w:
            return w.getnframes() / w.getframerate()
    except wave.Error:
        return 0.0

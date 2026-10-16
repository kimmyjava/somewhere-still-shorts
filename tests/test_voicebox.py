"""Fast VoiceboxTTS tests (httpx.MockTransport, no real Voicebox)."""
import json

import httpx
import pytest

from shorts.tts.base import VoiceSpec
from shorts.tts.voicebox import DEFAULT_BASE_URL, VoiceboxError, VoiceboxTTS

PROFILE_ID = "ac52122c-5b02-4c66-b00d-ba5bb47b65f7"


def make_tts(handler, **kwargs) -> VoiceboxTTS:
    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://voicebox.test")
    return VoiceboxTTS(client=client, **kwargs)


def test_default_base_url_is_local_only():
    assert DEFAULT_BASE_URL == "http://127.0.0.1:17493"


def test_synthesize_success(tmp_path):
    seen = {}
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.url.path == "/generate":
            seen.update(json.loads(request.content))
            return httpx.Response(200, json={"id": "gen-1"})
        if request.url.path == "/history/gen-1":
            return httpx.Response(200, json={"id": "gen-1", "status": "completed", "duration": 1.5})
        if request.url.path == "/audio/gen-1":
            return httpx.Response(200, content=b"RIFFfake-wav-bytes")
        return httpx.Response(404)

    out = tmp_path / "vo.wav"
    result = make_tts(handler).synthesize("The kettle hums.", VoiceSpec(profile_id=PROFILE_ID), out)

    assert out.exists()
    assert out.read_bytes() == b"RIFFfake-wav-bytes"
    assert list(tmp_path.glob("*.part")) == []
    assert result.path == out
    assert result.duration_s == 1.5
    assert result.engine == "qwen"
    assert result.seconds_taken >= 0.0
    assert calls == [("POST", "/generate"), ("GET", "/history/gen-1"), ("GET", "/audio/gen-1")]
    assert seen["profile_id"] == PROFILE_ID
    assert seen["language"] == "en"
    assert seen["engine"] == "qwen"
    assert seen["model_size"] == "1.7B"
    assert seen["seed"] == 42


def test_synthesize_failed_raises_with_error_text(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/generate":
            return httpx.Response(200, json={"id": "gen-9"})
        if request.url.path == "/history/gen-9":
            return httpx.Response(200, json={"id": "gen-9", "status": "failed", "error": "engine qwen crashed"})
        return httpx.Response(404)

    with pytest.raises(VoiceboxError, match="engine qwen crashed"):
        make_tts(handler).synthesize("hello", VoiceSpec(profile_id=PROFILE_ID), tmp_path / "vo.wav")


def test_synthesize_timeout_raises(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/generate":
            return httpx.Response(200, json={"id": "gen-1"})
        return httpx.Response(200, json={"id": "gen-1", "status": "processing"})

    with pytest.raises(VoiceboxError, match="timed out"):
        make_tts(handler, poll_every=0.01, timeout_s=0.05).synthesize(
            "hello", VoiceSpec(profile_id=PROFILE_ID), tmp_path / "vo.wav")


def test_health_false_when_status_not_healthy():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "starting"})

    assert make_tts(handler).health() is False


def test_health_false_on_connection_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    assert make_tts(handler).health() is False


@pytest.mark.slow
def test_real_voicebox_one_sentence(tmp_path):
    tts = VoiceboxTTS()
    if not tts.health():
        pytest.skip("Voicebox not running on 127.0.0.1:17493")
    result = tts.synthesize(
        "Rain taps the window while the kettle warms.",
        VoiceSpec(profile_id=PROFILE_ID),
        tmp_path / "vo.wav",
    )
    assert result.path.exists()
    assert result.duration_s > 0
    assert result.seconds_taken > 0

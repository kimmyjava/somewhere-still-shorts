"""Fast image tests: prompt building and the Cloudflare call via httpx.MockTransport (no network)."""
import base64
import json

import httpx
import pytest

from shorts.images import (STYLE_PREFIX, STYLE_SUFFIX, MODEL, ImageError, bg_name, build_prompt,
                           generate_bg, get_bg)

ACCOUNT = "acct-123"
TOKEN = "tok-secret-9876"
FAKE_JPG = base64.b64encode(b"fakejpg-bytes").decode()
PROMPT = "  a rainy street with warm lamps  "


def mock_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def ok_handler(request: httpx.Request) -> httpx.Response:
    body = request.read()
    assert request.headers["Authorization"] == f"Bearer {TOKEN}"
    assert b'name="prompt"' in body
    assert b'name="width"' in body
    assert b'name="height"' in body
    assert b'name="input_image_0"' in body
    assert STYLE_PREFIX.encode() in body
    return httpx.Response(200, json={"result": {"image": FAKE_JPG}, "success": True})


def test_build_prompt_wraps_and_strips():
    assert build_prompt(PROMPT) == STYLE_PREFIX + "a rainy street with warm lamps" + STYLE_SUFFIX


def test_bg_name_is_stable_hash():
    assert bg_name("a street") == bg_name("  a   street ")
    assert bg_name("a street") != bg_name("a kitchen")
    assert bg_name("a street").startswith("gen-")
    assert len(bg_name("a street")) == 16


def test_generate_bg_success_writes_file(tmp_path):
    out = tmp_path / "gen" / "pic.jpg"
    generate_bg(build_prompt(PROMPT), out, ACCOUNT, TOKEN, client=mock_client(ok_handler))
    assert out.read_bytes() == b"fakejpg-bytes"


def test_top_level_image_fallback(tmp_path):
    def handler(request):
        return httpx.Response(200, json={"image": FAKE_JPG})

    out = tmp_path / "x.jpg"
    generate_bg("p", out, ACCOUNT, TOKEN, client=mock_client(handler))
    assert out.read_bytes() == b"fakejpg-bytes"


def test_get_bg_writes_library_and_index(tmp_path):
    lib = tmp_path / "library"
    name = get_bg(PROMPT, ACCOUNT, TOKEN, client=mock_client(ok_handler), library=lib)
    assert name == bg_name(PROMPT)
    assert (lib / f"{name}.jpg").read_bytes() == b"fakejpg-bytes"
    lines = (lib / "index.jsonl").read_text(encoding="utf-8").splitlines()
    entry = json.loads(lines[-1])
    assert entry["file"] == f"{name}.jpg"
    assert entry["prompt"] == build_prompt(PROMPT)
    assert entry["model"] == MODEL
    assert entry["created"]


def test_get_bg_reuses_without_new_http_call(tmp_path):
    calls = []

    def counting(request):
        calls.append(1)
        return ok_handler(request)

    lib = tmp_path / "library"
    first = get_bg(PROMPT, ACCOUNT, TOKEN, client=mock_client(counting), library=lib)
    second = get_bg(PROMPT, ACCOUNT, TOKEN, client=mock_client(counting), library=lib)
    assert first == second == bg_name(PROMPT)
    assert len(calls) == 1


def test_http_500_twice_raises_image_error(tmp_path):
    calls = []

    def failing(request):
        calls.append(1)
        return httpx.Response(500, json={"errors": [{"code": 9999, "message": "neuron limit reached"}]})

    with pytest.raises(ImageError, match="neuron limit reached"):
        generate_bg("p", tmp_path / "x.jpg", ACCOUNT, TOKEN, client=mock_client(failing))
    assert len(calls) == 2
    assert not (tmp_path / "x.jpg").exists()


def test_timeout_twice_raises_image_error(tmp_path):
    calls = []

    def slow(request):
        calls.append(1)
        raise httpx.ConnectTimeout("too slow", request=request)

    with pytest.raises(ImageError, match="timed out"):
        generate_bg("p", tmp_path / "x.jpg", ACCOUNT, TOKEN, client=mock_client(slow))
    assert len(calls) == 2


def test_http_4xx_raises_once_without_retry(tmp_path):
    calls = []

    def unauthorized(request):
        calls.append(1)
        return httpx.Response(403, json={"errors": [{"message": "authentication error"}]})

    with pytest.raises(ImageError, match="authentication error"):
        generate_bg("p", tmp_path / "x.jpg", ACCOUNT, TOKEN, client=mock_client(unauthorized))
    assert len(calls) == 1


@pytest.mark.parametrize("mode", ["timeout", "http500", "http403", "no_image"])
def test_token_never_appears_in_error(tmp_path, mode):
    def handler(request):
        if mode == "timeout":
            raise httpx.ConnectTimeout("t", request=request)
        if mode == "http500":
            return httpx.Response(500, json={"errors": [{"message": "boom"}]})
        if mode == "http403":
            return httpx.Response(403, json={"errors": [{"message": "denied"}]})
        return httpx.Response(200, json={"result": {}, "success": False})

    with pytest.raises(ImageError) as excinfo:
        generate_bg("p", tmp_path / "x.jpg", ACCOUNT, TOKEN, client=mock_client(handler))
    assert TOKEN not in str(excinfo.value)
    assert not (tmp_path / "x.jpg").exists()

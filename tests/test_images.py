"""Fast image tests: prompt building and the Cloudflare call via httpx.MockTransport (no network)."""
import base64
import json

import httpx
import pytest

from shorts.images import (STYLE_PREFIX, STYLE_REFS, STYLE_SUFFIX, MODEL, ImageError, bg_name,
                           build_prompt, generate_bg, get_bg, pick_style_ref)

ACCOUNT = "acct-123"
TOKEN = "tok-secret-9876"
FAKE_JPG = base64.b64encode(b"fakejpg-bytes").decode()
PROMPT = "  a rainy street with warm lamps  "
NEUTRAL = "a quiet room with soft light"


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
    assert bg_name("a street", "books") == bg_name("  a   street ", "books")
    assert bg_name("a street", "books") != bg_name("a kitchen", "books")
    assert bg_name("a street", "books").startswith("gen-")
    assert len(bg_name("a street", "books")) == 16


def test_bg_name_changes_with_style_ref():
    names = {ref: bg_name("the same words", ref) for ref in ("books", "kitchen", "street")}
    assert len(set(names.values())) == 3


@pytest.mark.parametrize("prompt,expected", [
    ("a stove and a mug on the counter", "kitchen"),
    ("Cozy KITCHEN late at night", "kitchen"),
    ("an old cafe table by the window", "kitchen"),
    ("the kettle hums", "kitchen"),
    ("rain on a quiet street", "street"),
    ("the road out of town", "street"),
    ("garden gate under the sky", "street"),
    ("car lights on the porch", "street"),
    ("a walk in the park", "street"),
])
def test_pick_style_ref_keywords(prompt, expected):
    assert pick_style_ref(prompt, 0) == expected


@pytest.mark.parametrize("index,expected", [
    (0, "books"), (1, "kitchen"), (2, "street"), (3, "books"), (4, "kitchen"), (5, "street"),
])
def test_pick_style_ref_rotates_by_index(index, expected):
    assert pick_style_ref(NEUTRAL, index) == expected


def test_generate_bg_sends_chosen_style_ref(tmp_path):
    def handler(request):
        body = request.read()
        assert b'name="input_image_0"' in body
        assert b"style-ref-kitchen.jpg" in body
        return httpx.Response(200, json={"result": {"image": FAKE_JPG}})

    out = tmp_path / "x.jpg"
    generate_bg("p", out, ACCOUNT, TOKEN, client=mock_client(handler), style_ref=STYLE_REFS["kitchen"])
    assert out.read_bytes() == b"fakejpg-bytes"


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
    assert name == bg_name(PROMPT, "street")
    assert (lib / f"{name}.jpg").read_bytes() == b"fakejpg-bytes"
    lines = (lib / "index.jsonl").read_text(encoding="utf-8").splitlines()
    entry = json.loads(lines[-1])
    assert entry["file"] == f"{name}.jpg"
    assert entry["prompt"] == build_prompt(PROMPT)
    assert entry["model"] == MODEL
    assert entry["style_ref"] == "street"
    assert entry["created"]


def test_get_bg_reuses_without_new_http_call(tmp_path):
    calls = []

    def counting(request):
        calls.append(1)
        return ok_handler(request)

    lib = tmp_path / "library"
    first = get_bg(PROMPT, ACCOUNT, TOKEN, client=mock_client(counting), library=lib)
    second = get_bg(PROMPT, ACCOUNT, TOKEN, client=mock_client(counting), library=lib)
    assert first == second == bg_name(PROMPT, "street")
    assert len(calls) == 1


def test_same_prompt_other_ref_is_a_different_picture(tmp_path):
    calls = []

    def counting(request):
        calls.append(1)
        return ok_handler(request)

    lib = tmp_path / "library"
    n0 = get_bg(NEUTRAL, ACCOUNT, TOKEN, client=mock_client(counting), library=lib, index=0)
    n1 = get_bg(NEUTRAL, ACCOUNT, TOKEN, client=mock_client(counting), library=lib, index=1)
    assert n0 == bg_name(NEUTRAL, "books")
    assert n1 == bg_name(NEUTRAL, "kitchen")
    assert n0 != n1
    assert len(calls) == 2
    entries = [json.loads(line) for line in (lib / "index.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [e["style_ref"] for e in entries] == ["books", "kitchen"]


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

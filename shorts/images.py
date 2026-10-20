"""AI scene backgrounds: Cloudflare Workers AI FLUX.2 klein 4B in the Somewhere Still style.

build_prompt(bg_prompt) -> the style-wrapped prompt sent to the model (one style ref image from
                           STYLE_REFS goes with it as image 0 so every picture shares the look).
pick_style_ref(bg_prompt, index) -> "books" / "kitchen" / "street": keywords choose the ref,
                           otherwise the refs rotate by scene index so scenes do not all look alike.
generate_bg(prompt, out_path, account_id, token, client=None, style_ref=None) -> one API call (one
                           retry on timeout or HTTP 5xx), decodes result.image (or top-level image).
get_bg(bg_prompt, account_id, token, client=None, library=None, index=0) -> library name for the
                           prompt+ref pair, generating the picture once per pair.
Library: C:/shorts/bg-library/<gen-hash>.jpg plus index.jsonl (file, prompt, model, style_ref,
created). The hash covers the prompt AND the ref name. Error messages carry Cloudflare's error
text and never the token.
"""
import base64
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

import httpx

MODEL = "@cf/black-forest-labs/flux-2-klein-4b"
WIDTH = 768
HEIGHT = 1344
LIBRARY = Path("C:/shorts/bg-library")
REPO = Path(__file__).resolve().parents[1]
STYLE_REFS = {
    "books": REPO / "assets" / "bg" / "style-ref.jpg",
    "kitchen": REPO / "assets" / "bg" / "style-ref-kitchen.jpg",
    "street": REPO / "assets" / "bg" / "style-ref-street.jpg",
}
REF_ROTATION = ("books", "kitchen", "street")
KITCHEN_WORDS = ("kitchen", "stove", "kettle", "table", "mug", "cafe")
STREET_WORDS = ("street", "outside", "road", "town", "garden", "porch", "sky", "park", "car")
API_ROOT = "https://api.cloudflare.com/client/v4/accounts"
TIMEOUT_S = 120.0

STYLE_PREFIX = (
    "Detailed cozy digital painting in the exact art style and colour palette of image 0 "
    "(copy only the style and colours, not its objects or layout): rich warm amber light and deep "
    "cozy shadows, soft glowing lights, painterly storybook details, nostalgic and calm. Scene: "
)
STYLE_SUFFIX = (
    " Full vertical composition filled to the bottom with cozy details. "
    "No people, no animals, no text, no letters."
)


class ImageError(Exception):
    """A background picture could not be generated (the message never contains the token)."""


def build_prompt(bg_prompt: str) -> str:
    return STYLE_PREFIX + bg_prompt.strip() + STYLE_SUFFIX


def bg_name(bg_prompt: str, ref: str = "books") -> str:
    normalized = " ".join(bg_prompt.split())
    return "gen-" + hashlib.sha256(f"{normalized}|{ref}".encode("utf-8")).hexdigest()[:12]


def _mentions(bg_prompt: str, words: tuple[str, ...]) -> bool:
    low = bg_prompt.lower()
    return any(re.search(rf"\b{re.escape(word)}\b", low) for word in words)


def pick_style_ref(bg_prompt: str, index: int) -> str:
    if _mentions(bg_prompt, KITCHEN_WORDS):
        return "kitchen"
    if _mentions(bg_prompt, STREET_WORDS):
        return "street"
    return REF_ROTATION[index % len(REF_ROTATION)]


def _cloudflare_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return f"HTTP {response.status_code} from Cloudflare"
    messages: list[str] = []
    if isinstance(payload, dict):
        for err in payload.get("errors") or []:
            if isinstance(err, dict) and err.get("message"):
                messages.append(str(err["message"]))
            else:
                messages.append(str(err))
    if messages:
        return "; ".join(messages)
    return f"HTTP {response.status_code} from Cloudflare"


def _image_b64(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return ""
    result = payload.get("result") if isinstance(payload, dict) else None
    if isinstance(result, dict) and isinstance(result.get("image"), str):
        return result["image"]
    if isinstance(payload, dict) and isinstance(payload.get("image"), str):
        return payload["image"]
    return ""


def generate_bg(prompt: str, out_path: Path, account_id: str, token: str, client=None,
                style_ref: Path | None = None) -> Path:
    out_path = Path(out_path)
    url = f"{API_ROOT}/{account_id}/ai/run/{MODEL}"
    form = {"prompt": prompt, "width": str(WIDTH), "height": str(HEIGHT)}
    ref_path = Path(style_ref) if style_ref is not None else STYLE_REFS["books"]
    files = {"input_image_0": (ref_path.name, ref_path.read_bytes(), "image/jpeg")}
    headers = {"Authorization": f"Bearer {token}"}
    own = client is None
    http = client if client is not None else httpx.Client(timeout=TIMEOUT_S)
    try:
        problem = "Cloudflare never answered"
        for _ in (1, 2):
            try:
                response = http.post(url, headers=headers, data=form, files=files)
            except httpx.TimeoutException:
                problem = f"timed out after {TIMEOUT_S:.0f}s"
                continue
            except httpx.HTTPError as exc:
                raise ImageError(f"request failed ({type(exc).__name__})") from None
            if response.status_code >= 500:
                problem = _cloudflare_message(response)
                continue
            image = _image_b64(response)
            if not image:
                raise ImageError(f"no image in the Cloudflare response; {_cloudflare_message(response)}")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(base64.b64decode(image))
            return out_path
        raise ImageError(problem)
    finally:
        if own:
            http.close()


def get_bg(bg_prompt: str, account_id: str, token: str, client=None, library: Path | None = None,
           index: int = 0) -> str:
    library = Path(library) if library is not None else LIBRARY
    ref = pick_style_ref(bg_prompt, index)
    name = bg_name(bg_prompt, ref)
    out = library / f"{name}.jpg"
    if out.is_file():
        return name
    library.mkdir(parents=True, exist_ok=True)
    full_prompt = build_prompt(bg_prompt)
    generate_bg(full_prompt, out, account_id, token, client, style_ref=STYLE_REFS[ref])
    entry = {"file": out.name, "prompt": full_prompt, "model": MODEL, "style_ref": ref,
             "created": datetime.now().isoformat(timespec="seconds")}
    with (library / "index.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return name

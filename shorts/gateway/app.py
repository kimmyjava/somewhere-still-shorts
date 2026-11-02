"""Local job gateway: n8n posts briefs, one worker thread runs make_short.

Bound to 127.0.0.1:8787 only (tools/gateway.py). Auth: X-API-Key header vs the
SHORTS_API_KEY env var (>= 32 chars; never logged or returned). Voicebox stays private.
"""
import hmac
import json
import os
import queue
import re
import shutil
import sys
import threading
from datetime import datetime
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse

from shorts.brief import BriefError, load_brief
from shorts.images import data_root
from shorts.runner import StepError, run


def voicebox_root() -> str:
    return (os.environ.get("SHORTS_VOICEBOX_URL", "").strip()
            or "http://127.0.0.1:17493/").rstrip("/") + "/"


JOB_ID_RE = re.compile(r"^[a-z0-9-]{1,80}$")
MAX_BODY = 65536
REPO_ROOT = Path(__file__).resolve().parents[2]
JOB_TIMEOUT_S = 14400


def voicebox_up() -> bool:
    try:
        with httpx.Client(timeout=2.0) as client:
            r = client.get(voicebox_root())
        return r.status_code == 200
    except httpx.HTTPError:
        return False


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _write_status(job_dir: Path, **fields) -> None:
    path = job_dir / "status.json"
    data = {}
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            data = {}
    data.update(fields)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def create_app(jobs_root=None) -> FastAPI:
    key = os.environ.get("SHORTS_API_KEY", "")
    if len(key) < 32:
        raise RuntimeError(
            "SHORTS_API_KEY is missing or shorter than 32 characters - refusing to start the gateway")
    jobs_root = Path(jobs_root) if jobs_root is not None else data_root() / "jobs"
    jobs_root.mkdir(parents=True, exist_ok=True)

    for status_path in jobs_root.glob("*/status.json"):
        try:
            old = json.loads(status_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if old.get("status") == "running":
            _write_status(status_path.parent, status="failed", finished=_now(),
                          error="gateway restarted while the job was running")

    app = FastAPI(title="shorts-worker gateway", docs_url=None, redoc_url=None)
    jobs: "queue.Queue[str]" = queue.Queue()

    def require_key(x_api_key: str = Header(default="")) -> None:
        if not hmac.compare_digest(x_api_key, key):
            raise HTTPException(status_code=401, detail="invalid or missing API key")

    @app.get("/health")
    def health():
        return {"ok": True, "voicebox": voicebox_up()}

    @app.post("/jobs", status_code=202, dependencies=[Depends(require_key)])
    async def create_job(request: Request):
        body = await request.body()
        if len(body) > MAX_BODY:
            raise HTTPException(status_code=413, detail="brief too large (max 64 KB)")
        try:
            data = json.loads(body)
        except ValueError:
            raise HTTPException(status_code=422, detail="body is not valid JSON")
        if not isinstance(data, dict):
            raise HTTPException(status_code=422, detail="body must be a JSON object")
        job_id = f"{data.get('slug', '')}-{datetime.now():%Y%m%d-%H%M%S}"
        data["slug"] = job_id
        job_dir = jobs_root / job_id
        (job_dir / "logs").mkdir(parents=True, exist_ok=True)
        brief_path = job_dir / "brief.json"
        brief_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        try:
            load_brief(brief_path)
        except BriefError as e:
            shutil.rmtree(job_dir, ignore_errors=True)
            raise HTTPException(status_code=422, detail=str(e))
        _write_status(job_dir, status="queued", created=_now(), started=None, finished=None, error=None)
        jobs.put(job_id)
        return {"job_id": job_id, "status": "queued"}

    def worker():
        while True:
            job_id = jobs.get()
            job_dir = jobs_root / job_id
            try:
                _write_status(job_dir, status="running", started=_now())
                run([sys.executable, "-m", "tools.make_short",
                     "--brief", str(job_dir / "brief.json"), "--jobs-root", str(jobs_root)],
                    cwd=REPO_ROOT, log_path=job_dir / "logs" / "gateway.log", timeout_s=JOB_TIMEOUT_S)
                _write_status(job_dir, status="done", finished=_now())
            except StepError as e:
                _write_status(job_dir, status="failed", finished=_now(), error=str(e))
            except Exception as e:
                _write_status(job_dir, status="failed", finished=_now(),
                              error=f"{type(e).__name__}: {e}")
            finally:
                jobs.task_done()

    threading.Thread(target=worker, daemon=True, name="gateway-worker").start()

    @app.get("/jobs/{job_id}", dependencies=[Depends(require_key)])
    def get_job(job_id: str):
        if not JOB_ID_RE.match(job_id):
            raise HTTPException(status_code=400, detail="invalid job id")
        path = jobs_root / job_id / "status.json"
        if not path.is_file():
            raise HTTPException(status_code=404, detail="unknown job")
        return json.loads(path.read_text(encoding="utf-8"))

    @app.get("/jobs/{job_id}/video", dependencies=[Depends(require_key)])
    def get_video(job_id: str):
        if not JOB_ID_RE.match(job_id):
            raise HTTPException(status_code=400, detail="invalid job id")
        path = jobs_root / job_id / f"{job_id}.mp4"
        if not path.is_file():
            raise HTTPException(status_code=404, detail="video not ready")
        return FileResponse(path, media_type="video/mp4", filename=path.name)

    return app

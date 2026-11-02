"""Fast gateway tests: TestClient + fake runner, no real make_short, no network."""
import json
import os
import sys
import threading
import time
from pathlib import Path

import pytest

os.environ.setdefault("SHORTS_API_KEY", "test-key-" + "0" * 32)

from fastapi.testclient import TestClient

import shorts.gateway.app as gw
from shorts.gateway.app import create_app
from shorts.runner import StepError

KEY = os.environ["SHORTS_API_KEY"]
H = {"X-API-Key": KEY}
FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "brief_kitchen.json"


def brief():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture()
def env(tmp_path, monkeypatch):
    state = {"calls": [], "gate": threading.Event(), "returncode": 0}

    def fake_run(cmd, cwd=None, log_path=None, timeout_s=600):
        state["calls"].append(cmd)
        log = "fake gateway log line 1\nfake gateway log line 2\n"
        Path(log_path).write_text(log, encoding="utf-8")
        state["gate"].wait(timeout=10)
        if state["returncode"] != 0:
            raise StepError(
                f"step failed with exit code {state['returncode']}: {' '.join(cmd)} (log: {log_path})\n{log}")
        return log

    monkeypatch.setattr(gw, "run", fake_run)
    monkeypatch.setattr(gw, "voicebox_up", lambda: True)
    app = create_app(jobs_root=tmp_path / "jobs")
    return {"client": TestClient(app), "jobs": tmp_path / "jobs", "state": state}


def wait_status(env, job_id, want, timeout=5.0):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        r = env["client"].get(f"/jobs/{job_id}", headers=H)
        last = r
        if r.status_code == 200 and r.json().get("status") == want:
            return r.json()
        time.sleep(0.05)
    pytest.fail(f"job never reached {want!r} (last: {last.text if last else None})")


def test_health_needs_no_key(env):
    r = env["client"].get("/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "voicebox": True}


def test_missing_or_wrong_key_rejected(env):
    assert env["client"].post("/jobs", json=brief()).status_code == 401
    assert env["client"].get("/jobs/some-job", headers={"X-API-Key": "wrong" + KEY}).status_code == 401
    assert env["client"].get("/jobs/some-job/video").status_code == 401


def test_bad_brief_422_and_folder_removed(env):
    d = brief()
    d["scenes"] = []
    r = env["client"].post("/jobs", json=d, headers=H)
    assert r.status_code == 422
    assert "0 scenes" in r.json()["detail"]
    assert list(env["jobs"].iterdir()) == []


def test_extra_scene_fields_accepted(env):
    d = brief()
    d["scenes"][0]["bg_prompt"] = "cozy kitchen, warm light"
    r = env["client"].post("/jobs", json=d, headers=H)
    assert r.status_code == 202
    assert r.json()["status"] == "queued"


def test_oversized_body_413(env):
    d = brief()
    d["junk"] = "x" * 70000
    assert env["client"].post("/jobs", json=d, headers=H).status_code == 413


def test_invalid_json_422(env):
    assert env["client"].post("/jobs", content=b"{nope", headers=H).status_code == 422


def test_good_brief_runs_to_done(env):
    env["state"]["gate"].set()
    r = env["client"].post("/jobs", json=brief(), headers=H)
    assert r.status_code == 202
    job_id = r.json()["job_id"]
    assert job_id.startswith("kitchen-table-")
    assert r.json()["status"] == "queued"

    data = wait_status(env, job_id, "done")
    assert data["error"] is None
    assert data["created"] and data["started"] and data["finished"]

    cmd = env["state"]["calls"][0]
    assert cmd[:5] == [sys.executable, "-m", "tools.make_short", "--brief",
                       str(env["jobs"] / job_id / "brief.json")]
    assert cmd[5:] == ["--jobs-root", str(env["jobs"])]
    saved = json.loads((env["jobs"] / job_id / "brief.json").read_text(encoding="utf-8"))
    assert saved["slug"] == job_id


def test_failed_job_status_has_log_tail(env):
    env["state"]["returncode"] = 3
    env["state"]["gate"].set()
    job_id = env["client"].post("/jobs", json=brief(), headers=H).json()["job_id"]
    data = wait_status(env, job_id, "failed")
    assert "exit code 3" in data["error"]
    assert "fake gateway log line" in data["error"]
    assert data["finished"]


def test_video_404_until_done(env):
    job_id = env["client"].post("/jobs", json=brief(), headers=H).json()["job_id"]
    wait_status(env, job_id, "running")
    assert env["client"].get(f"/jobs/{job_id}/video", headers=H).status_code == 404
    env["state"]["gate"].set()
    wait_status(env, job_id, "done")
    assert env["client"].get(f"/jobs/{job_id}/video", headers=H).status_code == 404


def test_bad_job_id_400(env):
    for bad in ("UPPER", "a_b", "x.y"):
        assert env["client"].get(f"/jobs/{bad}", headers=H).status_code == 400
        assert env["client"].get(f"/jobs/{bad}/video", headers=H).status_code == 400


def test_unknown_job_404(env):
    assert env["client"].get("/jobs/s01-nope", headers=H).status_code == 404


def test_startup_marks_running_jobs_failed(tmp_path, monkeypatch):
    job = tmp_path / "jobs" / "old-job-20260101-000000"
    job.mkdir(parents=True)
    (job / "status.json").write_text(json.dumps({"status": "running"}), encoding="utf-8")

    def fake_run(cmd, cwd=None, log_path=None, timeout_s=600):
        Path(log_path).write_text("x\n", encoding="utf-8")
        return 0

    monkeypatch.setattr(gw, "run", fake_run)
    monkeypatch.setattr(gw, "voicebox_up", lambda: True)
    client = TestClient(create_app(jobs_root=tmp_path / "jobs"))
    r = client.get("/jobs/old-job-20260101-000000", headers=H)
    assert r.status_code == 200
    assert r.json()["status"] == "failed"
    assert "restarted" in r.json()["error"]


def test_create_app_refuses_without_or_short_key(tmp_path, monkeypatch):
    monkeypatch.delenv("SHORTS_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="SHORTS_API_KEY"):
        create_app(jobs_root=tmp_path / "jobs")
    monkeypatch.setenv("SHORTS_API_KEY", "too-short")
    with pytest.raises(RuntimeError, match="SHORTS_API_KEY"):
        create_app(jobs_root=tmp_path / "jobs")


def test_gateway_cli_host_defaults_loopback(monkeypatch, tmp_path):
    """--host defaults to 127.0.0.1; --host 0.0.0.0 reaches uvicorn (published-port mode)."""
    import tools.gateway as cli

    seen = {}
    monkeypatch.setenv("SHORTS_API_KEY", KEY)
    monkeypatch.setattr(cli, "create_app", lambda jobs_root=None: jobs_root)
    monkeypatch.setattr(cli.uvicorn, "run",
                        lambda app, host, port: seen.update(host=host, port=port, jobs=app))

    cli.main([])
    assert seen["host"] == "127.0.0.1" and seen["port"] == 8787 and seen["jobs"] is None
    jobs = tmp_path / "jobs"
    cli.main(["--host", "0.0.0.0", "--port", "9001", "--jobs-root", str(jobs)])
    assert seen["host"] == "0.0.0.0" and seen["port"] == 9001 and seen["jobs"] == jobs

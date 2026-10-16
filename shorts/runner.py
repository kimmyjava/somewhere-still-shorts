"""Subprocess runner with per-step logs, timeouts and a Windows process-tree kill."""
import subprocess
import sys
from pathlib import Path

TAIL_LINES = 20


class StepError(Exception):
    """A pipeline step failed (non-zero exit or timeout); the message carries the last log lines."""


def _tail(out: str) -> str:
    return "\n".join((out or "").splitlines()[-TAIL_LINES:])


def run(cmd, cwd=None, log_path=None, timeout_s=600) -> str:
    cmd = [str(c) for c in cmd]
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    shell = sys.platform == "win32" and cmd[0] == "npx"
    proc = subprocess.Popen(
        cmd,
        cwd=None if cwd is None else str(cwd),
        shell=shell,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    try:
        out, _ = proc.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True, check=False)
        else:
            proc.kill()
        out, _ = proc.communicate()
        log_path.write_text(out or "", encoding="utf-8")
        raise StepError(f"step timed out after {timeout_s}s: {' '.join(cmd)} (log: {log_path})\n{_tail(out)}")
    log_path.write_text(out or "", encoding="utf-8")
    if proc.returncode != 0:
        raise StepError(
            f"step failed with exit code {proc.returncode}: {' '.join(cmd)} (log: {log_path})\n{_tail(out)}")
    return out

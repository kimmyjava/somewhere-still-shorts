"""Fast runner tests (tiny real subprocesses, no Voicebox/node/render)."""
import sys
from pathlib import Path

import pytest

from shorts.runner import StepError, run


def test_run_writes_log_and_returns_output(tmp_path):
    log = tmp_path / "logs" / "ok.log"
    out = run([sys.executable, "-c", "print('hello from step')"], cwd=tmp_path, log_path=log)
    assert "hello from step" in out
    assert "hello from step" in log.read_text(encoding="utf-8")


def test_failing_command_raises_step_error_with_log_tail(tmp_path):
    log = tmp_path / "fail.log"
    with pytest.raises(StepError) as err:
        run([sys.executable, "-c", "print('line1'); import sys; print('boom-line', file=sys.stderr); sys.exit(3)"],
            cwd=tmp_path, log_path=log)
    msg = str(err.value)
    assert "exit code 3" in msg
    assert "boom-line" in msg
    assert log.exists()
    assert "boom-line" in log.read_text(encoding="utf-8")


def test_timeout_raises_step_error(tmp_path):
    with pytest.raises(StepError, match="timed out after"):
        run([sys.executable, "-c", "import time; time.sleep(60)"],
            cwd=tmp_path, log_path=tmp_path / "slow.log", timeout_s=1)

"""Start the local job gateway. Binds 127.0.0.1 ONLY - expose via a Cloudflare Tunnel, never 0.0.0.0.

usage: C:/shorts/venv/Scripts/python tools/gateway.py [--jobs-root C:/shorts/jobs] [--port 8787]
Needs SHORTS_API_KEY (>= 32 chars) in the environment.
"""
import argparse
import sys
from pathlib import Path

import uvicorn

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from shorts.gateway.app import create_app


def main() -> None:
    ap = argparse.ArgumentParser(description="Run the shorts-worker job gateway on 127.0.0.1 only.")
    ap.add_argument("--jobs-root", default="C:/shorts/jobs", help="folder for all job output")
    ap.add_argument("--port", type=int, default=8787)
    args = ap.parse_args()
    uvicorn.run(create_app(jobs_root=Path(args.jobs_root)), host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()

"""Start the local job gateway. Binds 127.0.0.1 ONLY - expose via a Cloudflare Tunnel, never 0.0.0.0.

usage: python tools/gateway.py [--jobs-root <dir>] [--port 8787]
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
    ap.add_argument("--jobs-root", default=None, help="folder for all job output (default: SHORTS_DATA_ROOT/jobs)")
    ap.add_argument("--port", type=int, default=8787)
    args = ap.parse_args()
    jobs_root = Path(args.jobs_root) if args.jobs_root else None
    uvicorn.run(create_app(jobs_root=jobs_root), host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()

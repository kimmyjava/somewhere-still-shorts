"""Start the local job gateway. Binds 127.0.0.1 by default - expose via a tunnel or --host with a
published port, never without SHORTS_API_KEY.

usage: python tools/gateway.py [--jobs-root <dir>] [--host 127.0.0.1] [--port 8787]
Needs SHORTS_API_KEY (>= 32 chars) in the environment.
"""
import argparse
import sys
from pathlib import Path

import uvicorn

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from shorts.gateway.app import create_app


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="Run the shorts-worker job gateway.")
    ap.add_argument("--jobs-root", default=None, help="folder for all job output (default: SHORTS_DATA_ROOT/jobs)")
    ap.add_argument("--host", default="127.0.0.1",
                    help="bind address (default 127.0.0.1; 0.0.0.0 only behind a published port + API key)")
    ap.add_argument("--port", type=int, default=8787)
    args = ap.parse_args(argv)
    jobs_root = Path(args.jobs_root) if args.jobs_root else None
    uvicorn.run(create_app(jobs_root=jobs_root), host=args.host, port=args.port)


if __name__ == "__main__":
    main()

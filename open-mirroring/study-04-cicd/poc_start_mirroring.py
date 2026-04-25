"""Study-04 / Q6: Post-deploy hook to start mirroring.

Fabric deployment pipelines do NOT auto-start mirroring on the target
stage. Run this after a deployment completes (as a CI step) to start
mirroring on the target environment's mirror.

Usage:
    python poc_start_mirroring.py --mirror-id <guid> --workspace-id <guid>

Or via .env:
    BRONZE_MIRROR_ID=<guid>
    FABRIC_WORKSPACE_ID=<guid>
    python poc_start_mirroring.py
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "clients"))

from config import BRONZE_MIRROR_ID, FABRIC_WORKSPACE_ID
from mirror_api import get_mirroring_status, start_mirroring, wait_for_running


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mirror-id", default=BRONZE_MIRROR_ID)
    ap.add_argument("--workspace-id", default=FABRIC_WORKSPACE_ID)
    ap.add_argument("--wait", action="store_true",
                    help="Block until mirror reports Running")
    ap.add_argument("--timeout", type=int, default=300)
    args = ap.parse_args()

    if not args.mirror_id:
        raise SystemExit("mirror_id not provided (flag or BRONZE_MIRROR_ID)")

    before = get_mirroring_status(args.mirror_id, args.workspace_id)
    print(f"Status before: {before}")

    if (before.get("status") or "").lower() == "running":
        print("Already running. Nothing to do.")
        return

    code = start_mirroring(args.mirror_id, args.workspace_id)
    print(f"startMirroring returned HTTP {code}")

    if args.wait:
        final = wait_for_running(args.mirror_id, timeout_s=args.timeout,
                                 workspace_id=args.workspace_id)
        print(f"Status after wait: {final}")


if __name__ == "__main__":
    main()

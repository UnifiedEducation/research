"""Deploy dbt project artifacts to a Fabric lakehouse.

Uploads dbt project files to the lakehouse via fab cp. DuckLake
auto-creates metadata.db on first dbt run; raw tables are read
directly via delta_scan() so no pre-built catalog is needed.

Usage:
    python tools/deploy.py --target dev     # Deploy to DEV lakehouse
    python tools/deploy.py --target prod    # Deploy to PROD lakehouse
"""
import argparse
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".env"))

ROOT = Path(__file__).parent.parent

TARGETS = {
    "dev": {
        "ws_name": "Fabric_BMAD_DEV",
        "lh_name": "DEV_FilmProd_LH2",
    },
    "prod": {
        "ws_name": "Fabric_BMAD_PROD",
        "lh_name": "fea002_data_lh",
    },
}

EXCLUDE_DIRS = {"data", "fabric_items", "__pycache__", "target", "dbt_packages", "logs", "tools", "ontology_changes"}
EXCLUDE_FILES = {".user.yml"}


# -- Helpers -------------------------------------------------------------------

def get_fab_path():
    """Find the fab CLI executable in the current venv or on PATH."""
    venv_fab = Path(sys.prefix) / "Scripts" / "fab.exe"
    if venv_fab.exists():
        return str(venv_fab)
    return shutil.which("fab") or "fab"


def run_command(cmd):
    """Execute a subprocess command and return the result."""
    return subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(ROOT),
    )


def collect_dbt_files():
    """Collect dbt project files to upload."""
    files = []
    for f in ROOT.rglob("*"):
        if not f.is_file():
            continue
        if any(part in EXCLUDE_DIRS for part in f.relative_to(ROOT).parts):
            continue
        if f.name in EXCLUDE_FILES:
            continue
        files.append(f)
    return files


# -- Deploy steps --------------------------------------------------------------

def resolve_target(target_name):
    """Resolve the Fabric workspace/lakehouse path for a target."""
    target = TARGETS[target_name]
    return f"{target['ws_name']}.Workspace/{target['lh_name']}.Lakehouse"


def upload_artifacts(lakehouse):
    """Upload dbt project files to the lakehouse."""
    print("\n=== 1. Upload dbt files ===")
    fab = get_fab_path()
    dbt_files = collect_dbt_files()

    # Create directory tree
    dirs = set()
    for f in dbt_files:
        p = f.relative_to(ROOT).parent
        while p.parts:
            dirs.add(p.as_posix())
            p = p.parent

    run_command([fab, "mkdir", f"{lakehouse}/Files/dbt"])
    for d in sorted(dirs):
        run_command([fab, "mkdir", f"{lakehouse}/Files/dbt/{d}"])

    # Copy files in parallel
    def copy_one(f):
        rel = f.relative_to(ROOT)
        run_command([fab, "cp", rel.as_posix(),
                     f"{lakehouse}/Files/dbt/{rel.as_posix()}", "-f"])

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(copy_one, dbt_files))

    print(f"  Uploaded {len(dbt_files)} dbt files")


# -- Main ----------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deploy dbt artifacts to Fabric lakehouse")
    parser.add_argument("--target", choices=["dev", "prod"], required=True)
    args = parser.parse_args()

    lakehouse = resolve_target(args.target)
    upload_artifacts(lakehouse)

    print("\n=== Deploy complete ===")

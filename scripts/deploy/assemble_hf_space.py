"""Assemble the Hugging Face Docker Space build context: code subset + verified INT8 bundle.

The bundle is verified against the pinned id before it is copied, so the Space only ever
ships the exact release-candidate artifact. Output: artifacts/deploy/hf-space/ (gitignored).
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from verify_bundle import verify_bundle  # noqa: E402

CODE = (
    "packages/resolveit-core",
    "packages/resolveit-frames",
    "apps/api",
    "apps/worker",
    "enterprise",
    "infra/migrations",
)
FILES = ("alembic.ini", "requirements-runtime.txt", "requirements-model.txt", "scripts/bootstrap_db.py")
SKIP = shutil.ignore_patterns("__pycache__", "*.pyc", "tests", ".pytest_cache", ".mypy_cache", "*.egg-info")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=ROOT / "artifacts/release_candidate_bundle")
    parser.add_argument("--expected-id", required=True)
    parser.add_argument("--out", type=Path, default=ROOT / "artifacts/deploy/hf-space")
    args = parser.parse_args()
    verify_bundle(args.bundle, args.expected_id)
    if args.out.exists():
        shutil.rmtree(args.out)
    args.out.mkdir(parents=True)
    for rel in CODE:
        shutil.copytree(ROOT / rel, args.out / rel, ignore=SKIP)
    for rel in FILES:
        (args.out / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, args.out / rel)
    shutil.copytree(args.bundle, args.out / "bundle")
    deploy = ROOT / "infra/hf-space"
    shutil.copy2(deploy / "Dockerfile", args.out / "Dockerfile")
    shutil.copy2(deploy / "entrypoint.sh", args.out / "hfspace_entrypoint.sh")
    shutil.copy2(deploy / "README.md", args.out / "README.md")
    verify_bundle(args.out / "bundle", args.expected_id)
    print({"assembled": str(args.out), "bundle_id": args.expected_id})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

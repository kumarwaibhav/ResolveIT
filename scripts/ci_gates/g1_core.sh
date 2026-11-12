#!/usr/bin/env bash
# Gate G1: core math and contracts. Exits non-zero on any failure.
set -euo pipefail
cd "$(dirname "$0")/../../packages/resolveit-core"
ruff check .
mypy resolveit_core
python -m pytest -q

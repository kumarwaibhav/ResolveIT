"""ResolveIT API on Modal: scale-to-zero ASGI service + scheduled worker sweep.

Deploy with: python scripts/deploy/push_modal.py --bundle-id <id> --web-origin https://...
The verified INT8 bundle is mounted read-only; the API re-verifies it against the pinned id at
startup and falls back to the rule-only bundle if anything is off (never serves an unverified model).
"""

from __future__ import annotations

import os
from pathlib import Path

import modal

_HERE = Path(__file__).resolve()
# Inside the Modal container this file is /root/app.py; local paths only matter at deploy time.
ROOT = _HERE.parents[2] if len(_HERE.parents) > 2 else Path("/")
BUNDLE = Path(os.environ.get("RESOLVEIT_DEPLOY_BUNDLE", ROOT / "artifacts/release_candidate_bundle"))
SKIP = ["**/__pycache__", "**/*.pyc", "**/tests", "**/*.egg-info", "**/.pytest_cache", "**/.mypy_cache"]

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install_from_requirements(str(ROOT / "requirements-runtime.txt"))
    .pip_install_from_requirements(str(ROOT / "requirements-model.txt"))
    .add_local_dir(ROOT / "packages/resolveit-core", "/app/packages/resolveit-core", copy=True, ignore=SKIP)
    .add_local_dir(ROOT / "apps/api", "/app/apps/api", copy=True, ignore=SKIP)
    .run_commands("pip install --no-cache-dir /app/packages/resolveit-core /app/apps/api")
    .env(
        {
            "PYTHONPATH": "/app/apps/api:/app/apps/worker:/app/enterprise",
            "OMP_NUM_THREADS": "2",
            "RESOLVEIT_BUNDLE_DIR": "/app/bundle",
            "RESOLVEIT_ENCODER_THREADS": "2",
            "RESOLVEIT_BUNDLE_ID": os.environ.get("RESOLVEIT_BUNDLE_ID", ""),
            "RESOLVEIT_ALLOWED_ORIGINS": os.environ.get("RESOLVEIT_ALLOWED_ORIGINS", ""),
        }
    )
    .add_local_dir(ROOT / "apps/worker", "/app/apps/worker", ignore=SKIP)
    .add_local_dir(ROOT / "enterprise", "/app/enterprise", ignore=SKIP)
    .add_local_dir(ROOT / "packages/resolveit-frames", "/app/packages/resolveit-frames", ignore=SKIP)
    .add_local_dir(BUNDLE, "/app/bundle")
)

app = modal.App("resolveit-api", image=image)
secret = modal.Secret.from_name("resolveit-prod")


# Same place as the Neon database (AWS Sydney, ap-southeast-2): each ticket makes dozens of DB
# round trips. Modal's broad "ap-southeast" also places containers in Sydney, which put a
# Singapore database ~95 ms away per query (8-10 s per ticket); "au" keeps both in Australia.
REGION = "au"


@app.function(
    secrets=[secret],
    region=REGION,
    routing_region="ap-south",  # HTTPS ingress in Mumbai, near Indian users and Vercel bom1
    cpu=2.0,
    memory=3072,
    min_containers=0,
    scaledown_window=180,  # idle containers stop after 3 min: keeps the demo inside the free monthly credit
    timeout=120,
)
@modal.concurrent(max_inputs=16)
@modal.asgi_app()
def web():  # type: ignore[no-untyped-def]
    from resolveit_api.main import create_app

    return create_app()


@app.function(
    secrets=[secret], region=REGION, cpu=1.0, memory=2048, schedule=modal.Period(hours=1), timeout=300
)
def sweep() -> str:
    """Hourly worker pass: time out unanswered questions, recover unevaluated incidents.

    Hourly, not every few minutes: each run starts a container, and on the Starter plan the
    frequent schedule alone used most of the monthly credit.
    """
    import asyncio

    from resolveit_api.main import create_app
    from resolveit_worker.runner import sweep as run_sweep

    async def once() -> str:
        state = create_app().state
        try:
            return str(await run_sweep(state))
        finally:
            await state.db.dispose()

    return asyncio.run(once())

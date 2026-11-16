# Local synthetic runtime

This stack binds published ports to loopback and uses generated private secrets.
It is a development demonstration. Production OIDC sessions, managed encryption
key lifecycle, operational restore drills and human calibration remain release gates.

## Docker bootstrap

From repository root, with Docker Desktop running:

```powershell
python scripts/local_env.py
python scripts/gpu_guard.py -- docker compose build
docker compose up -d
docker compose ps
```

Open http://127.0.0.1:3000. API readiness: http://127.0.0.1:8000/healthz.
The generated `.env` is ignored. Keep it for restarts: generating new master keys
would make old incident ciphertext unreadable. Never commit or print its values.
On POSIX the generator restricts file permissions; Windows uses inherited workspace
ACLs, which the operator must keep private.

Setup creates least-privilege app/migrator roles, runs Alembic, and seeds a permanent
synthetic tenant. API traffic goes through transaction-mode PgBouncer; worker uses
direct PostgreSQL for session advisory locks. Pool authentication follows official
[PgBouncer configuration](https://www.pgbouncer.org/config). No database port is published.
API and web bind loopback only. Shared-key proxy requires explicit local demo mode;
public hostnames and cross-site browser actions are denied.

Stop without deleting data:

```powershell
docker compose stop
```

The named database volume persists. Do not delete it to fix ordinary startup errors.
Do not rotate `.env` passwords while existing roles retain old passwords; use an
explicit audited database-role rotation. Bootstrap preserves existing roles/keys.

## Native checks

```powershell
uv venv .venv
uv pip install --python .venv/Scripts/python.exe -e "packages/resolveit-core[dev]" -e "apps/api[dev]" psutil types-psutil asyncpg-stubs uvicorn onnx onnxruntime playwright
.venv/Scripts/python.exe -m pytest scripts/tests/test_gpu_guard.py -q
.venv/Scripts/python.exe scripts/ml_smoke.py
```

Heavy checks must use the governor and exclusive heavy-job lock. Phase2 profile
allows RAM<=95.5% while requiring750MiB available; below1024MiB pauses and stops
after3 consecutive low polls. Windowscommit/swap<=88%, VRAM<=85%; GPU pauses
at75C and stops at78C. Training must launch below65C. Training loops
checkpoint between micro-batches. Arbitrary subprocesses are stopped at hard limits;
they cannot promise model-specific checkpoint recovery without cooperative callbacks.

`.githooks/pre-commit` scans staged files for known secret signatures. Local
`core.hooksPath` is configured during this audit; fresh clones should run
`git config --local core.hooksPath .githooks`. The scanner reports paths/counts,
never matching values. It is a bounded signature scan, not proof of secret absence.

## Verification status

See `BUILD_STATE.md` for executed results and blocked gates. Compose syntax passes;
fresh image build and full Compose startup must be executed before calling this
bootstrap verified. A health response proves API process liveness, not dependency
readiness or enterprise deployment fitness.

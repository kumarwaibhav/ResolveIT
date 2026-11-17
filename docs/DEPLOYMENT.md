# Hosted deployment (free tiers): Vercel + Modal + Neon

Live:
- Web: https://resolveit-one.vercel.app (Vercel Hobby, functions in `bom1` Mumbai)
- API: https://kumarwaibhav--resolveit-api-web.ap-south.modal.run (Modal Starter: container in
  `ap-southeast`, HTTPS ingress `ap-south`; scales to zero; worker sweep every 5 min)
- Database: Neon Postgres 16, AWS Singapore (direct endpoint, TLS)

| Piece | Why this host |
|---|---|
| Web | Next.js native; free HTTPS |
| API + model | 315 MB INT8 bundle and ~1.3 GB RAM do not fit Vercel or Cloudflare Workers free limits; HF Docker Spaces now need PRO; Modal's free monthly credit covers demo traffic |
| Postgres | RLS, SQL migrations, advisory locks need Postgres; Neon free suspends compute but wakes itself |

Secrets never enter git or chat: `artifacts/deploy/*.env` (gitignored) feed Modal secrets and Vercel
environment variables directly. The Modal secret is least-privilege: app-role DB URL + master key only.

## Owner sign-ins (one-time)
`vercel login`; `python -m modal setup`; Neon direct owner connection string saved as
`artifacts/deploy/neon.env` (`NEON_OWNER_DSN=...`).

## Deploy / redeploy
```powershell
.venv\Scripts\python.exe scripts\deploy\prod_env.py          # fresh prod secrets, kept on re-run
.venv\Scripts\python.exe scripts\deploy\bootstrap_remote.py  # roles, migrations, synthetic tenant (idempotent)
.venv\Scripts\python.exe scripts\deploy\push_modal.py --bundle-id <id> --web-origin https://resolveit-one.vercel.app
.venv\Scripts\python.exe scripts\deploy\vercel_env.py --api-url <modal url> --origin https://resolveit-one.vercel.app
cd apps\web; vercel deploy --prod --yes
```

## Verify
```powershell
.venv\Scripts\python.exe scripts\showcase_smoke.py <modal url> artifacts\deploy\prod.env
```
Last run 2026-11-17: healthz `int8_trained_synthetic` bundle 968fd32c; clear ticket routed, vague
ticket asked then routed, compound asked, security escalated; ~1 s per ticket warm.

Sign in at https://resolveit-one.vercel.app/login with `RESOLVEIT_API_KEY` from `artifacts/deploy/prod.env`.

## Limits stated honestly
- Cold start after ~3 min idle: first request waits ~15-30 s while the container loads the model.
- Neon free: 0.5 GB; compute auto-suspends (first query after idle ~1 s slower).
- Modal Starter: $30/month free credit with a payment method on file; keep the workspace usage limit at
  $30 so usage past the credit stops the API instead of charging. The worker sweep runs hourly and idle
  containers stop after 3 min to stay inside the credit.
- Synthetic tenant only; real tenants stay shadow-mode. G2 128-token latency target not met.
- `infra/hf-space/` is kept as an alternative host (needs HF PRO).

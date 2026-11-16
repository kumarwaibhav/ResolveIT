# Free hosted deployment (Vercel + Neon + Hugging Face Space)

| Piece | Host | Notes |
|---|---|---|
| Web (Next.js, `apps/web`) | Vercel Hobby | production mode: individual API-key sign-in, HTTPS-only origin |
| Postgres 16 | Neon free tier | direct (non-pooled) endpoint; RLS roles created by bootstrap |
| API + worker + INT8 bundle | Hugging Face Docker Space (cpu-basic, 16 GB) | `infra/hf-space/`; migrates on boot; sleeps after ~48 h idle |

Secrets never enter git or chat: they live in `artifacts/deploy/*.env` (gitignored) and are
written straight into Hugging Face Space secrets and Vercel environment variables.

## One-time sign-ins (owner)
1. `vercel login`
2. Hugging Face account + write token, then `hf auth login`
3. Neon project (neon.tech or Vercel Storage -> Neon). Save the **direct** owner connection string as
   `artifacts/deploy/neon.env` with one line: `NEON_OWNER_DSN=postgresql://...?sslmode=require`

## Deploy
```powershell
.venv\Scripts\python.exe scripts\deploy\prod_env.py                      # fresh prod secrets (kept on re-run)
.venv\Scripts\python.exe scripts\deploy\assemble_hf_space.py --expected-id <bundle id>
# 1) Vercel project first, to learn the HTTPS origin
cd apps\web; vercel link --yes; cd ..\..
# 2) API Space (needs the web origin for the MCP origin allowlist)
.venv\Scripts\python.exe scripts\deploy\push_hf_space.py --bundle-id <bundle id> --web-origin https://<project>.vercel.app
# 3) Web env + production deploy
#    RESOLVEIT_API_URL=https://<user>-resolveit-api.hf.space, RESOLVEIT_PUBLIC_ORIGIN=https://<project>.vercel.app,
#    RESOLVEIT_SESSION_KEY_B64 from prod.env, RESOLVEIT_LOCAL_DEMO=false
cd apps\web; vercel deploy --prod
```

Sign in at `https://<project>.vercel.app/login` with `RESOLVEIT_API_KEY` from `prod.env` (admin of the
synthetic demo tenant). Share that key only with people who should see the demo; rotate by running
bootstrap with a new key and revoking the old one.

## Verify
- `https://<user>-resolveit-api.hf.space/healthz` -> `int8_trained_synthetic` and the pinned bundle id.
- Sign in, paste the four tickets from `docs/DEMO_WALKTHROUGH.md`.

## Limits stated honestly
- Free Space sleeps after ~48 h without traffic; first request then waits ~30-60 s for the image.
- Synthetic tenant only; real tenants remain shadow-mode. G2 128-token latency target not met.
- Neon free tier: 0.5 GB storage, compute auto-suspends (first query after idle ~1 s slower).

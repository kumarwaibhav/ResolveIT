"""Create/update the Hugging Face Docker Space for the API and set its secrets.

Inputs (all gitignored, never printed):
  artifacts/deploy/prod.env   from scripts/deploy/prod_env.py
  artifacts/deploy/neon.env   NEON_OWNER_DSN=<Neon direct owner connection string, sslmode=require>
Requires `hf auth login` (write token). Prints only names, ids and the Space URL.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parents[2]


def read_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if "=" in line and not line.startswith("#"):
            name, value = line.split("=", 1)
            out[name.strip()] = value.strip()
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--space", default="resolveit-api")
    parser.add_argument("--bundle-id", required=True)
    parser.add_argument("--web-origin", required=True, help="https://<project>.vercel.app")
    parser.add_argument("--context", type=Path, default=ROOT / "artifacts/deploy/hf-space")
    args = parser.parse_args()
    prod = read_env(ROOT / "artifacts/deploy/prod.env")
    owner = urlsplit(read_env(ROOT / "artifacts/deploy/neon.env")["NEON_OWNER_DSN"])
    host, db = owner.hostname, owner.path.lstrip("/")
    if not host or not db or not args.web_origin.startswith("https://"):
        raise SystemExit("neon.env DSN or web origin malformed")

    def url(user: str, password: str, driver: str) -> str:
        return urlunsplit((driver, f"{user}:{password}@{host}", f"/{db}", "", ""))

    secrets = {
        "RESOLVEIT_ADMIN_DSN": owner.geturl(),
        "RESOLVEIT_MIGRATOR_DATABASE_URL": url(
            "resolveit_migrator", prod["RESOLVEIT_MIGRATOR_PASSWORD"], "postgresql+asyncpg"
        )
        + "?ssl=require",
        "RESOLVEIT_APP_DATABASE_URL": url(
            "resolveit_app", prod["RESOLVEIT_APP_PASSWORD"], "postgresql+asyncpg"
        )
        + "?ssl=require",
        **{
            k: prod[k]
            for k in (
                "RESOLVEIT_MIGRATOR_PASSWORD",
                "RESOLVEIT_APP_PASSWORD",
                "RESOLVEIT_API_KEY",
                "RESOLVEIT_AGENT_KEY",
                "RESOLVEIT_MASTER_KEY_B64",
            )
        },
    }
    variables = {
        "RESOLVEIT_BUNDLE_ID": args.bundle_id,
        "RESOLVEIT_ALLOWED_ORIGINS": args.web_origin,
    }
    api = HfApi()
    user = api.whoami()["name"]
    repo_id = f"{user}/{args.space}"
    api.create_repo(repo_id, repo_type="space", space_sdk="docker", exist_ok=True, private=False)
    for key, value in secrets.items():
        api.add_space_secret(repo_id, key, value)
    for key, value in variables.items():
        api.add_space_variable(repo_id, key, value)
    api.upload_folder(
        repo_id=repo_id,
        repo_type="space",
        folder_path=str(args.context),
        commit_message=f"Deploy bundle {args.bundle_id[:16]}",
    )
    print(
        {
            "space": repo_id,
            "url": f"https://{user.lower()}-{args.space}.hf.space",
            "secrets_set": sorted(secrets),
            "variables_set": sorted(variables),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

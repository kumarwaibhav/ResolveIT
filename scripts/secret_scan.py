"""Bounded signature scan. Never emits matching values; not absence proof."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    "github_token": re.compile(rb"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})"),
    "openai_token": re.compile(rb"sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{32,}"),
    "aws_access_id": re.compile(rb"(?:AKIA|ASIA)[A-Z0-9]{16}"),
    "private_key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    # ${VAR} interpolations (compose) are references, not literal credentials.
    "credential_url": re.compile(
        rb"[a-z][a-z0-9+.-]*://[^\s:/@]+:(?!\$\{[A-Za-z_][A-Za-z0-9_]*\}@)[^\s/@]+@(?!(?:127\.0\.0\.1|localhost|postgres|unused|\{HOST\})(?:[:/]|$))[^\s/]+",
        re.IGNORECASE,
    ),
}


def git(*args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True).stdout


def inspect(label: str, content: bytes) -> list[str]:
    return [f"{label}: {name}" for name, pattern in PATTERNS.items() if pattern.search(content)]


def scan(staged: bool, history: bool) -> tuple[list[str], int]:
    findings: list[str] = []
    count = 0
    if history:
        seen: set[str] = set()
        for line in git("rev-list", "--objects", "--all").splitlines():
            oid = line.split(b" ", 1)[0].decode("ascii")
            if oid in seen or git("cat-file", "-t", oid).strip() != b"blob":
                continue
            seen.add(oid)
            findings.extend(inspect(f"history blob {oid[:12]}", git("cat-file", "blob", oid)))
            count += 1
    else:
        command = (
            ("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z") if staged else ("ls-files", "-z")
        )
        for raw in git(*command).split(b"\0"):
            if not raw:
                continue
            path = raw.decode("utf-8", errors="replace")
            if staged:
                content = git("show", f":{path}")
            else:
                source = ROOT / path
                if not source.is_file():
                    continue
                content = source.read_bytes()
            findings.extend(inspect(path, content))
            count += 1
    findings.extend(inspect("local git config", git("config", "--local", "--list")))
    return findings, count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged", action="store_true")
    parser.add_argument("--history", action="store_true")
    args = parser.parse_args()
    findings, count = scan(args.staged, args.history)
    print(
        f"Scanned {count} {'historical blobs' if args.history else 'files'} and local git config; "
        f"{len(findings)} signature findings."
    )
    for finding in findings:
        print(finding)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())

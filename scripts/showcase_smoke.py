"""Live smoke test of the running showcase: healthz, four demo tickets, one clarification answer.

Reads the API key from .env (or a given env file) and never prints it.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = "http://127.0.0.1:8000"
ENV_FILE = ROOT / ".env"
TICKETS = {
    "clear_english": "Outlook keeps crashing for the whole floor since this morning",
    "vague_hinglish": "kal se kuch bhi kaam nahi kar raha, please jaldi dekho",
    "compound": (
        "VPN disconnects every few minutes and after that MS Teams calls drop, whole team since yesterday"
    ),
    "security": (
        "I clicked a link in an email and typed my password, now my account is sending spam to everyone"
    ),
}


def key() -> str:
    for line in ENV_FILE.read_text(encoding="utf-8-sig").splitlines():
        if line.startswith("RESOLVEIT_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("RESOLVEIT_API_KEY missing from .env")


def call(method: str, path: str, body: dict | None = None) -> tuple[int, dict, float]:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(API + path, data=data, method=method)
    req.add_header("Authorization", f"Bearer {key()}")
    req.add_header("Content-Type", "application/json")
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read()), (time.perf_counter() - start) * 1000
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read() or b"{}"), (time.perf_counter() - start) * 1000


def summary(view: dict) -> dict:
    d = view.get("decision") or {}
    return {
        "state": view.get("state"),
        "routed_team": view.get("routed_team"),
        "action": d.get("action"),
        "recommended": d.get("recommended_team"),
        "ask_slot": d.get("ask_slot"),
        "defer_reason": d.get("defer_reason"),
        "security": view.get("security_trigger"),
        "slots": [
            (s["slot"], s["value"], len(s["evidence"])) for s in view.get("frame", []) if s.get("value")
        ],
    }


def main() -> int:
    global API, ENV_FILE
    if len(sys.argv) == 3:  # hosted check: showcase_smoke.py <api base url> <env file with RESOLVEIT_API_KEY>
        API, ENV_FILE = sys.argv[1].rstrip("/"), Path(sys.argv[2])
    with urllib.request.urlopen(API + "/healthz", timeout=90) as resp:
        health = json.loads(resp.read())
    print(json.dumps({"healthz": health}))
    ok = health.get("synthetic_bundle_kind") == "int8_trained_synthetic"
    results = {}
    for name, text in TICKETS.items():
        status, view, ms = call("POST", "/v1/incidents", {"text": text, "channel": "web"})
        results[name] = view
        print(json.dumps({name: {"http": status, "ms": round(ms), **summary(view)}}))
        ok &= status in (200, 201)
    vague = results["vague_hinglish"]
    if vague.get("state") == "PENDING_CLARIFICATION" and vague.get("question"):
        status, view, ms = call("POST", f"/v1/incidents/{vague['id']}/answer", {"answer": "vpn"})
        print(json.dumps({"vague_answer_vpn": {"http": status, "ms": round(ms), **summary(view)}}))
        ok &= status == 200
    ok &= results["clear_english"].get("routed_team") is not None
    security = results["security"]
    ok &= bool(security.get("security_trigger")) and security.get("state") == "DEFERRED"
    ok &= (security.get("decision") or {}).get("defer_reason") == "security_escalation"
    print(json.dumps({"smoke_passed": ok}))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

"""Send each demo scenario to the live demo engine and record what actually happened.
Reads the admin key from artifacts/deploy/prod.env; never prints it."""
import json, sys, time, urllib.request, pathlib
ROOT = pathlib.Path(sys.argv[1])
API = sys.argv[2].rstrip("/")
key = next(l.split("=", 1)[1].strip().strip('"').strip("'") for l in (ROOT / "artifacts/deploy/prod.env").read_text().splitlines() if l.strip().startswith("RESOLVEIT_API_KEY="))
TEAMS = ["Network","Identity_Access","Email_Collab","Hardware_Endpoint","Software_Licensing","Database","Cloud_Infra","Security","ERP_Finance","HR_Systems","DevOps_CICD","Facilities_AV"]
def call(path, body=None, method="POST"):
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())
here = pathlib.Path(__file__).parent
scenarios = json.loads((here / "scenarios.json").read_text(encoding="utf-8"))
call("/healthz", method="GET")
out = {}
for s in scenarios:
    t0 = time.perf_counter()
    v = call("/v1/incidents", {"text": s["text"], "locale": s["locale"], "channel": "web"})
    ms = round((time.perf_counter() - t0) * 1000)
    d = v.get("decision") or {}
    probs = d.get("probs") or []
    top = max(range(len(probs)), key=lambda i: probs[i]) if probs else None
    out[s["id"]] = {
        "state": v["state"], "action": d.get("action"), "routed_team": v.get("routed_team"),
        "recommended_team": d.get("recommended_team"), "defer_reason": d.get("defer_reason"),
        "question": (v.get("question") or {}).get("text"), "security_trigger": v.get("security_trigger"),
        "top_team": TEAMS[top] if top is not None else None, "top_p": round(probs[top], 3) if top is not None else None,
        "plausible": (d.get("conformal") or {}).get("teams"), "found": [f["slot"] for f in v.get("frame", []) if f["state"] != "MISSING"],
        "bundle": d.get("bundle_id"), "round_trip_ms": ms,
    }
    print(s["id"], v["state"], v.get("routed_team") or d.get("defer_reason") or "", f"{ms}ms")
(here / "scenario-results.json").write_text(json.dumps({"verified_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "results": out}, indent=1, ensure_ascii=False), encoding="utf-8")
print("saved", len(out))

# ResolveIT showcase walkthrough

Everything runs on this laptop, loopback only. The workspace is a **synthetic demo tenant**
(permanent "Synthetic Demo Data" banner); real tenants stay in shadow mode.

## Start and stop

```powershell
# from E:\ResolveIT App\ResolveIT, Docker Desktop running
powershell -ExecutionPolicy Bypass -File scripts\start_showcase.ps1
# stop (database keeps its data):
powershell -ExecutionPolicy Bypass -File scripts\stop_showcase.ps1
# stop and also stop the database container:
powershell -ExecutionPolicy Bypass -File scripts\stop_showcase.ps1 -Database
```

Health: http://127.0.0.1:8000/healthz shows `"synthetic_bundle_kind": "int8_trained_synthetic"`
and the pinned bundle id. Smoke test: `.venv\Scripts\python.exe scripts\showcase_smoke.py`.

## The six workspaces

| # | URL | What to show |
|---|-----|--------------|
| 01 | http://127.0.0.1:3000/ | Incident intake: type a ticket, see frame, evidence highlights, decision |
| 02 | http://127.0.0.1:3000/review | Review console: human judgment on deferred tickets |
| 03 | http://127.0.0.1:3000/bounce | Bounce analyzer: paste assignment history CSV, see hand-off loops |
| 04 | http://127.0.0.1:3000/evaluation | Evaluation lab: evidence over confidence (no invented metrics) |
| 05 | http://127.0.0.1:3000/mcp | Agent handoff: an AI agent files a ticket via MCP and answers with citations |
| 06 | http://127.0.0.1:3000/settings | Tenant settings: privacy, retention, erasure |

## Four tickets to paste into 01 (copy exactly)

**1. Clear English, auto-route with evidence**
```
Outlook keeps crashing for the whole floor since this morning
```
Expected: ROUTED to Email_Collab. Highlights on "Outlook", "whole floor", "since this morning"
(UTF-16 offsets, so they stay exact with emoji/Devanagari too). Talk track: the route is allowed
only because Email_Collab is the single team in the conformal set and the queue holds a
selective-risk certificate (error <= 5% at 95% confidence).
Variation for Q&A: add `error 0x80070005. Urgent.` - 0x80070005 is "access denied", so Identity
and Database become plausible; the set grows to three teams and the ticket goes to a person.
That is the system refusing to guess.

**2. Vague Hinglish, one question**
```
kal se kuch bhi kaam nahi kar raha, please jaldi dekho
```
Expected: one question (which service?). Answer `VPN` -> ROUTED to Network. Talk track: the gate
asks only when the expected value of the answer beats the cost of asking; one question, never a
chain.

**3. Compound**
```
VPN disconnects every few minutes and after that MS Teams calls drop, whole team since yesterday
```
Expected: VPN found, but Teams symptoms too, so it asks which service is the real problem
before routing (Network vs Email_Collab). Talk track: it does not split or guess on mixed reports.

**4. Security**
```
I clicked a link in an email and typed my password, now my account is sending spam to everyone
```
Expected: security flag, no question, handed straight to a person flagged for the security team
(`security_escalation`). Talk track: security bypasses ordinary routing; no model confidence is
dressed up as a security verdict.

## Numbers you can quote (synthetic frozen test, 624 tickets; see docs/BUILD_STATE.md)

- 455 auto-routed, 455 correct (0 misroutes); 160 asked one question, 111 answered and routed,
  all correct; 9 deferred to a person; auto-route rate 90.7%.
- INT8 model 315 MB, parity with FP32 cosine 0.9999. Full pipeline on a typical ticket:
  40 ms median / 45 ms p95 (CPU, 4 threads). 128-token ticket: ~180 ms (distilled model planned).
- Caveat to state: synthetic data, not customer tickets; real tenants stay shadow until certified
  on their own human-labelled tickets.

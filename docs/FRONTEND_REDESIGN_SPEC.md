# ResolveIT Web — Frontend Redesign Specification

Version 1.0 · 2026-11-17 · Source of truth: `apps/web` at commit `bf5ddab`

This document describes everything the current frontend does, the rules it must keep, and what to
consider when rebuilding it from scratch. It is built from the actual code (every page, component,
route handler, API contract, test and security control), not from memory.

**How to use it.** Read Part A once (what cannot change). Use Part B as the inventory while you
redesign each screen. Part C covers design direction. Part D is the build order and the checklists.

---

## Contents

**Part A — Ground rules**
1. What ResolveIT is (one page)
2. Non-negotiables for any redesign
3. Tech stack and architecture of the web app
4. Runtime modes, environment variables and security boundaries

**Part B — Complete inventory**
5. Route map
6. Global shell (layout, navigation, banners)
7. Page specs: Login, Intake, Incident detail, Review, Bounce, Evaluation, Agent hand-off, Settings, Error, Not found
8. Shared components and helper libraries
9. Domain dictionary (teams, slots, states, reasons, roles)
10. API contract the frontend consumes
11. Decision semantics the UI must explain honestly

**Part C — Design direction**
12. Brand, colour and type: current tokens and redesign brief
13. Motion, glass and "billion-dollar SaaS" patterns, translated into rules
14. Accessibility requirements (gate-enforced)
15. Internationalisation and scripts
16. Responsive behaviour
17. Performance budgets

**Part D — Delivery**
18. Tests and gates that must keep passing
19. Gaps and opportunities the current UI does not cover
20. Staggered rebuild plan with acceptance criteria
21. Final pre-ship checklist

---

# Part A — Ground rules

## 1. What ResolveIT is

ResolveIT is a multi-tenant B2B IT-incident triage SaaS. An employee reports a problem in their own
words: English, Hindi or Hinglish today, with Marathi and Tamil planned. Voice-call intake is also
planned. The system then does five things:

1. **Saves the ticket first.** The incident is persisted and encrypted before any analysis, so nothing is lost.
2. **Reads it.** Deterministic rules plus an INT8 mDeBERTa encoder extract an *incident frame*: 11 slots
   such as service, symptom, scope and urgency. Each slot links to evidence spans in the user's own text.
3. **Decides one of three actions. No LLM is involved in this decision.**
   - **ROUTE** to one of 12 teams. This is allowed only when a statistical risk certificate holds: wrong
     routes stay at or below 5% with 95% confidence.
   - **ASK** at most one optional clarifying question. It is asked only when the expected value of the
     answer beats the cost of asking.
   - **DEFER** to a human, always with a stated reason.
4. **Escalates security.** A security incident (phishing, a clicked link, a hacked account) bypasses ordinary
   routing. No question is asked, and it goes straight to a human with a flag for the Security team.
5. **Keeps real tenants in shadow mode.** For real tenants the system suggests but never auto-routes until
   it is certified on that tenant's own human-labelled tickets. Only the **synthetic demo tenant**
   auto-routes, and it must say so permanently.

**Users and roles (enforced by the API):**

| Role | Can do |
|---|---|
| `admin` | Everything: submit and read incidents, review and adjudicate, settings, privacy erasure, export |
| `reviewer` | Submit and read incidents, label review items, bounce analysis, agreement metrics |
| `viewer` | Read incidents, list the review queue, read evaluation status |
| `agent` | Third-party AI agent key: submit via MCP or REST and read decisions. It **never** receives decrypted ticket text and cannot answer questions over REST (it must use MCP with evidence citations) |

**The product promise the UI must sell:** *evidence before action.* Every decision is explained
in the user's own words, with numbers that are honest about uncertainty.

## 2. Non-negotiables for any redesign

These rules come from security audits, release gates and the product's honesty guarantees.
Break one and a gate fails or a trust claim becomes false.

1. **No API key ever reaches the browser.** The browser talks only to Next.js route handlers under
   `/api/*`, which attach the key server-side (backend-for-frontend pattern). Do not call the
   Python API directly from client code.
2. **The synthetic-data banner is permanent** on every view of a synthetic tenant's data. It cannot be
   dismissed, hidden behind a tooltip or collapsed. The exact claim is: decisions come from a bundle
   calibrated on generated tickets, are excluded from evaluation, and say nothing about real accuracy.
3. **Never invent metrics.** If a number does not come from the API or a computed file, show "—" or
   "Undefined". No placeholder accuracy, no fake charts, no "99.9%" marketing figures inside the
   product. (Marketing pages may use only measured figures; see §13.)
4. **Colour never carries meaning alone.** Every state carries a word and/or an icon, with colour as reinforcement.
5. **User text is rendered as text.** Never use `dangerouslySetInnerHTML`. Evidence highlights are
   built by slicing the string at offsets (`lib/highlight.ts`). Offsets are **UTF-16 code units**, so
   emoji and Devanagari stay aligned. Keep that.
6. **Skip is always available and never visually smaller than Send** on a clarifying question.
7. **Security escalation is never softened.** No "Are you sure?" and no extra step before sending a security ticket.
8. **Erasure is deliberate.** It needs an explicit confirmation checkbox, an exact identifier, and a
   result message stating that backups need a separate process.
9. **Accessibility gate:** zero axe violations on all 6 workspaces at 1440 px light **and** 320 px dark,
   with no horizontal overflow (see §14).
10. **API types are generated, never hand-written.** `src/generated/api.ts` comes from `openapi.json`
    (`npm run gen:types`). `src/generated/lexicon.json` comes from the Python rule engine
    (`scripts/export_contracts.py`). CI fails if they drift.
11. **Authorship:** every commit uses `Kumar Waibhav Akshat <kwa.waibhav@gmail.com>`.

## 3. Tech stack and architecture

| Layer | Current choice | Notes for the redesign |
|---|---|---|
| Framework | **Next.js 15.5 (App Router)**, React 19.1, TypeScript 5.7 | Keep App Router. Pages are server components by default; interactive parts are `"use client"` |
| Styling | **Tailwind CSS v4** (`@import "tailwindcss"`, `@theme inline`), CSS variables in `globals.css`, plus about 200 lines of bespoke classes (`.workspace-*`, `.surface-panel`, …) | The bespoke classes are what you're replacing. Move to tokens + components |
| Components | **shadcn/ui** (copied into `components/ui/`: alert, badge, button, card, label, separator, textarea), **Radix** primitives, **lucide-react** icons, `class-variance-authority`, `tw-animate-css` | Keep shadcn as the base layer; extend with a real design system |
| Data | `fetch` to same-origin route handlers; no client cache library | Consider TanStack Query or SWR for review, settings and evaluation (refresh, optimistic UI) |
| Types | `openapi-typescript` → `src/generated/api.ts`; aliases in `lib/types.ts`, `lib/workspace-api.ts` | Keep. Never redeclare API shapes |
| Rules in browser | `lib/meter.ts` compiles the generated lexicon regexes for the live detail meter (no network) | Keep. It is a key demo moment |
| Tests | Vitest (22 unit tests in `src/lib/__tests__`); Playwright Python E2E (`e2e/stage_c.py`, `e2e/journeys.py`) driven by gate G4 | E2E selectors depend on visible labels; see §18 |
| Build | `next build`; Node 22.x; deployed on **Vercel** (`apps/web/vercel.json` → region `bom1`) | `NODE_OPTIONS` heap and `experimental.cpus:1` exist for the low-memory laptop |

**Request flow:**

```
Browser ──fetch──▶ Next.js route handler (/api/...) ──Bearer key from sealed cookie──▶ ResolveIT API
                     │  middleware: host/origin checks, session gate, security headers
                     └─ server components may also call apiFetch() directly (incident page)
```

## 4. Runtime modes, environment and security boundaries

**Two modes (`RESOLVEIT_LOCAL_DEMO`):**

| | Local demo (`true`) | Production (`false`) |
|---|---|---|
| Who can open it | Loopback hosts only (`localhost`, `127.0.0.1`, `[::1]`); any other host gets 403 | HTTPS host equal to `RESOLVEIT_PUBLIC_ORIGIN` only, otherwise 503 |
| Sign-in | Not required. Server uses shared demo keys, **only** if `/v1/me` says the tenant is synthetic | Required. Any page except `/login` redirects to `/login`; `/api/*` returns 401 |
| Cookie name | `resolveit_local_session` | `__Host-resolveit_session` (Secure) |
| HSTS | Off | `max-age=63072000; includeSubDomains` |

**Environment variables used by the web app:** `RESOLVEIT_API_URL`, `RESOLVEIT_PUBLIC_ORIGIN`,
`RESOLVEIT_LOCAL_DEMO`, `RESOLVEIT_SESSION_KEY_B64` (32-byte AES key), plus `RESOLVEIT_API_KEY` and
`RESOLVEIT_AGENT_KEY` in local demo only. None are `NEXT_PUBLIC_*`. Keep it that way.

**Session (`lib/auth-session.ts`):**
- The cookie holds the API key encrypted with AES-GCM under a fresh nonce, with AAD
  `resolveit:web-session:v1` and a **1-hour TTL**.
- It is `httpOnly`, `SameSite=Strict` and `Secure` in production.
- Sign-in posts the key to `/api/session`. The server verifies it against `/v1/me`, then seals the cookie.
- Sign-out (`DELETE /api/session`) clears the cookie.

**Middleware (`src/middleware.ts`), for every matched path (`/`, `/login`, `/api/*`, `/incidents/*`, `/review/*`, `/bounce/*`, `/evaluation/*`, `/settings/*`, `/mcp/*`):**
1. Host validation (see the modes table).
2. `Sec-Fetch-Site: cross-site` → 403.
3. An `Origin` header must equal the expected origin, otherwise 403.
4. A non-GET request **without** `Origin` → 403. Any client-side `fetch` you write must be same-origin.
5. Production: no session → redirect to `/login` (pages) or 401 (API). `/login` and `/api/session` are exempt.
6. Adds `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy: same-origin`, `Cache-Control: no-store`.

**`next.config.ts` headers on all routes:**
- CSP `frame-ancestors 'none'; base-uri 'none'; form-action 'self'; object-src 'none'`.
- `X-Frame-Options`, `nosniff`, `Referrer-Policy`.
- `Permissions-Policy: camera=(), geolocation=(), microphone=(self)`. The microphone is allowed for future voice intake.
- HSTS in production.

**Design implications:**
- **Iframes.** You cannot embed the app in an iframe, and the app cannot rely on third-party iframes. Spline, Rive and YouTube embeds need CSP changes. Prefer self-hosted assets.
- **Scripts.** Script sources are not restricted yet. If you add analytics, think about adding `script-src` with nonces.
- **Fonts.** Load them from Google Fonts via `next/font` (self-hosted at build time), not from a remote `<link>`.

**Body size limits enforced by route handlers:**

| Endpoint | Limit |
|---|---|
| Default | 128 KB |
| Bounce analyze | 8 MB to the proxy; UI limits are 1 MB connected and 2 MB local |
| Session | 2 KB |
| Incident text | 20,000 characters (UI `maxLength` and API) |

---

# Part B — Complete inventory

## 5. Route map

### Pages

| Path | File | Type | Purpose | Who sees it |
|---|---|---|---|---|
| `/login` | `app/login/page.tsx` | client | Sign in with an individual API credential; clear session | Everyone (production) |
| `/` | `app/page.tsx` → `components/intake-workspace.tsx` | client | **01 Incident intake.** Report a problem and see the frame, evidence and decision | admin, reviewer (agent via API) |
| `/incidents/[id]` | `app/incidents/[id]/page.tsx` | **server** | Permalink to one incident (read-only panel) | admin, reviewer, viewer |
| `/review` | `app/review/page.tsx` → `review-workspace.tsx` | client | **02 Review console.** Human labelling, agreement, adjudication, export | reviewer, admin (viewer can list) |
| `/bounce` | `app/bounce/page.tsx` → `bounce-workspace.tsx` | client | **03 Bounce analyzer.** CSV assignment history → reassignment analysis | reviewer, admin |
| `/evaluation` | `app/evaluation/page.tsx` → `evaluation-workspace.tsx` | client | **04 Evaluation lab.** Bundle provenance, honest certification status, upload predictions to compute metrics | admin, reviewer, viewer |
| `/mcp` | `app/mcp/page.tsx` → `mcp-simulator.tsx` + `architecture-explorer.tsx` | client | **05 Agent hand-off.** MCP inspector, signed clarification round trips, pipeline explorer | admin (uses agent key in demo) |
| `/settings` | `app/settings/page.tsx` → `settings-workspace.tsx` | client | **06 Tenant settings.** Queue map, routing costs, timezone, privacy erasure | admin |
| (error) | `app/error.tsx` | client | Error boundary: "The service did not respond" + Try again | — |
| (404) | `app/not-found.tsx` | server | "Nothing here" + link to report a problem | — |

### Route handlers (backend-for-frontend)

| Method + path | File | Upstream | Notes |
|---|---|---|---|
| `POST /api/session` | `app/api/session/route.ts` | `GET /v1/me` | Body `{apiKey}` (≤ 2 KB). Returns `{tenant_id, role, human_labeling_enrolled}` and sets the cookie. 400/401/413/503 errors |
| `GET /api/session` | same | — | `{signed_in: boolean}` |
| `DELETE /api/session` | same | — | Clears the cookie |
| `POST /api/incidents` | `app/api/incidents/route.ts` | `POST /v1/incidents` | Body `IncidentCreate` |
| `GET /api/incidents/[id]` | `.../[id]/route.ts` | `GET /v1/incidents/{id}` | |
| `POST /api/incidents/[id]/answer` | `.../answer/route.ts` | `POST /v1/incidents/{id}/answer` | `{answer: string \| null}`; null means Skip |
| `POST /api/mcp` | `app/api/mcp/route.ts` | `POST /mcp` | Returns `{request, status, response}` so the UI can show both sides. The bearer token is shown as "(agent key, held on the server)" |
| `POST /api/privacy/erasure` | `app/api/privacy/erasure/route.ts` | `POST /v1/privacy/erasure` | admin |
| `GET\|POST\|PUT /api/workspaces/[...path]` | `app/api/workspaces/[...path]/route.ts` | `/v1/...` | **Allowlist:** GET `review`, `review/agreement`, `review/export`, `settings`, `evaluation`; PUT `settings`; POST `review/{uuid}/labels`, `review/{uuid}/adjudication`, `bounce/analyze`. Query params passed through: `blind`, `limit`, `after` |

## 6. Global shell

**Layout (`app/layout.tsx`):**
- `<html lang="en">`.
- **Skip link** "Skip to content" → `#main`. It is visible on focus; keep it.
- Left **sidebar** (`SiteNav`, fixed, 248 px; 210 px at ≤ 1100 px; becomes a horizontal scroll strip at ≤ 760 px).
- **Top bar:** breadcrumb "ResolveIT AI / Workspace" and a "CONTROLLED SANDBOX" badge.
- `<main id="main">`, max width 1560 px.
- **Footer:** "Every decision should have evidence." · "English · हिन्दी · Hinglish".
- Metadata: title template `%s · ResolveIT`; description "Report an IT problem and see how it is understood and routed."

**Sidebar contents (`components/site-nav.tsx`):**

| Element | Behaviour | Note for redesign |
|---|---|---|
| Brand lockup "r↗ resolve**it** · INCIDENT INTELLIGENCE" | Link to `/` | `aria-label="ResolveIT home"` |
| Tenant switcher ("R · ResolveIT sandbox · Local workspace ⌄") | **Decorative only; does nothing** | Either make it real (show tenant name, role and synthetic flag from `/v1/me`) or remove it |
| Nav eyebrow "WORKSPACE" | — | |
| 6 nav links | `01 Incident intake / Understand & route`, `02 Review console / Human judgment`, `03 Bounce analyzer / Follow the handoffs`, `04 Evaluation lab / Evidence over confidence`, `05 Agent handoff / Inspect every exchange`, `06 Tenant settings / Control & privacy` | Active state uses `aria-current="page"`. `/` is also active for `/incidents/*` |
| Footer "Human oversight, by design · Real tenants stay in shadow mode · 0.1" | Static | |

**Missing from the shell today** (add these in the redesign):
- **Sign out** button. `DELETE /api/session` exists, but there is no button except on `/login`.
- **Who am I:** role and tenant, from `POST /api/session`'s response or a new `GET` that proxies `/v1/me`.
- **Role-aware navigation:** hide or disable Settings for non-admins, and so on. Today a viewer sees every link and gets 403 errors.
- **API status / cold-start indicator.** The production API on Modal sleeps after about 10 minutes and the first call takes 15–30 s. Show "Waking the engine…" instead of a frozen spinner.
- **Theme toggle.** Dark mode currently follows the OS only (`prefers-color-scheme`).

**Banners:**
- `SyntheticBanner` (`role="note"`, warn colours). Text: **"Synthetic demo data.** Decisions here come from a bundle calibrated on generated tickets. They are excluded from evaluation and say nothing about real accuracy." Shown wherever `is_synthetic_tenant` is true. **Non-dismissible.**
- `LocalDraftNotice`: "◈ Browser-local workspace. Changes are drafts until exported; they are not saved to the server." Used on Review (practice), Bounce and Evaluation.

## 7. Page specifications

Each page lists its purpose, every control and behaviour, its states, its API calls, the copy that
carries meaning (keep it or improve it without changing the meaning), its accessibility hooks, and
redesign notes.

### 7.1 `/login` — Secure access

**Purpose:** exchange an individual API credential for an encrypted session cookie.

| Element | Behaviour |
|---|---|
| Eyebrow "RESOLVEIT / SECURE ACCESS", H1 "Your workspace. Your identity.", copy about individual credentials | Static |
| Input **"Individual API credential"** (`type=password`, `autocomplete=current-password`, `maxLength 512`, required) | |
| Button **"Sign in"** | Disabled while busy or when empty. `POST /api/session {apiKey}`. On success: clear the field, `router.replace("/review")`, refresh. On error: show `detail` ("Credential rejected", "Request too large", …) in `role="status"` |
| Button **"Clear current session"** | `DELETE /api/session` → "Signed out. Session cleared." |

**States:** idle, busy ("Signing in…"), error, signed out.

**Redesign notes:**
- After sign-in, go to Intake (`/`) for admins and reviewers, not `/review`. Update the E2E `login()` expectation, which waits for the heading "Make judgment visible.".
- Add a "Where do I get a key?" explainer: keys are issued per person by an admin.
- Never show the key.
- Show the role returned by the server.
- This page must work without JavaScript failing badly. It is also the investor's first impression in production.

### 7.2 `/` — 01 Incident intake (the hero flow)

**Purpose:** a person reports a problem and immediately sees what was understood, as evidence in
their own words, and what happens next.

**Header block:**
- Eyebrow "01 / INCIDENT INTAKE"; H1 **"Clarity before the handoff."**; sub "One report. The right context. A more considered next step."; pill "Human oversight enabled".
- Overview strip: **11 / slots** "A complete incident picture" · **3 / languages** "Express the problem your way" · **1 / question, at most** "Less friction. More signal."

**Left: report form**

| Control | Behaviour | Constraints |
|---|---|---|
| Textarea **"What is going wrong?"** (`id=problem`) | Free text. Placeholder "VPN keeps dropping since this morning for the whole floor" | `maxLength=20000`, 7 rows. Help text: "Paste error codes exactly as shown. Detected identifiers are masked in derived text; your original report is encrypted." (`aria-describedby`) |
| Radio group **"Language for any follow-up question"** | `English` / `हिन्दी` (`lang="hi"`) / `Hinglish`; default `en` | Sets `locale`, which controls the language of the question text. Touch target ≥ 44 px on mobile |
| **Detail meter** (`DetailMeter`) | Live, client-side, on every keystroke. Shows "Details spotted so far · N of 6", a progress bar (`role="meter"`), and a checklist of 6 meter slots: System or app, Error code, Who is affected, How often, Urgency, When it started (✓ found, – missing, with sr-only ", found"/", not yet stated") | Footer: "Checked on this device as you type. Missing details never block sending." **No network call.** |
| Security hint | If the lexicon security regex matches: `role="status"` risk box: "This reads like a security incident. Send it now; the Security team is flagged straight away." | Appears while typing |
| Button **"Send ticket"** | `POST /api/incidents {text, locale, channel:"web"}`. Disabled when busy or when the text is blank. Busy label "Sending…" | On success, focus moves to the result heading (`[data-result-heading]`) |
| Error line | `role="alert"`: "{message} Your text is still here; try again." 409 → "This question was already closed." | The text is never cleared on error |

**Right: result region** (`<section aria-label="Result" aria-live="polite">`)

- **Empty state:** an orbit illustration (decorative); eyebrow "EVIDENCE, THEN ACTION"; "A little context goes a long way."; "Your incident frame and source evidence will appear here."; and an ordered list **"What happens when you send":**
  1. The ticket is saved first, so nothing is lost.
  2. You see which details were understood, marked in your own words.
  3. It goes to a team, or to a person if the team is not clear. You may get one optional question.
- **After send:** `SyntheticBanner` (if synthetic), then `IncidentPanel` (§8).
- **Answer flow:** the `QuestionCard` inside the panel. "Send answer" → `POST /api/incidents/{id}/answer {answer}`; "Skip" → `{answer:null}`. The panel re-renders with the final decision, and the question disappears.

**The 4 canonical demo tickets** (`docs/DEMO_WALKTHROUGH.md`). Design every state around them:

| Ticket | Expected outcome |
|---|---|
| `Outlook keeps crashing for the whole floor since this morning` | **ROUTED → Email_Collab.** Evidence on "Outlook", "whole floor", "since this morning" |
| `kal se kuch bhi kaam nahi kar raha, please jaldi dekho` | **ASK** "Which system or app is this about?" → answer `vpn` → **ROUTED → Network** |
| `VPN disconnects every few minutes and after that MS Teams calls drop, whole team since yesterday` | **ASK** (service), because it is compound |
| `I clicked a link in an email and typed my password, now my account is sending spam to everyone` | **DEFERRED · security_escalation.** No question, security flag |

Hedging variant: adding `error 0x80070005. Urgent.` to ticket 1 gives three plausible teams, so it **DEFERs**. That is a "refuses to guess" story worth designing for.

**Redesign notes:**
- This is the investor-demo screen. Make the transition from "typing" to "understood" to "decided" cinematic but fast. The p50 response is about 1 s warm, plus a cold start of up to 30 s.
- Consider a staged reveal: frame slots appear, then evidence highlights draw in, then the decision card resolves, with the processing pipeline (Rules → PII shield → Model → Risk gate → Decision) animating along the way.
- Keep the security hint instantaneous and unmissable.

### 7.3 `/incidents/[id]` — Incident permalink (server-rendered)

| Behaviour | Detail |
|---|---|
| Validate the UUID (`isUuid`); invalid → 404 page | |
| `apiFetch('/v1/incidents/{id}')`. 404 → not found; other non-OK → throws (error boundary) | |
| Shows "Report another problem" link, `SyntheticBanner` (if synthetic), `IncidentPanel` **without** `onAnswer` (read-only: the question is not interactive here) | |

**Redesign notes:**
- No list of incidents exists anywhere in the UI. Add an **Incidents inbox** (§19).
- Consider letting a reporter answer the pending question from the permalink. The API supports it via the same answer endpoint.

### 7.4 `/review` — 02 Review console

Top tabs (`aria-pressed` buttons): **"Connected tenant"** (default) | **"Synthetic practice"**.

#### Connected tenant (`live-review-workspace.tsx`)

- **Header:** "02 / REVIEW CONSOLE", H1 **"Make judgment visible."**, copy about independent annotations, server-enforced blinding and immutable splits. Pill "Connected tenant review".
- **Action row:**
  - Checkbox **"Blind audit: hide model suggestions"** (default on; changing it reloads with `?blind=`).
  - **"Refresh"**.
  - **"Export eligible labels"** → `GET review/export`, downloaded as `resolveit-reviewed-labels.json` (admin only server-side).
- **Metric cards** (from `GET review/agreement`): **Independent label pairs** (`n_pairs`), **Cohen's κ**, **Krippendorff's α**. Show "Undefined" when null, never 0.
- **Left panel:**
  - Select **"Incident to review"** (options `id[0:8] · status`).
  - Tags: synthetic_seed or customer incident; locale; split.
  - Record text, or "Text unavailable or erased.".
  - "Status: … · N independent labels · Random audit stream/Training-only review".
  - When not blind, the suggestion is shown with the warning "This view is not blind".
  - Provenance note: synthetic exports are `human_on_synthetic`, never `human_gold`.
- **Right panel, `LabelEditor`:**
  - "Eleven-slot human annotation".
  - Exposure warning if `model_exposed` or `peer_exposed`.
  - "Not enrolled" warning if `human_labeling_enrolled` is false; inputs are disabled in that case.
  - Select **"Responsible team"** (12 teams).
  - A table of 11 slots, each with **State** (`PRESENT/MISSING/AMBIGUOUS/CONTRADICTED`, starting "Unreviewed") and **Value** (text ≤ 500; disabled when MISSING or unreviewed).
  - Progress "N / 11 slots reviewed. Present slots require a value."
  - **"Save independent label"** (enabled only when complete) → `POST review/{id}/labels`.
  - **"Submit adjudication"** (only when `status === needs_adjudication`) → `POST review/{id}/adjudication` (admin).
  - `<details>` "Inspect conflicting annotations for adjudication" shows the JSON of `paired_labels`.
- **Empty state:** "No review items yet." "Submit an incident in Intake, then refresh."
- **Review status values:** `unlabeled`, `single_label`, `needs_adjudication`, `gold`, `synthetic_labeled`.

#### Synthetic practice (`PracticeReviewWorkspace`, browser-only)

- Four fixed synthetic records (SYN-001..004; English, Hindi, Hinglish).
- Annotator A and B tabs with identifier inputs (must be distinct).
- Team select per annotator. Adjudication select appears when the labels disagree.
- "Hide model suggestion until labels are recorded" checkbox. Revealing the suggestion shows a warning.
- Previous / Next buttons.
- Live κ and α computed locally (`lib/workspaces.agreement`).
- **"Export reviewed drafts"** → `resolveit-annotation-drafts.json` (`human_gold:false`, `blinding_enforced:false`).
- Workflow strip: Independent identities → Blind labels → Adjudication → Locked incident groups → Frozen split registry.

**Redesign notes:**
- This is a dense power-user tool. Design it as a split-pane queue (list | record | label form) with keyboard shortcuts (j/k to navigate, 1–4 for slot state).
- Keep the honesty texts.
- The JSON `<details>` view could become a proper side-by-side diff of the two annotations.

### 7.5 `/bounce` — 03 Bounce analyzer

- **Header:** "03 / BOUNCE ANALYZER", H1 **"Follow the friction."**, plus `LocalDraftNotice`.
- **Left: "Assignment history".** Required columns are `ticket_id, queue, timestamp` (ISO timestamps with a timezone).
  - File input **"Import CSV"** (accepts `.csv`, ≤ 2 MB).
  - Textarea **"Or paste CSV"** (monospace, ≤ 2,000,000 characters).
  - Buttons:
    - **"Analyze locally →"** (primary): browser parse with `parseCsv` + `analyzeBounces`.
    - **"Analyze with tenant API"**: renames `queue`→`assignment_group`, re-quotes, ≤ 1 MB → `POST bounce/analyze`.
    - **"Load synthetic example"**: sets provenance `synthetic_seed`.
  - Errors (`role="alert"`) give row-precise messages ("Row 4: timestamp is invalid.").
- **Right: definition panel.** "COUNT THE PATH, NOT THE GUESS". Defines a bounce, with the example Service Desk → Network → Identity = 2 reassignments, and states the caveats.
- **Local result:**
  - Provenance tag and **"Export analysis"**.
  - Metric cards: Observed tickets, Total reassignments, Tickets reassigned %.
  - Table: Ticket · Queue journey (A → B → C) · Reassignments · Observed span (h).
- **Connected result:**
  - Assumptions text.
  - Cards: Tickets, Queue transitions, Reassigned tickets %.
  - **"Export connected report"**.
  - The API also returns `bounced_tickets`, `median_reassignments` and `top_transitions`, which are **not shown today**. That's an opportunity for a Sankey or flow visual.

**Redesign notes:** this is the natural place for a **flow / Sankey diagram** of queue transitions
and a "ping-pong" highlight. Data is fully client-side for local mode, so it's cheap to animate.

### 7.6 `/evaluation` — 04 Evaluation lab

- **Header:** "04 / EVALUATION LAB", H1 **"Confidence needs evidence."**, plus `LocalDraftNotice`.
- **Connected bundle card** (from `GET evaluation`):
  - Eyebrow "CONNECTED BUNDLE"; `bundle_id`; `explanation`.
  - Cards: **Bundle provenance** (`provenance` + "Synthetic demo routing enabled" / "Human gate enabled"), **Human gold incidents** (`human_gold_count`), **Frozen human test support** (`frozen_test_count`).
  - `human_test_accuracy` exists in the API but is not shown. Show it only when non-null.
- **"PRODUCTION CERTIFICATION · Human test report unavailable":** pill "Shadow mode"; workflow Training → Scaling → Conformal fit → Risk certification → Frozen test; copy that thresholds are fitted on the shipped INT8 outputs.
- **"Four explicit comparisons":** table with Majority class, Raw rules, TF-IDF + linear, Three-head INT8 student. All currently say "No frozen report". Real synthetic numbers exist in the bundle `report.json` (forced accuracy 0.761 vs TF-IDF 0.739, 0 misroutes among 455 routed) but are **not exposed by the API**. If you want them on screen, add an API field first. Never hard-code them.
- **"Inspect prediction outputs":** file input "Prediction JSON · maximum 2 MB" (shape `{provenance, baseline, rows:[{label, probs{12 teams}}]}`) and **"Download format example"**.
- **Result:** unverified-provenance notice; cards for Uploaded accuracy, Multiclass Brier and Negative log likelihood; **"Export computed report"** (`verified:false, certifies_routing:false`).

**Redesign notes:**
- Ideal for charts: reliability diagram, risk–coverage curve, per-queue certificate status, ask/defer funnel.
- Every chart needs real data from the API or an uploaded file. Design the empty states as carefully as the full ones.

### 7.7 `/mcp` — 05 Agent hand-off

**Header:** "05 / AGENT HANDOFF", H1 **"Trust the trace."**

**A. Standard MCP 2025-11-25 inspector:**
- **"Inspect initialize"** sends a JSON-RPC `initialize`.
- **"Inspect tools/list"** sends `tools/list`.
- Side by side: "Standard request" and "Standard response (HTTP n)" JSON blocks. The `<pre>` blocks are focusable (`tabIndex=0`).

**B. ResolveIT enterprise profile 2026-07-28: "Signed clarification round trips":**
- Textarea **"The user's report, verbatim"** (default "it stopped working this morning, the v-p-n client shows nothing", ≤ 20,000 characters).
- **"Call submit_incident"** sends `tools/call submit_incident` with `_meta` protocol version, client info and the elicitation capability.
- Ordered list of round trips. Each card is titled "Round trip N: complete / the server needs one answer / error CODE" and shows the Request and Response JSON.
- When the result is `input_required`: a clarify form showing the server's message and the copy "An answer only counts if it quotes the user's own words. Without a matching quote it is recorded as unknown."
  - Select **"Answer"** (from the schema enum).
  - Input **"Quote from the report"**.
  - **"Retry with answer"** sends `requestState` + `inputResponses.clarify {action:"accept", content:{answer, evidence_quote}}`.
  - **"Decline"** sends `{action:"decline"}`.
- Expected demo: answer `vpn` + quote `v-p-n client` → "Round trip 2: complete" and `"routed_team": "Network"`.

**C. Architecture explorer: "Trace the decision path".** Five stage buttons (`aria-pressed`), each opening a title and detail:
1. Raw evidence
2. PII shield
3. Model bundle
4. Risk gate
5. Human / agent

**Redesign notes:**
- This page is the "interactive product sandbox" opportunity (like runlatent.ai's hero).
- Make the architecture explorer an animated SVG pipeline where packets move stage to stage and the selected stage expands.
- Render JSON with syntax highlighting and collapsible nodes. Keep a raw-copy button.

### 7.8 `/settings` — 06 Tenant settings (admin)

**Header:** "06 / TENANT SETTINGS", H1 **"Keep control close."**

**Connection notice:** "Connected tenant settings · version N. Save uses optimistic version checks." or "Configuration is a local draft until the tenant API connects."

**Queue map:**
- A table of the 12 canonical teams, each with a text input "Destination queue" (placeholder `UNMAPPED`, ≤ 100 characters).
- Counter "N / 12 queues mapped in this draft."
- Copy: many teams can share a queue; an empty queue means UNMAPPED and cannot auto-route.

**Routing controls, "Human gate stays on":**
- Range **"Misroute cost multiplier · X.XX×"** (0.25–4, step 0.25; 240 min × scale).
- Copy explaining the placeholder costs, plus `defer_minutes`.
- Input **"Tenant timezone"** (IANA, default `Asia/Kolkata`).
- **"Save tenant settings"** → `PUT settings {version, timezone, queue_mapping, misroute_minutes, defer_minutes}`. On success: "Tenant configuration saved at version N. Routing certification remains independent." A version conflict shows as "Save failed: …".
- **"Export settings draft"** → `resolveit-settings-draft.json`.

**Privacy, "Erase a subject's incidents" (live action):**
- Select **"Identifier type"**: EMAIL, AADHAAR, PAN, IP_ADDR, PHONE_IN, EMP_ID, USER_NAME.
- Input **"Exact subject identifier"** (`autocomplete=off`, ≤ 320).
- Checkbox **"I understand this permanently removes matching live incidents."**
- **"Erase matching incidents"** is enabled only when confirmed and an identifier is present → `POST /api/privacy/erasure {kind, identifier}`.
  - Success: "N incident(s) erased from the live tenant store. Backup erasure requires the managed-key and restore-tombstone process."
  - 403 → "Admin access is required for erasure."

**Redesign notes:**
- Use a danger zone pattern for erasure: a separate surface, destructive styling, a typed confirmation of the identifier, and no default focus.
- Show `routing_config_status` from the API, which is unused today.
- Timezone should become a searchable combobox.

### 7.9 Error and Not found

- **Error boundary:** `role="alert"`, "The service did not respond", "The request could not be completed. Check the incident state before resubmitting.", **"Try again"** (`reset()`).
- **Not found:** "Nothing here", "That page or incident does not exist, or belongs to another workspace.", link "Report a problem". Cross-tenant incidents deliberately look like 404s. Do not reveal existence.

## 8. Shared components and helper libraries

| Component | Responsibility | Must keep |
|---|---|---|
| `IncidentPanel` | Security flag (`role="status"`), decision card (+ question), "What the message says" evidence card, "Details" frame card, footer `Incident {id} · bundle {bundle_id}` (monospace, `data-incident-id`) | Shared hover/active slot state links evidence ↔ table |
| `DecisionSummary` | Headline and detail from state, plus a `<dl>`: **Top team probability** (max of probs, %), **Plausible teams** (conformal set; ">4 → N of 12, not narrowed yet"), **Expected delay if routed** (`r_route` min or "not allowed"), **Delay if a person triages** (`c_def`). Holdout note | Heading has `tabIndex=-1` + `data-result-heading` for focus |
| `QuestionCard` | `fieldset/legend` question, radio options (≥ 44 px targets), "Optional. Your ticket is already saved.", **Send answer** (disabled until chosen) + **Skip** (same size) | Skip parity; `fieldset disabled` while busy |
| `EvidenceText` | The user's text with `<mark>` underlines; each mark carries an inline superscript slot label (sr-only "evidence for …"); hover activates the slot | Labels in text, not colour only; `lang="und"` |
| `FrameTable` | Rows only for stated slots: Detail · Understood as (ISO timestamps formatted `en-IN`) · Status (`StateBadge`) · **Team confidence without it** (attribution `delta_p` → "−12 pts" / "no change"). Missing slots as one line "Not stated: …" | Table semantics: caption, `th scope` |
| `StateBadge` | PRESENT "Found" ✓ ok · AMBIGUOUS "Unclear" ? warn · CONTRADICTED "Conflicting" ⚠ risk · MISSING "Not stated" ◌ muted | Word + icon + colour |
| `DetailMeter` | See §7.2 | `role="meter"` with aria values |
| `SyntheticBanner` | §6 | Non-dismissible |
| `WorkspaceHeading`, `LocalDraftNotice` | Page header pattern; local-draft notice | |
| `ArchitectureExplorer`, `McpSimulator` | §7.7 | |
| `components/ui/*` | shadcn primitives | Replace or extend freely |

| Library | Purpose |
|---|---|
| `lib/server-api.ts` | `apiFetch()` (server-only, attaches the key from the session; local-demo shared key only for a verified synthetic tenant), `relay()`, `isUuid()` |
| `lib/auth-session.ts` | Seal and open the AES-GCM session |
| `lib/bounded-body.ts` | Enforce byte limits before parsing; reject invalid UTF-8 |
| `lib/meter.ts` | Client lexicon meter; `SLOT_LABEL` (human slot names) |
| `lib/highlight.ts` | `segments(text, frame)`: UTF-16-safe evidence cutting |
| `lib/workspaces.ts` | `TEAMS`, `agreement` (κ, α), `parseCsv` (RFC-4180), `analyzeBounces`, `evaluatePredictions`, `downloadJson`, `draftSplit` |
| `lib/workspace-api.ts` | `workspaceApi<T>(path, method, body)`: calls `/api/workspaces/...`, surfaces `detail` |
| `lib/types.ts` | Aliases to generated types |

## 9. Domain dictionary

**12 teams (canonical enum → display):**

| Enum | Display |
|---|---|
| `Network` | Network |
| `Identity_Access` | Identity Access |
| `Email_Collab` | Email Collab |
| `Hardware_Endpoint` | Hardware Endpoint |
| `Software_Licensing` | Software Licensing |
| `Database` | Database |
| `Cloud_Infra` | Cloud Infra |
| `Security` | Security |
| `ERP_Finance` | ERP Finance |
| `HR_Systems` | HR Systems |
| `DevOps_CICD` | DevOps CICD |
| `Facilities_AV` | Facilities AV |

Today the display name is just underscore → space. Consider proper names and icons per team, for example "Email & Collaboration" and "Identity & Access".

**11 slots (enum → label in `SLOT_LABEL`):**
- `service`: System or app
- `component`: Part affected
- `symptom`: What happens
- `scope`: Who is affected
- `start_time`: When it started
- `frequency`: How often
- `environment`: Where you are
- `error_code`: Error code
- `recent_change`: Recent change
- `user_role_location`: Office or site
- `urgency`: Urgency

**Meter slots (6, live while typing):** service, error_code, scope, frequency, urgency, start_time.

**Epistemic states:** `PRESENT`, `MISSING`, `AMBIGUOUS`, `CONTRADICTED`.

**Incident states:**

| State | Meaning |
|---|---|
| `PENDING_CLARIFICATION` | Ticket saved; question open or evaluation pending |
| `ROUTED` | Sent to a team |
| `DEFERRED` | Sent to a person |
| `BOUNCED` | Reserved; not set by the API today |
| `RESOLVED` | Reserved; not set by the API today |
| `ERASED` | Content erased |

**Actions:** `ROUTE`, `ASK`, `DEFER`.

**Defer reasons → user copy** (keep the meaning):

| Reason | Copy |
|---|---|
| `shadow_mode` | This workspace is in shadow mode. Routing is not yet certified on its own tickets, so a person decides. |
| `no_conforming_team` | The message does not fit any team well enough. |
| `risk_above_defer_cost` | Routing now carries more expected delay than asking a person. |
| `set_too_large` | Too many teams remain plausible. |
| `critical_contradiction` | Key details in the message conflict. |
| `unmapped_queue` | The likely team has no mapped queue. |
| `security_escalation` | Possible security incident. No questions were asked; a person reviews it now, flagged for the security team. |
| `bundle_changed` | The model was updated while this question was open, so a person decides. |

**Channels:** `web`, `email`, `chat`, `itsm`, `agent`.

**Locales:** `en`, `hi`, `hinglish`.

**Question options** (service slot, from `packages/resolveit-frames/data/question_templates.json`): `vpn`, `wifi`, `email`, `teams`, `laptop`, `printer`, `sso`, `password`, `sap`, `hrms`, `database`, `cloud`, `cicd`, `licence`, `meeting_room`, plus "I don't know" / "मुझे नहीं पता" / "Pata nahi". Question text exists in en, hi and hinglish. The API returns `{text, options[{value,label}], skip_allowed, slot, template_id}`.

**Evidence sources (`SourceLayer`):** `rule`, `model`, `rule+model`, `user_answer`, `agent_asserted`, `human_correction`. These are useful to show as small provenance chips.

## 10. API contract the frontend consumes

Base: `RESOLVEIT_API_URL` (production `https://kumarwaibhav--resolveit-api-web.ap-south.modal.run`).
All requests carry a Bearer key, added server-side.

| Endpoint | Role | Request | Response |
|---|---|---|---|
| `GET /v1/me` | any | — | `IdentityView {tenant_id, role, is_synthetic, human_labeling_enrolled}` |
| `POST /v1/incidents` | admin, reviewer, agent | `{text (1..20000), channel="web", locale="en"}` | `IncidentView` (201) |
| `GET /v1/incidents/{id}` | admin, reviewer, viewer, agent | — | `IncidentView` (agent: `text` = null) |
| `POST /v1/incidents/{id}/answer` | admin, reviewer | `{answer: string\|null}` (≤ 200) | `IncidentView`. 409 if no open question; 403 for agent |
| `POST /v1/privacy/erasure` | admin | `{kind, identifier}` | `{incidents_erased}` |
| `GET /v1/review?blind=` | admin, reviewer | — | `ReviewList {human_labeling_enrolled, items: ReviewItem[]}` |
| `GET /v1/review/agreement` | admin, reviewer | — | `AgreementResult {n_pairs, observed_agreement, cohens_kappa, krippendorff_alpha, scope}` |
| `GET /v1/review/export` | admin | — | gold export JSON |
| `POST /v1/review/{id}/labels` | admin, reviewer | `HumanLabel {team, slots{slot:{state,value}}}` | `{incident_id, status, label_count}` |
| `POST /v1/review/{id}/adjudication` | admin | `HumanLabel` | same |
| `GET/PUT /v1/settings` | admin | `TenantSettings {version, timezone, queue_mapping, misroute_minutes, defer_minutes, routing_config_status}` | same |
| `GET /v1/evaluation` | admin, reviewer, viewer | — | `EvaluationStatus {bundle_id, provenance, auto_route_enabled, explanation, human_gold_count, frozen_test_count, human_test_accuracy}` |
| `POST /v1/bounce/analyze` | admin, reviewer | `{csv_text}` | `BounceReport {tickets, transitions, bounced_tickets, bounce_rate, median_reassignments, top_transitions, assumptions}` |
| `POST /mcp` | agent, admin | JSON-RPC | JSON-RPC |
| `GET /healthz` | public | — | `{status, synthetic_bundle_kind, synthetic_bundle_id}` |

**`IncidentView`:**

| Field | Type / meaning |
|---|---|
| `id` | UUID |
| `state` | Incident state |
| `channel`, `locale` | |
| `is_synthetic_tenant` | boolean |
| `security_trigger` | boolean |
| `routed_team` | `Team\|null` |
| `text` | `string\|null`; null when erased or for agents |
| `frame` | `SlotView[]` |
| `decision` | `Decision\|null` |
| `question` | `QuestionView\|null` |

**`SlotView`:** `{slot, state, value, evidence[{start, end, source, rule_id}]}`. Offsets are UTF-16.

**`Decision`:**

| Field | Meaning |
|---|---|
| `action` | ROUTE, ASK or DEFER |
| `bundle_id` | |
| `probs` | `number[12]` in `Team` enum order |
| `conformal` | `{teams[], alpha, class_conditional[]}` |
| `team`, `recommended_team` | |
| `ask_slot` | |
| `defer_reason` | |
| `r_route` | `number\|null`; null = route forbidden |
| `r_now`, `c_def` | |
| `tau_hat` | `number\|null`; null = shadow |
| `question_risks` | `[{slot, r_ask, r_after}]` |
| `no_ask_holdout` | |
| `attributions` | `[{slot, value, delta_p}]` |

**Status codes to design for:**

| Code | Meaning |
|---|---|
| 400 | Validation |
| 401 | Not signed in or credential rejected |
| 403 | Role or origin |
| 404 | Not found, or another tenant's incident |
| 409 | Question already closed, settings version conflict |
| 413 | Too large |
| 429 | API concurrency limit |
| 503 | Not configured |
| 5xx | Error boundary |

Plus a **cold start**: the first request after about 10 minutes idle can take 15–30 s.

## 11. Decision semantics the UI must explain honestly

- **Top team probability** is a calibrated model probability (temperature-scaled). It is **not** a guarantee.
- **Plausible teams** is the conformal prediction set at α = 0.10 (about 90% coverage). One team means confident; several means ambiguous; none means the system defers.
- **The route certificate:** a team is auto-routed only if its queue has a certified threshold (`tau_hat`) giving ≤ 5% misroute risk with 95% confidence on calibration data. On the synthetic test that gave 455/455 correct routes.
- **Expected delay if routed vs. delay if a person triages** is the cost comparison that drives ROUTE, ASK or DEFER. Present it as "minutes saved" storytelling. Never imply measured tenant outcomes: these costs are placeholders.
- **"Team confidence without it"** is an ablation: how much the top team's probability drops if that detail is removed. It is great for an animated "why" explanation.
- **No-ask holdout:** about 10% of tickets never get a question, for measurement. The UI says so in small print.
- **Security** never shows a model confidence as a security verdict.

---

# Part C — Design direction

## 12. Brand, colour and type

**Current tokens (light), from `globals.css`:**

| Token | Hex | Use |
|---|---|---|
| `--background` | `#f5f3ef` | Warm alabaster page |
| `--foreground` | `#24201e` | Text |
| `--card` | `#ffffff` | Surfaces |
| `--primary` / `--signal` / `--ring` | `#a52b3b` | **ResolveIT crimson.** Primary action and evidence underline only |
| `--accent` / `--accent-foreground` | `#f8e9eb` / `#8d2030` | Selected and active states |
| `--muted-foreground` | `#65605b` | Secondary text |
| `--border` / `--input` | `#ded9d2` / `#b8aea4` | Lines |
| `--ok` / `-surface` | `#17603a` / `#e3f3ea` | Found, success |
| `--warn` / `-surface` | `#7a4b00` / `#fbefd5` | Unclear, synthetic banner |
| `--risk` / `-surface` | `#9b1c1c` / `#fbe6e6` | Security, errors, conflict |
| `--info` / `-surface` | `#1d4e89` / `#e4eef9` | Info |
| Sidebar | `#211e1c` obsidian, link text `#ddd4cb`, active `#3b292a` with `#ffc1cc` text, brand accent `#ef8494` | |

- **Dark theme:** background `#1b1918`, card `#24211f`, primary `#ffadb8`. The rest is defined in the `prefers-color-scheme: dark` block.
- **Type:** system UI sans (with Noto Sans Devanagari in the stack); headings use **Georgia serif** (an editorial feel); monospace for numbers and IDs (`tabular-nums`).
- `scripts/check_contrast.mjs` verifies token contrast; update it when tokens change.

**Redesign brief (from your stated direction):**
- **Brand colours:** red, white and black, or leaning toward Anthropic-like warm neutrals (cream, ink, clay/crimson). Keep crimson as the single signal colour. Use black/ink and white/cream as the base, with one accent used sparingly. This is the "boldness spent in one place" rule.
- **Feel:** a billion-dollar B2B AI SaaS. Precise, calm, technical and trustworthy rather than playful. The product sells **trust under uncertainty**, so the visual language should feel like an instrument: measured, exact and legible.
- **Type proposal:** a modern grotesk for UI (Inter, Geist, or Söhne-like), a display serif or tight grotesk for hero numerals, and a mono for telemetry (Geist Mono or JetBrains Mono). It must render Devanagari (and later Tamil and Marathi) correctly: pair with **Noto Sans Devanagari / Noto Sans Tamil**.
- **Tokens first:** define primitive → semantic → component tokens, light and dark. Map state colours (ok, warn, risk, info) so they each pass 4.5:1 for text on their surface.

## 13. Motion, glass and "top AI startup" patterns, translated into rules

What you referenced (runlatent.ai, Linear, Vercel, Apple Liquid Glass, setproduct glass) and how to apply it **here**:

| Pattern | Where it fits in ResolveIT | Rules |
|---|---|---|
| **Interactive product sandbox in the hero** | A **marketing landing page** (new, see §19) with a live mini-intake. Type a sentence, watch the detail meter, slots and evidence light up. It can run **fully client-side** using `lib/meter.ts` (no API call, no cost, no cold start) | Label it as the rule preview; the full decision needs the API |
| **Bento grid + blueprint background** (dot or line grid, 1 px translucent borders) | Landing page proof section; Evaluation lab; Intake overview strip | Every number in a bento card must be measured (`docs/BUILD_STATE.md`): 455/455 synthetic auto-routes correct, 0 misroutes, 40 ms p50 pipeline on a typical ticket, 315 MB INT8 model, cosine 0.9999 to FP32, 11 slots, 12 teams. Always tag "synthetic test" |
| **Declarative UI motion** (Motion / Framer Motion) | Decision reveal; slot chips appearing; question card; tab indicators (shared layout); nav active pill | 150–300 ms, spring physics for layout, no motion on the critical path longer than 400 ms |
| **Animated SVG pipeline** (stroke-dashoffset, packets) | `/mcp` architecture explorer; the Intake processing state ("Rules → PII shield → Model → Risk gate → Decision") | Reflect real stages only; reduced-motion users see a static diagram |
| **Scroll-driven storytelling** (GSAP ScrollTrigger) | Landing page only: "From a messy call to a certified route" in 5 pinned steps, matching the demo storyline | Never inside the working app |
| **3D / shader** (Three.js, Spline, Rive) | Landing hero background only, lazy-loaded, paused off-screen | Not in workspaces. CSP and iframe rules apply (self-host Rive or Three; Spline embeds are iframes and blocked) |
| **Glassmorphism / Liquid Glass** | Floating layer only: top bar, command palette, popovers, toasts, the question sheet | **Never on content surfaces** (text over blur hurts legibility). Provide a `prefers-reduced-transparency` fallback (solid surface). Contrast must still pass |
| **Data-backed specificity** | Copy everywhere: "0 of 455 auto-routes wrong on the synthetic test" beats "highly accurate" | Every claim cites its provenance (synthetic vs real) |

**Psychology for "people love staying":**
- **Instant feedback:** the meter updates per keystroke.
- **Progressive disclosure:** headline first, then why, then the raw numbers.
- **Visible competence:** evidence in their own words.
- **Low friction:** one question at most, Skip always available.
- **Calm trust signals:** shadow-mode honesty and the synthetic banner.

**Motion accessibility:** honour `prefers-reduced-motion` (the E2E gate runs with `reduced_motion="reduce"`). No auto-playing loops longer than 5 s without a pause control. Nothing flashes more than 3 times per second.

## 14. Accessibility requirements (gate-enforced)

Gate G4 runs axe-core on `/`, `/review`, `/bounce`, `/evaluation`, `/mcp` and `/settings` at **1440 px light** and **320 px dark** with reduced motion, and requires:
- **0 violations** (WCAG 2.x A/AA rule set).
- **No horizontal overflow** at 320 px.

Requirements you must keep:
- **Semantics:** one H1 per page, logical headings, landmarks (`nav`, `main`, `aside`), and table semantics for tabular data.
- **Keyboard:** everything reachable; visible focus ring (`--ring`); skip link; focus moves to the result heading after submit; Esc closes overlays; no keyboard traps.
- **Live regions:** result region `aria-live="polite"`; meter count; status and alert messages (`role="status"` / `role="alert"`).
- **Forms:** every input has a `<label>`; radio groups use `fieldset/legend`; help text uses `aria-describedby`; errors are announced.
- **Targets:** ≥ 44 × 44 px on touch (current `min-h-11`).
- **Colour:** contrast ≥ 4.5:1 for text (3:1 for large text and UI parts); state never by colour alone.
- **Language:** mark Hindi spans with `lang="hi"`; user text uses `lang="und"`.
- **Tables:** `caption` (sr-only allowed), `th scope`.
- **Motion:** reduced-motion and reduced-transparency fallbacks.

## 15. Internationalisation and scripts

- **Languages:**
  - UI chrome is English today.
  - User input and questions support `en`, `hi` and `hinglish`.
  - **Marathi (`mr`) and Tamil (`ta`) are planned** (training v2), and so are voice transcripts.
- **Design for:** Devanagari and Tamil glyph heights (more line-height), mixed-script lines, long Hinglish words, and right-to-left is not needed.
- **Numbers and dates:**
  - Dates via `Intl.DateTimeFormat("en-IN")`.
  - Timestamps are in the tenant timezone (default Asia/Kolkata).
  - Use `tabular-nums` for metrics.
- **Text:** never truncate user text in a way that breaks evidence offsets. Highlighting relies on exact UTF-16 slicing.
- **Future:** extract UI strings into a message catalogue (for example `next-intl`) so the UI chrome can be localised later.

## 16. Responsive behaviour

| Breakpoint | Current behaviour | Keep or improve |
|---|---|---|
| ≥ 1280 px | Fixed sidebar + 2-column Intake (form | result) | Consider a 3-pane review layout |
| ≤ 1100 px | Narrower sidebar; workspace grids become 1 column; headings stack | |
| ≤ 760 px | Sidebar becomes a top horizontal scroll strip; tenant switch and footer hidden; metric grids 1 column; architecture track 2 columns | Consider a bottom tab bar or drawer on mobile |
| 320 px | Must not overflow (gate) | Tables need horizontal scroll wrappers (`.data-table-wrap`) |

Tested widths: 320, 768, 1024, 1440.

## 17. Performance budgets

- **First load JS:** currently about 103 kB shared, and about 108–120 kB per route. Budget **≤ 170 kB per workspace route**. Heavy visuals (Three.js, GSAP, Rive) belong on the landing page only and are lazy-loaded.
- **LCP** ≤ 2.0 s on 4G for the landing page; **INP** ≤ 200 ms (the meter runs on every keystroke, so keep it cheap; it is regex-only today).
- **Fonts:** at most 3 families, `next/font` self-hosted, `display: swap`, with Devanagari and Tamil subsets.
- **Cold start:** design a skeleton plus a "waking the engine" state for the first request. Never block typing.

---

# Part D — Delivery

## 18. Tests and gates that must keep passing

| Check | Command | What breaks it |
|---|---|---|
| Types | `npm run typecheck` | Removing generated aliases; wrong API shapes |
| Lint | `npm run lint` | ESLint (next config) |
| Unit | `npx vitest run` (22 tests) | `auth-session`, `bounded-body`, `highlight-meter`, `middleware`, `workspaces`. Keep these libraries' behaviour |
| Build | `npm run build` | |
| Contrast | `node scripts/check_contrast.mjs` | Token changes |
| Browser E2E + axe (gate G4) | `scripts/runtime_stage_c.py` → `apps/web/e2e/stage_c.py` and `journeys.py` | **Visible labels and names below** |

**E2E selectors in use today.** If you rename these, update `e2e/*.py` in the same change:
- Labels: `"Individual API credential"`, `"What is going wrong?"`, `"The user's report, verbatim"`, `"Answer"`, `"Quote from the report"`, radio option labels (for example `"vpn"`).
- Buttons: `"Sign in"`, `"Send ticket"`, `"Send answer"`, `"Skip"`, `"Call submit_incident"`, `"Retry with answer"`.
- Headings and texts: `"Make judgment visible."` (post-login landing), `"Nothing here"`, `"Synthetic demo data."`, the meter text `"4 of 6"` for `😀 VPN is down again for the whole floor, urgent`, `"Round trip 1:"`, `"Round trip 2: complete"`, `'"routed_team": "Network"'`.
- Attributes: `data-incident-id` (the E2E reads the incident id), `data-result-heading`.

## 19. Gaps and opportunities

**Missing product surfaces:**
1. **Marketing / landing page** (public, `/`, with the app moving to `/app/*` or staying at the root behind auth). This is the investor and stage story: interactive sandbox, proof bento, pipeline animation, and a "Book a demo" CTA. Today there is no public page; production redirects straight to `/login`.
2. **Incidents inbox** (list, filter, search: state, team, security, date) linking to the permalinks. Needs a new list endpoint (the API has none yet).
3. **Ops dashboard:** routed vs asked vs deferred over time, per-queue certificate status, deflection minutes saved. Needs aggregate endpoints.
4. **Incident-storm and duplicate view** ("40 calls: VPN, Pune, 10 min"), from the competitive research. Needs a backend.
5. **Voice intake** (planned): call recording/transcript view with ASR confidence and language tag. The microphone is already allowed by Permissions-Policy.
6. **SLA timers** and runbook suggestions after routing (outside the decision path).
7. **Shell gaps:** Sign out, the identity/role chip, role-aware nav, a real tenant switcher, a theme toggle, a cold-start indicator, a command palette (⌘K), toasts for async results.

**Existing data not shown yet:**
- `question_risks` (expected risk before and after asking each question). It could visualise *why this question*.
- `tau_hat` and certificate per queue.
- The `SourceLayer` of evidence.
- Bounce `top_transitions` and `median_reassignments`.
- Evaluation `human_test_accuracy`.
- Settings `routing_config_status`.
- Probability distribution across all 12 teams. A ranked bar list is a strong visual.

**Known UX debts:**
- The tenant switcher is decorative.
- Login lands on `/review`.
- Viewers see admin pages and hit 403.
- No pagination on review (the API supports `limit`/`after`).
- Raw JSON in the adjudication `<details>`.
- Footer language list will be out of date once mr/ta ship.

## 20. Staggered rebuild plan

Build in this order. Each stage ends green on the §18 checks before the next one starts.

| Stage | Scope | Done when |
|---|---|---|
| **0. Foundations** | Token system (primitive, semantic, component; light, dark, high-contrast); type scale with Devanagari and Tamil; spacing, radius and elevation; motion tokens (durations, springs, reduced-motion); icon set; update `check_contrast.mjs` | Contrast script passes; a token preview page renders both themes |
| **1. Component library** | Rebuild primitives on shadcn/Radix: Button, Input, Textarea, Select/Combobox, RadioGroup, Checkbox, Switch, Tabs, Table, Badge, StateBadge, Card, Sheet/Dialog, Toast, Tooltip, Skeleton, EmptyState, MetricCard, CodeBlock (JSON), DangerZone, Banner (synthetic, non-dismissible), plus a Storybook or a `/dev/ui` page | Each component has keyboard and screen-reader behaviour checked; axe clean in isolation |
| **2. App shell** | Sidebar/nav (role-aware), top bar with identity chip, sign out, theme toggle, cold-start indicator, command palette, skip link, responsive drawer | 320 px no overflow; nav `aria-current` works |
| **3. Intake + incident** (the demo core) | Form, live meter, security hint, staged decision reveal, evidence text, frame table with attribution, question sheet, permalink page | The 4 demo tickets behave as in §7.2; E2E journeys pass |
| **4. Review console** | Queue list, record, 11-slot label form, adjudication diff, practice mode | Live labelling round trip works; κ/α show "Undefined" correctly |
| **5. Bounce + Evaluation** | CSV import, flow visual, metrics; evaluation provenance, honest empty states, upload metrics | Sample CSV gives 2 reassignments for SYN-101 |
| **6. Agent hand-off** | MCP inspector, JSON viewer, animated architecture pipeline | Round trip 2 completes with `routed_team: Network` |
| **7. Settings** | Queue map, routing controls, timezone combobox, danger-zone erasure | Version conflict handled; erasure confirmation enforced |
| **8. Landing page** (optional, recommended) | Public marketing site with client-only sandbox, proof bento, scroll story, CTA | LCP ≤ 2 s; every number cited |
| **9. Polish and audit** | Motion pass, empty, loading and error states everywhere, i18n string extraction, performance budgets, full G4 gate | `run_all_gates.py --gate G4` passes; manual screen-reader pass |

## 21. Final pre-ship checklist

- [ ] No client-side code calls the Python API directly; no secrets in client bundles (`grep NEXT_PUBLIC` is empty).
- [ ] Synthetic banner on every synthetic view; non-dismissible.
- [ ] No hard-coded metrics inside the app; landing-page numbers cite provenance.
- [ ] All 8 defer reasons and all 6 incident states have designed copy and visuals.
- [ ] Security ticket path: no question, instant flag, no extra confirmation.
- [ ] Skip is the same size as Send.
- [ ] Erasure needs confirmation and explains the backup caveat.
- [ ] Evidence highlighting is correct with emoji and Devanagari (test string: `😀 VPN is down again for the whole floor, urgent`).
- [ ] Loading, empty, error, 401, 403, 404, 409, 413, 429 and cold-start states designed for every data view.
- [ ] axe: 0 violations at 1440 light and 320 dark; no horizontal overflow; reduced motion respected.
- [ ] Keyboard-only run through every page; focus visible; focus lands on the result after submit.
- [ ] E2E selectors updated together with any label changes; `npm run typecheck && npm run lint && npx vitest run && npm run build` all green.
- [ ] `npm run gen:types` produces no diff; lexicon untouched or regenerated from Python.
- [ ] Commits authored as Kumar Waibhav Akshat <kwa.waibhav@gmail.com>.

---

*Related docs: `docs/DEMO_WALKTHROUGH.md` (demo script and tickets), `docs/DEPLOYMENT.md` (hosting),
`docs/BUILD_STATE.md` (measured numbers you may quote), `docs/research/competitive_scan.md`
(feature ideas from 10 competitor repos), `docs/FINAL_RELEASE_SCORECARD.md` (gates).*

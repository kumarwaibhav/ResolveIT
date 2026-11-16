# Competitive scan: 10 public triage repos (2026-11-16)

Method: shallow clones, README plus classifier/router/confidence source read. Numbers quoted by
publishers (ASR WER) are self-reported.

## Findings in one line each
- varunsai-k/agentic-ai-ticket-resolution: LangGraph LLM classify + Qdrant RAG + human interrupt; confidence is `random.choice([60,65,75])` (src/nodes.py).
- SebAustin/AI-Agents-with-LangChain-and-LangGraph: LLM supervisor routes; 0.6/0.7 similarity escalation; JSONL logs; customer-support domain.
- m3yyyyy/it-incident-triage-agent: deterministic keyword triage, runbooks, always-human approval, audit timeline; confidence is a hand formula.
- smitdighe/Undertow (strongest): MiniLM dedupe (cos>=0.87), Postgres job queue, LLM classify, approve/edit loop, correction log, nightly LLM-judged F1 CI gate; read paths unauthenticated.
- paphaphin-spai/support-ticket-triage-agent: LLM tool loop, Chroma KB, hand priority score to SLA hours; no HITL.
- abieltesfai10-rgb/ai-helpdesk-assistant: single Streamlit prompt demo.
- shib1111111/Incident-Triage: NOC syslog; LLM analyst checked by deterministic guardrail + grounding evaluator.
- aperritano/langgraph-customer-support-agent: Ollama ReAct; 10-scenario LangSmith eval.
- Samanosukeh/langgraph-ticket-triage: LLM map-reduce multi-ticket extraction with evidence field.
- arindam-b/incident-triage-agents: GCP alert -> Gemini RCA; notification step in README not implemented; key in Terraform.

Gaps none of them fill: statistically certified routing error, principled abstain, value-of-information
clarifying question, voice intake, Indian languages, hard security override, held-out labelled evaluation.

## Features to add (decision path = DP, outside = OUT)
1. Certified routing with visible risk bound (DP, exists).
2. Security hard override before any model (DP, exists).
3. One-question EVSI clarification with posterior before/after (DP, exists).
4. Voice intake: VAD -> ASR -> frame (OUT; low ASR confidence becomes an ASK/DEFER feature).
   Candidates: AI4Bharat IndicConformer 600M (MIT, gated), IndicWhisper/Vistaar (MIT),
   Whisper large-v3 (MIT), Indic-Transcribe-core (custom licence: check commercial terms).
   Avoid Meta MMS (CC-BY-NC).
5. Frame slots linked to transcript offsets (exists for text).
6. Incident-storm clustering / dedupe into parent incidents (OUT; deterministic priority bump).
7. Defer with reason codes (DP).
8. Hash-chained immutable decision audit (OUT).
9. Reviewer corrections -> periodic conformal recalibration + coverage drift alarms (OUT, offline).
10. Per-language labelled evaluation harness incl. ASR channel (OUT, offline).
11. Runbook suggestion after routing (OUT).
12. SLA timers from call timestamp (OUT).
13. Read-back confirmation via TTS (OUT; a "no" feeds the ASK gate).
14. ServiceNow/JSM push with idempotency keys (OUT).
15. Transcript PII redaction before storage (exists for text).

## Demo storyline
1. Hinglish call -> live transcript with ASR confidence and language tag.
2. Frame card fills, each slot highlighted on its transcript span.
3. Storm view: call joins an open cluster; priority bump by explicit rule.
4. Certified route with set size 1 and the risk statement.
5. Vague Tamil call -> EVSI question -> answer -> route or reasoned defer.
6. Security call -> SOC P1, rule id in audit, no model consulted.
7. Ops view: SLA, runbook, audit chain, per-language risk/coverage dashboard; LLM-routed baseline vs ResolveIT.

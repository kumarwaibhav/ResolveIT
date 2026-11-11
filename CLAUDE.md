# ResolveIT engineering rules

These rules bind every contributor, human or AI. `.cursorrules` points here.

## Contracts
- `packages/resolveit-core/resolveit_core/schemas/` is the only place data shapes are defined.
  OpenAPI and web types are generated from it. Docs link to it; they never copy it.

## Data honesty
- LLM labels are `llm_silver`. Never call them gold, human, or annotated by people.
- Evaluation numbers come from the frozen human test split only. Synthetic tenants never feed metrics.
- No invented agreement scores, dataset sizes or benchmark results. A missing number stays missing.

## Calibration
- Temperature, thresholds, tau, cut-offs and theta are fitted on outputs of the shipped INT8 ONNX file.
- Model file and calibration artefacts ship as one bundle with one hash.
- Calibration data is the random audit stream. Corrections on deferred tickets go to training only.
- The empty conformal set is a result: DEFER with `no_conforming_team`.
- `tau_hat = None` means shadow mode. Shadow mode never auto-routes.

## Text handling
- Rules run on raw text before masking. The masker never touches protected error-code spans.
- Spans are stored as raw code-point offsets. Convert to UTF-16 only at the API edge.
- Ticket text never goes into logs, traces, metrics or experiment trackers.

## Database (applies from Phase 4)
- All access goes through `tenant_tx(tenant_id)`. `tenant_id` comes from the verified credential.
- Every tenant table has RLS enabled and forced. The app role has no BYPASSRLS.

## Quality bar
- `ruff check`, `mypy --strict`, `pytest` green before a step is called done.
- A gate that cannot run is reported as not run, never as passed.

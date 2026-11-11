# ResolveIT

Phase 2 deliverable: `packages/resolveit-core` (contracts, OffsetMap, rule engine,
PII masker, calibration, gate, evidence) and the `packages/resolveit-frames` seed data.

    cd packages/resolveit-core
    pip install -e ".[dev]"
    bash ../../scripts/ci_gates/g1_core.sh

Not in this drop: model training, ONNX bundle, API, worker, web app. No trained
model and no human-labelled data exist yet, so nothing here reports model accuracy.

"""Load and serve the verified INT8 release-candidate bundle.

The directory is verified against its SHA-256 manifest and a pinned bundle id,
then every served artifact is read into memory once, digest-checked, and loaded
from those bytes (never by reopening paths, so no verify-then-load window). Any failure leaves
the caller on the rule-based bundles: the API never serves an unverified model.
The bundle is synthetic-provenance (production_authorized=false), so it is
only ever attached to synthetic tenants; real tenants stay in shadow mode.
"""

from __future__ import annotations

import io
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray
from resolveit_core.calibrate.conformal_selective import ConformalCalibrator
from resolveit_core.explain.ablation import LinearTeamHead
from resolveit_core.gate.bayes_evsi import CostMatrix, ThetaTable
from resolveit_core.model.bundle_verify import read_verified, verify_bundle
from resolveit_core.model.features import FEATURE_VERSION, POOLED_WIDTH, frame_encoder
from resolveit_core.schemas import TEAMS, Slot

from resolveit_api.bundles import Bundle

log = logging.getLogger("resolveit.bundle")
MAX_TOKENS = 192
SERVED = ("model_int8.onnx", "tokenizer/tokenizer.json", "calibration.json", "linear_head.npz")


class TextEncoder:
    """Masked text -> pooled vector, with exactly the runtime settings used for calibration."""

    def __init__(self, model: bytes, tokenizer_json: bytes, threads: int) -> None:
        import onnxruntime as ort  # type: ignore[import-untyped]
        from tokenizers import Tokenizer  # type: ignore[import-untyped]

        self._tok = Tokenizer.from_str(tokenizer_json.decode("utf-8"))
        self._tok.enable_truncation(max_length=MAX_TOKENS)
        self._tok.no_padding()
        options = ort.SessionOptions()
        options.intra_op_num_threads = threads
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        options.enable_cpu_mem_arena = False
        self._session = ort.InferenceSession(model, options, providers=["CPUExecutionProvider"])

    def __call__(self, masked_text: str) -> NDArray[np.float64]:
        ids = self._tok.encode(masked_text).ids
        out = self._session.run(
            ["pooled"],
            {
                "input_ids": np.asarray([ids], dtype=np.int64),
                "attention_mask": np.ones((1, len(ids)), dtype=np.int64),
            },
        )[0][0]
        vector = np.asarray(out, dtype=np.float64)
        if vector.shape != (POOLED_WIDTH,) or not np.isfinite(vector).all():
            raise RuntimeError("encoder returned an invalid pooled vector")
        return vector


@dataclass(frozen=True, slots=True)
class BundleStatus:
    kind: str
    bundle_id: str | None
    detail: str


def _queue_map(raw: dict[str, Any]) -> dict[int, float | None]:
    names = [t.value for t in TEAMS]
    return {names.index(team): (None if tau is None else float(tau)) for team, tau in raw.items()}


def load_trained_bundle(directory: Path, expected_id: str, threads: int) -> Bundle:
    if not expected_id:
        raise ValueError("a pinned bundle id from the trusted release channel is required")
    verified = verify_bundle(directory, expected_id)
    blobs = read_verified(directory, expected_id, SERVED)
    cal = json.loads(blobs["calibration.json"].decode("utf-8"))
    if cal.get("production_authorized") is not False or cal.get("feature_version") != FEATURE_VERSION:
        raise ValueError("bundle provenance or feature contract does not match this server")
    head_file = np.load(io.BytesIO(blobs["linear_head.npz"]), allow_pickle=False)
    head = LinearTeamHead(
        np.asarray(head_file["weights"], dtype=np.float64),
        np.asarray(head_file["bias"], dtype=np.float64),
        frame_encoder(),
        int(head_file["pooled_dim"]),
    )
    conformal = ConformalCalibrator(
        alpha=float(cal["alpha"]),
        thresholds=np.asarray(cal["q_hat_y"], dtype=np.float64),
        class_conditional=np.asarray(cal["class_conditional_supported"], dtype=np.bool_),
        pooled_threshold=float(cal["pooled_q_hat"]),
        class_counts=np.asarray(cal["class_counts"], dtype=np.int64),
    )
    theta = ThetaTable(
        {Slot(s): tuple(v) for s, v in cal["theta_values"].items()}, kappa=float(cal["theta_kappa"])
    )
    for slot_name, counts in cal["theta_counts"].items():
        array = np.asarray(counts, dtype=np.float64)
        if array.shape != theta.counts[Slot(slot_name)].shape:
            raise ValueError("theta table shape mismatch")
        theta.counts[Slot(slot_name)] = array
    encoder = TextEncoder(blobs.pop("model_int8.onnx"), blobs["tokenizer/tokenizer.json"], threads)
    return Bundle(
        bundle_id=f"int8-synthetic-{verified['bundle_id'][:16]}",
        synthetic=True,
        head=head,
        temperature=float(cal["temperature"]),
        conformal=conformal,
        tau_hat=None,
        theta=theta,
        costs=CostMatrix(np.asarray(cal["L"], dtype=np.float64), float(cal["defer_minutes"])),
        queue_tau_hat=_queue_map(cal["queue_tau_hat"]),
        answer_queue_tau_hat=_queue_map(cal["answer_queue_tau_hat"]),
        encoder=encoder,
    )


def showcase_bundle(fallback: Bundle) -> tuple[Bundle, BundleStatus]:
    """The trained bundle when RESOLVEIT_BUNDLE_DIR verifies, otherwise the rule-based demo bundle."""
    raw = os.environ.get("RESOLVEIT_BUNDLE_DIR", "").strip()
    if not raw:
        return fallback, BundleStatus(
            "rules_synthetic_demo", fallback.bundle_id, "no trained bundle configured"
        )
    expected = os.environ.get("RESOLVEIT_BUNDLE_ID", "").strip()
    try:
        threads = int(os.environ.get("RESOLVEIT_ENCODER_THREADS", "4"))
        bundle = load_trained_bundle(Path(raw), expected, threads)
    except Exception as exc:  # fail closed to the rule bundle; never serve an unverified model
        log.error("trained bundle rejected: %s", type(exc).__name__)
        return fallback, BundleStatus("rules_synthetic_demo", fallback.bundle_id, "trained bundle rejected")
    return bundle, BundleStatus("int8_trained_synthetic", bundle.bundle_id, "verified manifest")


__all__ = ["BundleStatus", "TextEncoder", "load_trained_bundle", "showcase_bundle"]

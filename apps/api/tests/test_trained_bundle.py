"""Serving checks for the verified INT8 bundle. Skipped unless RESOLVEIT_BUNDLE_DIR points at one."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest
from resolveit_core.gate.bayes_evsi import ChannelCosts
from resolveit_core.schemas import Action, Slot, Team

from resolveit_api.bundles import synthetic_demo_bundle
from resolveit_api.pipeline import evaluate, finalize
from resolveit_api.trained_bundle import load_trained_bundle, showcase_bundle

BUNDLE = os.environ.get("RESOLVEIT_BUNDLE_DIR", "")
PINNED = os.environ.get("RESOLVEIT_BUNDLE_ID", "")
pytestmark = pytest.mark.skipif(not (BUNDLE and PINNED), reason="no pinned trained bundle configured")
NOW = datetime(2026, 11, 16, 6, 0, tzinfo=UTC)
COSTS = ChannelCosts(c_ask=1.0, c_ghost=10.0)


@pytest.fixture(scope="module")
def bundle():  # type: ignore[no-untyped-def]
    return load_trained_bundle(Path(BUNDLE), PINNED, threads=4)


def test_clear_english_ticket_routes_with_evidence(bundle) -> None:  # type: ignore[no-untyped-def]
    ev = evaluate("Outlook keeps crashing for the whole floor since this morning, urgent", NOW,
                  "Asia/Kolkata", bundle, COSTS, holdout=False)
    d = ev.decision
    assert d.bundle_id.startswith("int8-synthetic-")
    assert d.recommended_team is Team.EMAIL_COLLAB
    assert d.action is Action.ROUTE and d.team is Team.EMAIL_COLLAB
    assert d.attributions and d.attributions[0].slot is Slot.SERVICE and d.attributions[0].delta_p > 0
    assert abs(sum(d.probs) - 1) < 1e-9


def test_vague_hinglish_ticket_asks_service_and_answer_routes(bundle) -> None:  # type: ignore[no-untyped-def]
    ev = evaluate("subah se kuch kaam nahi kar raha, jaldi dekho", NOW, "Asia/Kolkata", bundle, COSTS,
                  holdout=False)
    assert ev.decision.action is Action.ASK and ev.decision.ask_slot is Slot.SERVICE
    final = finalize(ev.decision, ev.frame, Slot.SERVICE, "vpn", bundle, COSTS, False)
    assert final.action is Action.ROUTE and final.team is Team.NETWORK
    skipped = finalize(ev.decision, ev.frame, Slot.SERVICE, None, bundle, COSTS, False)
    assert skipped.action is Action.DEFER


def test_security_ticket_points_at_security(bundle) -> None:  # type: ignore[no-untyped-def]
    ev = evaluate("I clicked a suspicious link and my account got hacked", NOW, "Asia/Kolkata", bundle,
                  COSTS, holdout=False)
    assert ev.rules.security_trigger
    assert ev.decision.recommended_team is Team.SECURITY
    assert ev.decision.action is Action.DEFER and ev.decision.ask_slot is None
    assert ev.decision.defer_reason == "security_escalation"


def test_holdout_never_asks(bundle) -> None:  # type: ignore[no-untyped-def]
    ev = evaluate("kuch kaam nahi kar raha", NOW, "Asia/Kolkata", bundle, COSTS, holdout=True)
    assert ev.decision.action is not Action.ASK


def test_encoder_is_deterministic(bundle) -> None:  # type: ignore[no-untyped-def]
    a = bundle.encoder("VPN is down")
    b = bundle.encoder("VPN is down")
    assert np.array_equal(a, b)


def test_tampered_or_wrong_id_falls_back_to_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RESOLVEIT_BUNDLE_ID", "0" * 64)
    fallback = synthetic_demo_bundle()
    served, status = showcase_bundle(fallback)
    assert served is fallback and status.kind == "rules_synthetic_demo"


def test_missing_pinned_id_falls_back_to_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RESOLVEIT_BUNDLE_ID", "")
    fallback = synthetic_demo_bundle()
    served, status = showcase_bundle(fallback)
    assert served is fallback and status.kind == "rules_synthetic_demo"


def test_pinned_bundle_is_served_and_synthetic_only() -> None:
    fallback = synthetic_demo_bundle()
    served, status = showcase_bundle(fallback)
    assert status.kind == "int8_trained_synthetic"
    assert served.synthetic is True and served.encoder is not None

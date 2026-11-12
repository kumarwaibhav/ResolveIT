"""Decision bundles available before a trained model exists.

shadow_bundle: hand-set rule weights, NO calibration, tau_hat = None. It can
recommend a team to a human reviewer and can never auto-route. Every real
tenant gets this until human-labelled calibration data exists.

synthetic_demo_bundle: the same head, calibrated on generated tickets so the
demo tenant can show ROUTE / ASK / DEFER end to end. Its numbers describe the
generator, not any real workload. It is served only to tenants flagged
is_synthetic and must never appear in evaluation.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np
from resolveit_core.calibrate.conformal_selective import (
    ConformalCalibrator,
    fit_conformal,
    fit_temperature,
    select_tau,
    softmax,
)
from resolveit_core.explain.ablation import FrameEncoder, LinearTeamHead
from resolveit_core.gate.bayes_evsi import CostMatrix, ThetaTable
from resolveit_core.schemas import N_TEAMS, TEAMS, UNKNOWN_ANSWER, Slot, Team

SERVICE_TEAM: dict[str, Team] = {
    "vpn": Team.NETWORK,
    "wifi": Team.NETWORK,
    "sso": Team.IDENTITY_ACCESS,
    "password": Team.IDENTITY_ACCESS,
    "email": Team.EMAIL_COLLAB,
    "teams": Team.EMAIL_COLLAB,
    "laptop": Team.HARDWARE_ENDPOINT,
    "printer": Team.HARDWARE_ENDPOINT,
    "licence": Team.SOFTWARE_LICENSING,
    "database": Team.DATABASE,
    "cloud": Team.CLOUD_INFRA,
    "sap": Team.ERP_FINANCE,
    "hrms": Team.HR_SYSTEMS,
    "cicd": Team.DEVOPS_CICD,
    "meeting_room": Team.FACILITIES_AV,
}
VOCAB: dict[Slot, tuple[str, ...]] = {
    Slot.SERVICE: tuple(SERVICE_TEAM),
    Slot.SCOPE: ("single_user", "department_wide", "org_wide"),
    Slot.FREQUENCY: ("constant", "intermittent", "recurring", "first_time"),
    Slot.URGENCY: ("high", "low"),
}
POOLED_DIM = 1  # [security_trigger]; replaced by the encoder's pooled vector once a model ships
DEFAULT_COSTS = CostMatrix.uniform(
    misroute_minutes=240.0, c_def=45.0
)  # placeholders until bounce data exists


@dataclass(frozen=True, slots=True)
class Bundle:
    bundle_id: str
    synthetic: bool
    head: LinearTeamHead
    temperature: float
    conformal: ConformalCalibrator
    tau_hat: float | None
    theta: ThetaTable
    costs: CostMatrix


def _head() -> LinearTeamHead:
    enc = FrameEncoder(VOCAB)
    w = np.zeros((N_TEAMS, POOLED_DIM + enc.dim))
    w[TEAMS.index(Team.SECURITY), 0] = 4.0
    for service, team in SERVICE_TEAM.items():
        w[TEAMS.index(team), POOLED_DIM + enc.index(Slot.SERVICE, service)] = 3.0
    return LinearTeamHead(w, np.zeros(N_TEAMS), enc, POOLED_DIM)


def _digest(*arrays: np.ndarray) -> str:
    h = hashlib.sha256()
    for a in arrays:
        h.update(np.ascontiguousarray(a, dtype=np.float64).tobytes())
    return h.hexdigest()[:16]


def shadow_bundle() -> Bundle:
    head = _head()
    open_sets = ConformalCalibrator(
        alpha=0.10,
        thresholds=np.full(N_TEAMS, 1.0),
        class_conditional=np.zeros(N_TEAMS, dtype=np.bool_),
        pooled_threshold=1.0,
        class_counts=np.zeros(N_TEAMS, dtype=np.int64),
    )
    return Bundle(
        bundle_id=f"rules-shadow-uncalibrated-{_digest(head.weights)}",
        synthetic=False,
        head=head,
        temperature=1.0,
        conformal=open_sets,
        tau_hat=None,
        theta=ThetaTable(VOCAB),
        costs=DEFAULT_COSTS,
    )


def _generate(
    rng: np.random.Generator, per_team: int
) -> tuple[list[dict[Slot, str]], np.ndarray, np.ndarray]:
    services = list(SERVICE_TEAM)
    by_team: dict[Team, list[str]] = {t: [s for s, tt in SERVICE_TEAM.items() if tt is t] for t in TEAMS}
    frames: list[dict[Slot, str]] = []
    pooled: list[float] = []
    labels: list[int] = []
    for y, team in enumerate(TEAMS):
        for _ in range(per_team):
            values: dict[Slot, str] = {}
            roll = rng.random()
            if roll < 0.78 and by_team[team]:
                values[Slot.SERVICE] = str(rng.choice(by_team[team]))
            elif roll >= 0.98:
                values[Slot.SERVICE] = str(rng.choice(services))
            if rng.random() < 0.5:
                values[Slot.SCOPE] = str(rng.choice(VOCAB[Slot.SCOPE]))
            flag = float(rng.random() < (0.85 if team is Team.SECURITY else 0.001))
            frames.append(values)
            pooled.append(flag)
            labels.append(y)
    return frames, np.array(pooled), np.array(labels, dtype=np.int64)


def synthetic_demo_bundle(seed: int = 20261112) -> Bundle:
    rng = np.random.default_rng(seed)
    head = _head()

    def logits(frames: list[dict[Slot, str]], pooled: np.ndarray) -> np.ndarray:
        return np.stack([head.logits(np.array([p]), f) for f, p in zip(frames, pooled, strict=True)])

    sf, sp, sy = _generate(rng, 50)
    temperature = fit_temperature(logits(sf, sp), sy)
    cf, cp, cy = _generate(rng, 200)
    probs = softmax(logits(cf, cp), temperature)
    conformal = fit_conformal(probs, cy, alpha=0.10, min_class_n=150, seed=seed)
    routed_to = np.argmin(probs @ DEFAULT_COSTS.delay, axis=1)
    tau = select_tau(probs.max(axis=1), routed_to != cy, epsilon=0.05, delta=0.05)
    theta = ThetaTable(VOCAB)
    tf, _, ty = _generate(rng, 200)
    for values, y in zip(tf, ty, strict=True):
        for slot in (Slot.SERVICE, Slot.SCOPE):
            theta.add(slot, values.get(slot, UNKNOWN_ANSWER), int(y))
    digest = _digest(head.weights, np.array([temperature]), conformal.thresholds, theta.counts[Slot.SERVICE])
    return Bundle(
        bundle_id=f"synthetic-demo-{digest}",
        synthetic=True,
        head=head,
        temperature=temperature,
        conformal=conformal,
        tau_hat=tau.tau_hat,
        theta=theta,
        costs=DEFAULT_COSTS,
    )


__all__ = [
    "DEFAULT_COSTS",
    "POOLED_DIM",
    "SERVICE_TEAM",
    "VOCAB",
    "Bundle",
    "shadow_bundle",
    "synthetic_demo_bundle",
]

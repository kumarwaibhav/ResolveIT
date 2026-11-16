"""Authoritative persistent enterprise workspace HTTP contracts."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from resolveit_core.schemas import EpistemicState, Slot, Team

ReviewSplit = Literal["training", "scaling", "calibration", "frozen_test"]
ReviewStatus = Literal["unlabeled", "single_label", "needs_adjudication", "gold", "synthetic_labeled"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IdentityView(Contract):
    tenant_id: UUID
    role: str
    is_synthetic: bool
    human_labeling_enrolled: bool


class HumanSlotLabel(Contract):
    state: EpistemicState
    value: str | None = Field(default=None, max_length=500)


class HumanLabel(Contract):
    team: Team
    slots: dict[Slot, HumanSlotLabel]


class ReviewItem(Contract):
    incident_id: UUID
    text: str | None
    locale: str
    is_synthetic: bool
    split: ReviewSplit
    audit_selected: bool
    label_count: int
    own_label: HumanLabel | None = None
    status: ReviewStatus
    suggestion: str | None = None
    paired_labels: list[HumanLabel] = Field(default_factory=list)
    model_exposed: bool = False
    peer_exposed: bool = False


class ReviewList(Contract):
    items: list[ReviewItem]
    human_labeling_enrolled: bool


class LabelResult(Contract):
    incident_id: UUID
    status: ReviewStatus
    label_count: int


class EnqueueResult(Contract):
    enqueued: int


class AgreementResult(Contract):
    n_pairs: int
    observed_agreement: float | None
    cohens_kappa: float | None
    krippendorff_alpha: float | None
    scope: str = "Paired independent human annotations in this tenant; nominal team labels only."


class GoldRecord(Contract):
    incident_id: UUID
    split: ReviewSplit
    provenance: Literal["human_gold", "human_on_synthetic"]
    label: HumanLabel
    text: str


class GoldExport(Contract):
    records: list[GoldRecord]
    next_after: UUID | None = None


class TenantSettings(Contract):
    version: int = Field(ge=1)
    timezone: str
    queue_mapping: dict[Team, str] = Field(default_factory=dict)
    misroute_minutes: float = Field(default=240, gt=0, le=100000)
    defer_minutes: float = Field(default=45, gt=0, le=100000)
    routing_config_status: Literal["pending_connector_and_recalibration"] = (
        "pending_connector_and_recalibration"
    )


class EvaluationStatus(Contract):
    bundle_id: str
    provenance: Literal["synthetic_seed", "uncalibrated_rules"]
    auto_route_enabled: bool
    human_gold_count: int
    frozen_test_count: int
    human_test_accuracy: float | None = None
    explanation: str


class BounceAnalyzeRequest(Contract):
    csv_text: str = Field(min_length=1, max_length=1000000)


class BounceReport(Contract):
    tickets: int
    transitions: int
    bounced_tickets: int
    bounce_rate: float | None
    median_reassignments: float | None
    top_transitions: dict[str, int]
    assumptions: str

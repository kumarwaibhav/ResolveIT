"""Request and response contracts for the REST API. Spans here are UTF-16 code units."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from resolveit_core.schemas import Channel, Decision, EpistemicState, Slot, SourceLayer

Locale = Literal["en", "hi", "hinglish"]
IncidentState = Literal["PENDING_CLARIFICATION", "ROUTED", "DEFERRED", "BOUNCED", "RESOLVED", "ERASED"]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IncidentCreate(_Model):
    text: str = Field(min_length=1, max_length=20_000)
    channel: Channel = Channel.WEB
    locale: Locale = "en"


class AnswerSubmit(_Model):
    answer: str | None = Field(default=None, max_length=200, description="null means the user pressed Skip.")


class EvidenceView(_Model):
    start: int
    end: int
    source: SourceLayer
    rule_id: str | None = None


class SlotView(_Model):
    slot: Slot
    state: EpistemicState
    value: str | None = None
    evidence: list[EvidenceView] = []


class OptionView(_Model):
    value: str
    label: str


class QuestionView(_Model):
    slot: Slot
    template_id: str
    text: str
    options: list[OptionView]
    skip_allowed: Literal[True] = True


class IncidentView(_Model):
    id: UUID
    state: IncidentState
    channel: Channel
    locale: Locale
    is_synthetic_tenant: bool = Field(description="True: show the permanent synthetic-data banner.")
    security_trigger: bool
    routed_team: str | None = None
    text: str | None = Field(
        default=None, description="Original text, for the evidence view. Null once the incident is erased."
    )
    frame: list[SlotView] = []
    decision: Decision | None = None
    question: QuestionView | None = None


class ErasureRequest(_Model):
    kind: Literal["EMAIL", "AADHAAR", "PAN", "IP_ADDR", "PHONE_IN", "EMP_ID", "USER_NAME"]
    identifier: str = Field(min_length=1, max_length=320)


class ErasureResult(_Model):
    incidents_erased: int


__all__ = [
    "AnswerSubmit",
    "ErasureRequest",
    "ErasureResult",
    "EvidenceView",
    "IncidentCreate",
    "IncidentState",
    "IncidentView",
    "Locale",
    "OptionView",
    "QuestionView",
    "SlotView",
]

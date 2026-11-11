"""Single source of truth for ResolveIT data contracts (Pydantic v2).

OpenAPI and the web TypeScript types are generated from these models.
Never redefine these shapes anywhere else.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Team(StrEnum):
    NETWORK = "Network"
    IDENTITY_ACCESS = "Identity_Access"
    EMAIL_COLLAB = "Email_Collab"
    HARDWARE_ENDPOINT = "Hardware_Endpoint"
    SOFTWARE_LICENSING = "Software_Licensing"
    DATABASE = "Database"
    CLOUD_INFRA = "Cloud_Infra"
    SECURITY = "Security"
    ERP_FINANCE = "ERP_Finance"
    HR_SYSTEMS = "HR_Systems"
    DEVOPS_CICD = "DevOps_CICD"
    FACILITIES_AV = "Facilities_AV"


TEAMS: tuple[Team, ...] = tuple(Team)
N_TEAMS: int = len(TEAMS)


class Slot(StrEnum):
    SERVICE = "service"
    COMPONENT = "component"
    SYMPTOM = "symptom"
    SCOPE = "scope"
    START_TIME = "start_time"
    FREQUENCY = "frequency"
    ENVIRONMENT = "environment"
    ERROR_CODE = "error_code"
    RECENT_CHANGE = "recent_change"
    USER_ROLE_LOCATION = "user_role_location"
    URGENCY = "urgency"


SLOTS: tuple[Slot, ...] = tuple(Slot)
UNKNOWN_ANSWER = "unknown"


class EpistemicState(StrEnum):
    PRESENT = "PRESENT"
    MISSING = "MISSING"
    AMBIGUOUS = "AMBIGUOUS"
    CONTRADICTED = "CONTRADICTED"


ASKABLE_STATES: frozenset[EpistemicState] = frozenset(
    {EpistemicState.MISSING, EpistemicState.AMBIGUOUS, EpistemicState.CONTRADICTED}
)


class SourceLayer(StrEnum):
    RULE = "rule"
    MODEL = "model"
    RULE_AND_MODEL = "rule+model"
    USER_ANSWER = "user_answer"
    AGENT_ASSERTED = "agent_asserted"
    HUMAN_CORRECTION = "human_correction"


class LabelSource(StrEnum):
    LLM_SILVER = "llm_silver"
    HUMAN_GOLD = "human_gold"
    HUMAN_CORRECTION = "human_correction"
    AUDIT_BLIND = "audit_blind"
    SYNTHETIC = "synthetic"


class Channel(StrEnum):
    WEB = "web"
    EMAIL = "email"
    CHAT = "chat"
    ITSM = "itsm"
    AGENT = "agent"


class Action(StrEnum):
    ROUTE = "ROUTE"
    ASK = "ASK"
    DEFER = "DEFER"


class DeferReason(StrEnum):
    NO_CONFORMING_TEAM = "no_conforming_team"
    RISK_ABOVE_DEFER_COST = "risk_above_defer_cost"
    SHADOW_MODE = "shadow_mode"
    SET_TOO_LARGE = "set_too_large"
    CRITICAL_CONTRADICTION = "critical_contradiction"
    UNMAPPED_QUEUE = "unmapped_queue"


class Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Span(Frozen):
    """Half-open span in RAW text, counted in Unicode code points."""

    start: int = Field(ge=0)
    end: int = Field(ge=0)

    @model_validator(mode="after")
    def _ordered(self) -> Span:
        if self.end < self.start:
            raise ValueError("span end before start")
        return self


class Utf16Span(Frozen):
    """Same span in UTF-16 code units, for browsers. Produced at the API edge only."""

    start: int = Field(ge=0)
    end: int = Field(ge=0)


class Evidence(Frozen):
    span: Span
    source: SourceLayer
    confidence: float = Field(ge=0.0, le=1.0)
    rule_id: str | None = None


class SlotValue(Frozen):
    slot: Slot
    state: EpistemicState
    value: str | None = None
    evidence: tuple[Evidence, ...] = ()

    @model_validator(mode="after")
    def _value_matches_state(self) -> SlotValue:
        if self.state is EpistemicState.MISSING and self.value is not None:
            raise ValueError("MISSING slot cannot carry a value")
        if self.state is EpistemicState.PRESENT and self.value is None:
            raise ValueError("PRESENT slot needs a value")
        return self


class IncidentFrame(Frozen):
    slots: tuple[SlotValue, ...]

    @model_validator(mode="after")
    def _all_slots_once(self) -> IncidentFrame:
        names = [s.slot for s in self.slots]
        if sorted(names) != sorted(SLOTS):
            raise ValueError("frame must contain each of the 11 slots exactly once")
        return self

    def get(self, slot: Slot) -> SlotValue:
        for s in self.slots:
            if s.slot is slot:
                return s
        raise KeyError(slot)

    def values(self) -> dict[Slot, str]:
        return {s.slot: s.value for s in self.slots if s.value is not None}

    @classmethod
    def empty(cls) -> IncidentFrame:
        return cls(slots=tuple(SlotValue(slot=s, state=EpistemicState.MISSING) for s in SLOTS))


class ConformalResult(Frozen):
    teams: tuple[Team, ...]
    alpha: float
    class_conditional: tuple[bool, ...] = Field(
        description="Per team in TEAMS order: True if that team has its own threshold "
        "(class-level coverage claimed), False if it uses the pooled threshold."
    )

    @property
    def is_empty(self) -> bool:
        return len(self.teams) == 0


class SlotAttribution(Frozen):
    slot: Slot
    value: str
    delta_p: float = Field(description="Drop in top-team probability when this slot is ablated.")


class QuestionRisk(Frozen):
    slot: Slot
    r_after: float
    r_ask: float


class Decision(Frozen):
    action: Action
    bundle_id: str
    probs: tuple[float, ...]
    conformal: ConformalResult
    team: Team | None = None
    ask_slot: Slot | None = None
    defer_reason: DeferReason | None = None
    r_route: float | None = Field(default=None, description="None encodes +infinity (route forbidden).")
    r_now: float
    c_def: float
    tau_hat: float | None = Field(default=None, description="None = shadow mode, auto-route off.")
    question_risks: tuple[QuestionRisk, ...] = ()
    no_ask_holdout: bool = False
    attributions: tuple[SlotAttribution, ...] = ()

    @model_validator(mode="after")
    def _action_fields(self) -> Decision:
        if self.action is Action.ROUTE and self.team is None:
            raise ValueError("ROUTE needs a team")
        if self.action is Action.ASK and self.ask_slot is None:
            raise ValueError("ASK needs a slot")
        if self.action is Action.DEFER and self.defer_reason is None:
            raise ValueError("DEFER needs a reason")
        return self


__all__ = [
    "ASKABLE_STATES",
    "N_TEAMS",
    "SLOTS",
    "TEAMS",
    "UNKNOWN_ANSWER",
    "Action",
    "Channel",
    "ConformalResult",
    "Decision",
    "DeferReason",
    "EpistemicState",
    "Evidence",
    "IncidentFrame",
    "LabelSource",
    "QuestionRisk",
    "Slot",
    "SlotAttribution",
    "SlotValue",
    "SourceLayer",
    "Span",
    "Team",
    "Utf16Span",
]

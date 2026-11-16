"""Persistent human review and tenant workspaces. No fabricated model evaluation numbers."""

from __future__ import annotations

import asyncio
import csv
import hashlib
import io
import json
from collections import Counter, defaultdict
from datetime import datetime
from itertools import pairwise
from statistics import median
from typing import Annotated, Any
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from resolveit_core.schemas import EpistemicState, Slot
from resolveit_core.schemas.workspaces import (
    AgreementResult,
    BounceAnalyzeRequest,
    BounceReport,
    EnqueueResult,
    EvaluationStatus,
    GoldExport,
    GoldRecord,
    HumanLabel,
    IdentityView,
    LabelResult,
    ReviewItem,
    ReviewList,
    ReviewSplit,
    ReviewStatus,
    TenantSettings,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from resolveit_api.auth import Principal, principal, require_role
from resolveit_api.review_privacy import record_exposure
from resolveit_api.routes.intake import load_view

router = APIRouter(prefix="/v1")
Reviewer = Annotated[Principal, Depends(require_role("admin", "reviewer"))]
Admin = Annotated[Principal, Depends(require_role("admin"))]
Reader = Annotated[Principal, Depends(require_role("admin", "reviewer", "viewer"))]
Authenticated = Annotated[Principal, Depends(principal)]


@router.get("/me", response_model=IdentityView)
async def identity(request: Request, who: Authenticated) -> IdentityView:
    async with request.app.state.db.tenant_tx(who.tenant_id) as session:
        synthetic = (
            await session.execute(text("SELECT is_synthetic FROM tenants WHERE id=:t"), {"t": who.tenant_id})
        ).scalar_one()
    return IdentityView(
        tenant_id=who.tenant_id,
        role=who.role,
        is_synthetic=synthetic,
        human_labeling_enrolled=who.human_subject_id is not None,
    )


def review_split(tenant_id: UUID, incident_id: UUID, audit: bool) -> ReviewSplit:
    if not audit:
        return "training"
    value = (
        int.from_bytes(hashlib.sha256(f"review-split:v1:{tenant_id}:{incident_id}".encode()).digest()[:8])
        % 10
    )
    return "scaling" if value < 2 else "calibration" if value < 6 else "frozen_test"


def validate_label(label: HumanLabel) -> None:
    if set(label.slots) != set(Slot):
        raise HTTPException(422, "label all 11 epistemic slots")
    for slot in label.slots.values():
        if slot.state == EpistemicState.PRESENT and not (slot.value and slot.value.strip()):
            raise HTTPException(422, "PRESENT slots require a value")
        if slot.state == EpistemicState.MISSING and slot.value is not None:
            raise HTTPException(422, "MISSING slots must have null values")


@router.post("/review/enqueue", response_model=EnqueueResult)
async def enqueue_legacy(request: Request, who: Reviewer) -> EnqueueResult:
    """Enroll pre-migration tickets as training corrections, never calibration/test data."""
    async with request.app.state.db.tenant_tx(who.tenant_id) as session:
        rows = (
            await session.execute(
                text(
                    "INSERT INTO review_items (tenant_id,incident_id,split) SELECT tenant_id,id,'training' "
                    "FROM incidents WHERE state<>'ERASED' ON CONFLICT DO NOTHING RETURNING incident_id"
                )
            )
        ).all()
    return EnqueueResult(enqueued=len(rows))


@router.get("/review", response_model=ReviewList)
async def list_review(
    request: Request,
    who: Reviewer,
    blind: bool = True,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    after: UUID | None = None,
) -> ReviewList:
    items: list[ReviewItem] = []
    async with request.app.state.db.tenant_tx(who.tenant_id) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT r.incident_id,r.split,r.status,i.audit_selected FROM review_items r JOIN "
                    "incidents i ON i.id=r.incident_id WHERE i.state<>'ERASED' AND (CAST(:after AS uuid) "
                    "IS NULL OR r.incident_id>CAST(:after AS uuid)) ORDER BY r.incident_id LIMIT :n"
                ),
                {"n": limit, "after": after},
            )
        ).all()
        for row in rows:
            view = await load_view(request.app.state, session, who.tenant_id, row[0])
            labels = (
                await session.execute(
                    text(
                        "SELECT annotator_id,label FROM review_labels WHERE incident_id=:i ORDER BY "
                        "created_at,annotator_id"
                    ),
                    {"i": row[0]},
                )
            ).all()
            own = next(
                (
                    HumanLabel.model_validate(annotation[1])
                    for annotation in labels
                    if annotation[0] == who.human_subject_id
                ),
                None,
            )
            paired = (
                [HumanLabel.model_validate(annotation[1]) for annotation in labels]
                if who.role == "admin" and row[2] == "needs_adjudication"
                else []
            )
            suggestion = (
                None
                if blind or not view.decision or not view.decision.recommended_team
                else view.decision.recommended_team.value
            )
            if suggestion is not None:
                await record_exposure(session, who.tenant_id, row[0], who.human_subject_id)
            if paired:
                await record_exposure(session, who.tenant_id, row[0], who.human_subject_id, "peer")
            exposures = set(
                (
                    await session.execute(
                        text("SELECT kind FROM review_exposures WHERE incident_id=:i AND subject_id=:s"),
                        {"i": row[0], "s": who.human_subject_id},
                    )
                )
                .scalars()
                .all()
            )
            items.append(
                ReviewItem(
                    incident_id=row[0],
                    text=view.text,
                    locale=view.locale,
                    is_synthetic=view.is_synthetic_tenant,
                    split=row[1],
                    audit_selected=row[3],
                    label_count=len(labels),
                    own_label=own,
                    status=row[2],
                    suggestion=suggestion,
                    paired_labels=paired,
                    model_exposed="model" in exposures,
                    peer_exposed="peer" in exposures,
                )
            )
    return ReviewList(items=items, human_labeling_enrolled=who.human_subject_id is not None)


async def _review_lock(session: AsyncSession, incident_id: UUID) -> Any:
    await session.execute(text("SELECT id FROM incidents WHERE id=:i FOR UPDATE"), {"i": incident_id})
    row = (
        await session.execute(
            text(
                "SELECT r.status,t.is_synthetic,r.split FROM review_items r JOIN tenants t ON "
                "t.id=r.tenant_id JOIN incidents i ON i.id=r.incident_id WHERE r.incident_id=:i AND "
                "i.state<>'ERASED' FOR UPDATE OF r"
            ),
            {"i": incident_id},
        )
    ).first()
    if row is None:
        raise HTTPException(404, "review item not found")
    return row


@router.post("/review/{incident_id}/labels", response_model=LabelResult)
async def submit_label(incident_id: UUID, body: HumanLabel, request: Request, who: Reviewer) -> LabelResult:
    if who.human_subject_id is None:
        raise HTTPException(403, "credential is not enrolled for human labeling")
    validate_label(body)
    async with request.app.state.db.tenant_tx(who.tenant_id) as session:
        item = await _review_lock(session, incident_id)
        labels = (
            await session.execute(
                text(
                    "SELECT annotator_id,label FROM review_labels WHERE incident_id=:i ORDER BY "
                    "created_at,annotator_id"
                ),
                {"i": incident_id},
            )
        ).all()
        own = next((annotation for annotation in labels if annotation[0] == who.human_subject_id), None)
        if own is not None:
            if HumanLabel.model_validate(own[1]) != body:
                raise HTTPException(409, "annotation is immutable; duplicate submission differs")
            return LabelResult(incident_id=incident_id, status=item[0], label_count=len(labels))
        if len(labels) >= 2 or item[0] in ("gold", "synthetic_labeled"):
            raise HTTPException(409, "two labels already collected; use adjudication")
        exposure = (
            await session.execute(
                text("SELECT 1 FROM review_exposures WHERE incident_id=:i AND subject_id=:s LIMIT 1"),
                {"i": incident_id, "s": who.human_subject_id},
            )
        ).first()
        if item[2] != "training" and exposure is not None:
            raise HTTPException(403, "audit labels require an annotator with no model or peer exposure")
        await session.execute(
            text(
                "INSERT INTO review_labels (tenant_id,incident_id,annotator_id,label) VALUES "
                "(:t,:i,:a,CAST(:l AS jsonb))"
            ),
            {"t": who.tenant_id, "i": incident_id, "a": who.human_subject_id, "l": body.model_dump_json()},
        )
        status: ReviewStatus = "single_label"
        agreed = bool(labels) and HumanLabel.model_validate(labels[0][1]) == body
        if labels:
            status = ("synthetic_labeled" if item[1] else "gold") if agreed else "needs_adjudication"
        await session.execute(
            text("UPDATE review_items SET status=:s,gold_label=CAST(:g AS jsonb) WHERE incident_id=:i"),
            {"s": status, "g": body.model_dump_json() if agreed else None, "i": incident_id},
        )
    return LabelResult(incident_id=incident_id, status=status, label_count=len(labels) + 1)


@router.post("/review/{incident_id}/adjudication", response_model=LabelResult)
async def adjudicate(incident_id: UUID, body: HumanLabel, request: Request, who: Admin) -> LabelResult:
    if who.human_subject_id is None:
        raise HTTPException(403, "credential is not enrolled for human adjudication")
    validate_label(body)
    async with request.app.state.db.tenant_tx(who.tenant_id) as session:
        item = await _review_lock(session, incident_id)
        subjects = (
            (
                await session.execute(
                    text("SELECT annotator_id FROM review_labels WHERE incident_id=:i"), {"i": incident_id}
                )
            )
            .scalars()
            .all()
        )
        if item[0] != "needs_adjudication" or len(subjects) != 2:
            raise HTTPException(409, "item does not need adjudication")
        if who.human_subject_id in subjects:
            raise HTTPException(403, "adjudicator must be independent of both annotators")
        exposed = (
            await session.execute(
                text(
                    "SELECT 1 FROM review_exposures WHERE incident_id=:i AND subject_id=:s AND kind='model'"
                ),
                {"i": incident_id, "s": who.human_subject_id},
            )
        ).first()
        if item[2] != "training" and exposed is not None:
            raise HTTPException(403, "audit adjudication requires a model-blind adjudicator")
        status: ReviewStatus = "synthetic_labeled" if item[1] else "gold"
        await session.execute(
            text(
                "UPDATE review_items SET status=:s,gold_label=CAST(:g AS jsonb),adjudicator=:a WHERE "
                "incident_id=:i"
            ),
            {"s": status, "g": body.model_dump_json(), "a": who.human_subject_id, "i": incident_id},
        )
    return LabelResult(incident_id=incident_id, status=status, label_count=2)


def agreement(pairs: list[tuple[str, str, str, str]]) -> AgreementResult:
    n = len(pairs)
    if not n:
        return AgreementResult(n_pairs=0, observed_agreement=None, cohens_kappa=None, krippendorff_alpha=None)
    observed = sum(a == b for _, _, a, b in pairs) / n
    counts = Counter(label for _, _, a, b in pairs for label in (a, b))
    total = 2 * n
    expected_disagreement = (total * total - sum(c * c for c in counts.values())) / (total * (total - 1))
    alpha = 1 - (1 - observed) / expected_disagreement if expected_disagreement else None
    kappa = None
    if len({(r1, r2) for r1, r2, _, _ in pairs}) == 1:
        first = Counter(a for _, _, a, _ in pairs)
        second = Counter(b for _, _, _, b in pairs)
        chance = sum(first[k] * second[k] for k in first.keys() | second.keys()) / (n * n)
        kappa = (observed - chance) / (1 - chance) if chance < 1 else None
    return AgreementResult(
        n_pairs=n,
        observed_agreement=observed,
        cohens_kappa=kappa,
        krippendorff_alpha=alpha,
        scope=(
            "Most recent 5000 paired units, nominal team labels. Cohen kappa requires "
            "one fixed annotator pair; undefined statistics remain null."
        ),
    )


@router.get("/review/agreement", response_model=AgreementResult)
async def get_agreement(request: Request, who: Reviewer) -> AgreementResult:
    async with request.app.state.db.tenant_tx(who.tenant_id) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT l.incident_id,l.annotator_id,l.label FROM review_labels l JOIN (SELECT "
                    "incident_id,max(created_at) AS latest FROM review_labels GROUP BY incident_id HAVING "
                    "count(*)=2 ORDER BY latest DESC LIMIT 5000) p ON p.incident_id=l.incident_id ORDER BY "
                    "l.incident_id,l.annotator_id"
                )
            )
        ).all()
    units: dict[UUID, list[Any]] = defaultdict(list)
    for row in rows:
        units[row[0]].append(row)
    return agreement(
        [
            (str(v[0][1]), str(v[1][1]), v[0][2]["team"], v[1][2]["team"])
            for v in units.values()
            if len(v) == 2
        ]
    )


@router.get("/review/export", response_model=GoldExport)
async def export_gold(
    request: Request,
    who: Admin,
    split: ReviewSplit = "training",
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    after: UUID | None = None,
) -> GoldExport:
    records: list[GoldRecord] = []
    async with request.app.state.db.tenant_tx(who.tenant_id) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT incident_id,gold_label,status FROM review_items WHERE split=:s AND status IN "
                    "('gold','synthetic_labeled') AND (CAST(:after AS uuid) IS NULL OR "
                    "incident_id>CAST(:after AS uuid)) ORDER BY incident_id LIMIT :n"
                ),
                {"s": split, "after": after, "n": limit},
            )
        ).all()
        for row in rows:
            view = await load_view(request.app.state, session, who.tenant_id, row[0])
            if view.text is not None:
                records.append(
                    GoldRecord(
                        incident_id=row[0],
                        split=split,
                        provenance="human_on_synthetic" if row[2] == "synthetic_labeled" else "human_gold",
                        label=HumanLabel.model_validate(row[1]),
                        text=view.text,
                    )
                )
    return GoldExport(records=records, next_after=rows[-1][0] if len(rows) == limit else None)


async def _settings(session: AsyncSession, tenant_id: UUID) -> TenantSettings:
    row = (
        await session.execute(
            text(
                "SELECT t.timezone,s.version,s.queue_mapping,s.misroute_minutes,s.defer_minutes FROM "
                "tenants t LEFT JOIN tenant_settings s ON s.tenant_id=t.id WHERE t.id=:t"
            ),
            {"t": tenant_id},
        )
    ).one()
    return TenantSettings(
        timezone=row[0],
        version=row[1] or 1,
        queue_mapping=row[2] or {},
        misroute_minutes=row[3] or 240,
        defer_minutes=row[4] or 45,
    )


@router.get("/settings", response_model=TenantSettings)
async def get_settings(request: Request, who: Admin) -> TenantSettings:
    async with request.app.state.db.tenant_tx(who.tenant_id) as session:
        return await _settings(session, who.tenant_id)


@router.put("/settings", response_model=TenantSettings)
async def put_settings(body: TenantSettings, request: Request, who: Admin) -> TenantSettings:
    try:
        ZoneInfo(body.timezone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise HTTPException(422, "unknown IANA timezone") from exc
    if any(not v.strip() or len(v) > 128 for v in body.queue_mapping.values()):
        raise HTTPException(422, "queue mapping values must contain 1..128 characters")
    async with request.app.state.db.tenant_tx(who.tenant_id) as session:
        await session.execute(text("SELECT id FROM tenants WHERE id=:t FOR UPDATE"), {"t": who.tenant_id})
        current = await _settings(session, who.tenant_id)
        if body.version != current.version:
            raise HTTPException(409, "settings changed; reload current version")
        await session.execute(
            text(
                "INSERT INTO tenant_settings "
                "(tenant_id,version,queue_mapping,misroute_minutes,defer_minutes) VALUES (:t,:v,CAST(:q AS "
                "jsonb),:m,:d) ON CONFLICT (tenant_id) DO UPDATE SET "
                "version=EXCLUDED.version,queue_mapping=EXCLUDED.queue_mapping,misroute_minutes=EXCLUDED.misroute_minutes,defer_minutes=EXCLUDED.defer_minutes"
            ),
            {
                "t": who.tenant_id,
                "v": body.version + 1,
                "q": json.dumps(body.model_dump(mode="json")["queue_mapping"]),
                "m": body.misroute_minutes,
                "d": body.defer_minutes,
            },
        )
        await session.execute(
            text("UPDATE tenants SET timezone=:z WHERE id=:t"), {"z": body.timezone, "t": who.tenant_id}
        )
        return await _settings(session, who.tenant_id)


@router.get("/evaluation", response_model=EvaluationStatus)
async def evaluation(request: Request, who: Reader) -> EvaluationStatus:
    async with request.app.state.db.tenant_tx(who.tenant_id) as session:
        synthetic = (
            await session.execute(text("SELECT is_synthetic FROM tenants WHERE id=:t"), {"t": who.tenant_id})
        ).scalar_one()
        counts = (
            await session.execute(
                text(
                    "SELECT count(*) FILTER (WHERE status='gold'),count(*) FILTER (WHERE status='gold' AND "
                    "split='frozen_test') FROM review_items"
                )
            )
        ).one()
    bundle = request.app.state.bundles[synthetic]
    return EvaluationStatus(
        bundle_id=bundle.bundle_id,
        provenance="synthetic_seed" if synthetic else "uncalibrated_rules",
        auto_route_enabled=synthetic
        and (bundle.tau_hat is not None or any(t is not None for t in (bundle.queue_tau_hat or {}).values())),
        human_gold_count=counts[0],
        frozen_test_count=counts[1],
        explanation=(
            "Synthetic generator metrics cannot establish production quality. Human frozen-test "
            "evaluation has not been executed; accuracy remains unavailable."
        ),
    )


def analyze_csv(body: str) -> BounceReport:
    reader = csv.DictReader(io.StringIO(body))
    required = {"ticket_id", "assignment_group", "timestamp"}
    try:
        headers = reader.fieldnames
        csv_rows = list(reader)
    except csv.Error as exc:
        raise HTTPException(422, "malformed or oversized CSV field") from exc
    if not headers or not required.issubset(headers):
        raise HTTPException(422, "CSV requires ticket_id, assignment_group, timestamp columns")
    tickets: dict[str, list[tuple[datetime, str]]] = defaultdict(list)
    for count, row in enumerate(csv_rows, 1):
        if count > 20000:
            raise HTTPException(422, "CSV exceeds 20000 rows")
        try:
            ticket, group = row["ticket_id"].strip(), row["assignment_group"].strip()
            at = datetime.fromisoformat(row["timestamp"].strip().replace("Z", "+00:00"))
        except (ValueError, AttributeError) as exc:
            raise HTTPException(422, f"invalid CSV row {count + 1}") from exc
        if not ticket or not group or at.tzinfo is None:
            raise HTTPException(
                422, f"row {count + 1} requires nonempty ticket/group and timezone-aware ISO timestamp"
            )
        tickets[ticket].append((at, group))
    transitions: Counter[str] = Counter()
    changes = []
    for rows in tickets.values():
        ordered = sorted(rows)
        if any(a[0] == b[0] and a[1] != b[1] for a, b in pairwise(ordered)):
            raise HTTPException(422, "conflicting assignments share a timestamp; event order is unknown")
        groups = [group for _, group in ordered]
        count = 0
        for before, after in pairwise(groups):
            if before != after:
                count += 1
                transitions[f"{before} -> {after}"] += 1
        changes.append(count)
    bounced = sum(n > 0 for n in changes)
    return BounceReport(
        tickets=len(tickets),
        transitions=sum(changes),
        bounced_tickets=bounced,
        bounce_rate=bounced / len(tickets) if tickets else None,
        median_reassignments=float(median(changes)) if changes else None,
        top_transitions=dict(transitions.most_common(20)),
        assumptions=(
            "Input is complete assignment history; first assignment is baseline. "
            "Adjacent repeats are ignored; any later group change is a bounce. "
            "CSV values are analyzed in memory and not retained."
        ),
    )


@router.post("/bounce/analyze", response_model=BounceReport)
async def bounce(body: BounceAnalyzeRequest, who: Reviewer) -> BounceReport:
    return await asyncio.to_thread(analyze_csv, body.csv_text)

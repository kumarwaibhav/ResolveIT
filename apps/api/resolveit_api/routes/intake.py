"""Persist-first intake, single optional clarification, and erasure.

Order of operations on submit:
  1. transaction 1 commits the incident (PENDING_CLARIFICATION, SLA clock,
     encrypted text, blind index). The ticket now exists whatever happens next.
  2. transaction 2 evaluates and stores frame + decision, and either finalises
     or records the one optional question.
Ticket text is never logged.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from resolveit_core.frame.merger import apply_answer
from resolveit_core.gate.bayes_evsi import ChannelCosts
from resolveit_core.masking.pii_shield import PiiType, canonical_identifier, mask_pii
from resolveit_core.offsets.offset_map import Utf16Index, normalize_nfkc
from resolveit_core.schemas import (
    UNKNOWN_ANSWER,
    Action,
    Channel,
    Decision,
    IncidentFrame,
    Slot,
    SourceLayer,
)
from resolveit_core.schemas.api import (
    AnswerSubmit,
    ErasureRequest,
    ErasureResult,
    EvidenceView,
    IncidentCreate,
    IncidentView,
    QuestionView,
    SlotView,
)
from resolveit_enterprise.privacy.crypto_shredder import SealedText, blind_index, seal, unseal
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from resolveit_api.auth import Principal, require_role
from resolveit_api.bundles import Bundle
from resolveit_api.pipeline import channel_costs, evaluate, finalize

router = APIRouter(prefix="/v1")
_rng = secrets.SystemRandom()

Writer = Annotated[Principal, Depends(require_role("admin", "reviewer", "agent"))]
Reader = Annotated[Principal, Depends(require_role("admin", "reviewer", "viewer", "agent"))]
Admin = Annotated[Principal, Depends(require_role("admin"))]


def _frame_view(frame: IncidentFrame, raw_text: str | None) -> list[SlotView]:
    index = Utf16Index(raw_text) if raw_text is not None else None
    out: list[SlotView] = []
    for s in frame.slots:
        evidence: list[EvidenceView] = []
        if index is not None:
            for e in s.evidence:
                a, b = index.span_to_utf16(e.span.start, e.span.end)
                evidence.append(EvidenceView(start=a, end=b, source=e.source, rule_id=e.rule_id))
        out.append(SlotView(slot=s.slot, state=s.state, value=s.value, evidence=evidence))
    return out


async def _tenant(session: AsyncSession, tenant_id: UUID) -> tuple[str, bool]:
    row = (
        await session.execute(
            text("SELECT timezone, is_synthetic FROM tenants WHERE id = :id"), {"id": tenant_id}
        )
    ).one()
    return row[0], row[1]


async def _stats(session: AsyncSession, tenant_id: UUID, channel: Channel) -> ChannelCosts:
    row = (
        await session.execute(
            text("SELECT asks, answers FROM channel_stats WHERE tenant_id = :t AND channel = :c"),
            {"t": tenant_id, "c": channel.value},
        )
    ).first()
    return channel_costs(channel, row[0] if row else 0, row[1] if row else 0)


async def _bump(session: AsyncSession, tenant_id: UUID, channel: str, asks: int, answers: int) -> None:
    await session.execute(
        text(
            "INSERT INTO channel_stats (tenant_id, channel, asks, answers) VALUES (:t, :c, :a, :n) "
            "ON CONFLICT (tenant_id, channel) DO UPDATE SET asks = channel_stats.asks + :a, "
            "answers = channel_stats.answers + :n"
        ),
        {"t": tenant_id, "c": channel, "a": asks, "n": answers},
    )


async def _store_decision(
    session: AsyncSession, tenant_id: UUID, incident_id: UUID, stage: str, decision: Decision
) -> None:
    await session.execute(
        text(
            "INSERT INTO decisions (id, incident_id, tenant_id, stage, bundle_id, payload) "
            "VALUES (:id, :i, :t, :s, :b, CAST(:p AS jsonb))"
        ),
        {
            "id": uuid4(),
            "i": incident_id,
            "t": tenant_id,
            "s": stage,
            "b": decision.bundle_id,
            "p": decision.model_dump_json(),
        },
    )


async def _store_frame(
    session: AsyncSession, tenant_id: UUID, incident_id: UUID, version: int, frame: IncidentFrame
) -> None:
    await session.execute(
        text(
            "INSERT INTO frames (incident_id, tenant_id, version, slots) "
            "VALUES (:i, :t, :v, CAST(:s AS jsonb))"
        ),
        {"i": incident_id, "t": tenant_id, "v": version, "s": frame.model_dump_json()},
    )


async def _close(session: AsyncSession, incident_id: UUID, decision: Decision) -> str:
    state = "ROUTED" if decision.action is Action.ROUTE else "DEFERRED"
    await session.execute(
        text(
            "UPDATE incidents SET state = :s, routed_team = :team, clarify_deadline = NULL, "
            "version = version + 1 WHERE id = :i AND state = 'PENDING_CLARIFICATION'"
        ),
        {"s": state, "team": decision.team.value if decision.team else None, "i": incident_id},
    )
    return state


@router.post("/incidents", response_model=IncidentView, status_code=status.HTTP_201_CREATED)
async def create_incident(body: IncidentCreate, request: Request, who: Writer) -> IncidentView:
    app = request.app.state
    now = datetime.now(UTC)
    incident_id = uuid4()
    audit = _rng.random() < app.settings.audit_rate  # drawn before any decision exists
    holdout = _rng.random() < app.settings.holdout_rate
    minutes = (
        app.settings.web_clarify_minutes
        if body.channel in (Channel.WEB, Channel.CHAT, Channel.AGENT)
        else app.settings.async_clarify_minutes
    )
    normalised, _ = normalize_nfkc(body.text)
    mask = mask_pii(normalised)
    sealed = seal(app.wrapper, who.tenant_id, incident_id, body.text)

    async with app.db.tenant_tx(who.tenant_id) as session:
        timezone, is_synthetic = await _tenant(session, who.tenant_id)
        await session.execute(
            text(
                "INSERT INTO incidents (id, tenant_id, state, channel, locale, sla_started_at, "
                "clarify_deadline, audit_selected, no_ask_holdout) "
                "VALUES (:id, :t, 'PENDING_CLARIFICATION', :c, :l, :now, :dl, :a, :h)"
            ),
            {
                "id": incident_id,
                "t": who.tenant_id,
                "c": body.channel.value,
                "l": body.locale,
                "now": now,
                "dl": now + timedelta(minutes=minutes),
                "a": audit,
                "h": holdout,
            },
        )
        await session.execute(
            text("INSERT INTO incident_keys (incident_id, tenant_id, wrapped_key) VALUES (:i, :t, :k)"),
            {"i": incident_id, "t": who.tenant_id, "k": sealed.wrapped_key},
        )
        await session.execute(
            text(
                "INSERT INTO incident_text (incident_id, tenant_id, masked_text, raw_ciphertext, raw_nonce) "
                "VALUES (:i, :t, :m, :c, :n)"
            ),
            {
                "i": incident_id,
                "t": who.tenant_id,
                "m": mask.masked_text,
                "c": sealed.ciphertext,
                "n": sealed.nonce,
            },
        )
        for ent in {(e.kind.name, e.identifier) for e in mask.entities}:
            await session.execute(
                text(
                    "INSERT INTO subject_index (tenant_id, identifier_hmac, incident_id) VALUES (:t, :h, :i) "
                    "ON CONFLICT DO NOTHING"
                ),
                {
                    "t": who.tenant_id,
                    "h": blind_index(app.wrapper, who.tenant_id, ent[0], ent[1]),
                    "i": incident_id,
                },
            )

    bundle: Bundle = app.bundles[is_synthetic]
    question: QuestionView | None = None
    async with app.db.tenant_tx(who.tenant_id) as session:
        costs = await _stats(session, who.tenant_id, body.channel)
        ev = evaluate(body.text, now, timezone, bundle, costs, holdout)
        await _store_frame(session, who.tenant_id, incident_id, 1, ev.frame)
        await _store_decision(session, who.tenant_id, incident_id, "initial", ev.decision)
        await session.execute(
            text("UPDATE incidents SET security_trigger = :s WHERE id = :i"),
            {"s": ev.rules.security_trigger, "i": incident_id},
        )
        state = "PENDING_CLARIFICATION"
        if ev.decision.action is Action.ASK and ev.decision.ask_slot is not None:
            slot = ev.decision.ask_slot
            question = app.templates.question(slot, body.locale, bundle.theta.values[slot])
            await session.execute(
                text(
                    "INSERT INTO questions (incident_id, tenant_id, slot, template_id, channel) "
                    "VALUES (:i, :t, :s, :tpl, :c)"
                ),
                {
                    "i": incident_id,
                    "t": who.tenant_id,
                    "s": slot.value,
                    "tpl": question.template_id,
                    "c": body.channel.value,
                },
            )
            await _bump(session, who.tenant_id, body.channel.value, 1, 0)
        else:
            state = await _close(session, incident_id, ev.decision)

    return IncidentView(
        id=incident_id,
        state=state,
        channel=body.channel,
        locale=body.locale,
        is_synthetic_tenant=is_synthetic,
        security_trigger=ev.rules.security_trigger,
        routed_team=ev.decision.team.value if ev.decision.team and state == "ROUTED" else None,
        frame=_frame_view(ev.frame, body.text),
        decision=ev.decision,
        question=question,
    )


async def _load_view(app: object, session: AsyncSession, tenant_id: UUID, incident_id: UUID) -> IncidentView:
    row = (
        await session.execute(
            text(
                "SELECT i.state, i.channel, i.locale, i.security_trigger, i.routed_team, t.is_synthetic, "
                "x.raw_ciphertext, x.raw_nonce, k.wrapped_key "
                "FROM incidents i JOIN tenants t ON t.id = i.tenant_id "
                "LEFT JOIN incident_text x ON x.incident_id = i.id "
                "LEFT JOIN incident_keys k ON k.incident_id = i.id WHERE i.id = :i"
            ),
            {"i": incident_id},
        )
    ).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "incident not found")
    raw: str | None = None
    if row[6] is not None and row[8] is not None:
        raw = unseal(app.wrapper, tenant_id, incident_id, SealedText(row[8], row[7], row[6]))  # type: ignore[attr-defined]
    frame_row = (
        await session.execute(
            text("SELECT slots FROM frames WHERE incident_id = :i ORDER BY version DESC LIMIT 1"),
            {"i": incident_id},
        )
    ).first()
    dec_row = (
        await session.execute(
            text(
                "SELECT payload FROM decisions WHERE incident_id = :i ORDER BY created_at DESC, stage LIMIT 1"
            ),
            {"i": incident_id},
        )
    ).first()
    q_row = (
        await session.execute(
            text("SELECT slot FROM questions WHERE incident_id = :i AND outcome = 'pending'"),
            {"i": incident_id},
        )
    ).first()
    erased = row[0] == "ERASED"
    frame = IncidentFrame.model_validate(frame_row[0]) if frame_row and not erased else None
    decision = Decision.model_validate(dec_row[0]) if dec_row and not erased else None
    question = None
    if q_row and row[0] == "PENDING_CLARIFICATION":
        bundle: Bundle = app.bundles[row[5]]  # type: ignore[attr-defined]
        question = app.templates.question(Slot(q_row[0]), row[2], bundle.theta.values[Slot(q_row[0])])  # type: ignore[attr-defined]
    return IncidentView(
        id=incident_id,
        state=row[0],
        channel=Channel(row[1]),
        locale=row[2],
        is_synthetic_tenant=row[5],
        security_trigger=row[3],
        routed_team=row[4],
        frame=_frame_view(frame, raw) if frame else [],
        decision=decision,
        question=question,
    )


@router.get("/incidents/{incident_id}", response_model=IncidentView)
async def get_incident(incident_id: UUID, request: Request, who: Reader) -> IncidentView:
    async with request.app.state.db.tenant_tx(who.tenant_id) as session:
        return await _load_view(request.app.state, session, who.tenant_id, incident_id)


@router.post("/incidents/{incident_id}/answer", response_model=IncidentView)
async def answer_question(
    incident_id: UUID, body: AnswerSubmit, request: Request, who: Writer
) -> IncidentView:
    app = request.app.state
    async with app.db.tenant_tx(who.tenant_id) as session:
        inc = (
            await session.execute(
                text(
                    "SELECT i.state, i.channel, i.security_trigger, t.is_synthetic FROM incidents i "
                    "JOIN tenants t ON t.id = i.tenant_id WHERE i.id = :i FOR UPDATE OF i"
                ),
                {"i": incident_id},
            )
        ).first()
        if inc is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "incident not found")
        q = (
            await session.execute(
                text("SELECT slot FROM questions WHERE incident_id = :i AND outcome = 'pending' FOR UPDATE"),
                {"i": incident_id},
            )
        ).first()
        if inc[0] != "PENDING_CLARIFICATION" or q is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "no open question for this incident")
        slot, channel = Slot(q[0]), Channel(inc[1])
        bundle: Bundle = app.bundles[inc[3]]
        initial = Decision.model_validate(
            (
                await session.execute(
                    text("SELECT payload FROM decisions WHERE incident_id = :i AND stage = 'initial'"),
                    {"i": incident_id},
                )
            ).scalar_one()
        )
        frame = IncidentFrame.model_validate(
            (
                await session.execute(
                    text("SELECT slots FROM frames WHERE incident_id = :i AND version = 1"),
                    {"i": incident_id},
                )
            ).scalar_one()
        )
        answer = body.answer
        if answer is not None and answer not in bundle.theta.values[slot]:
            answer = UNKNOWN_ANSWER
        costs = await _stats(session, who.tenant_id, channel)
        final = finalize(initial, frame, slot, answer, bundle, costs, inc[2])
        source = SourceLayer.AGENT_ASSERTED if who.role == "agent" else SourceLayer.USER_ANSWER
        if answer is not None and answer != UNKNOWN_ANSWER:
            await _store_frame(
                session, who.tenant_id, incident_id, 2, apply_answer(frame, slot, answer, source)
            )
        await session.execute(
            text(
                "UPDATE questions SET outcome = :o, answer = :a, answer_source = :src, closed_at = now() "
                "WHERE incident_id = :i"
            ),
            {
                "o": "skipped" if answer is None else "answered",
                "a": answer,
                "src": None if answer is None else source.value,
                "i": incident_id,
            },
        )
        if answer is not None:
            await _bump(session, who.tenant_id, channel.value, 0, 1)
        await _store_decision(session, who.tenant_id, incident_id, "final", final)
        await _close(session, incident_id, final)
        return await _load_view(app, session, who.tenant_id, incident_id)


@router.post("/privacy/erasure", response_model=ErasureResult)
async def erase_subject(body: ErasureRequest, request: Request, who: Admin) -> ErasureResult:
    """Crypto-shred every incident linked to one identifier. Irreversible."""
    app = request.app.state
    canonical = canonical_identifier(PiiType[body.kind], body.identifier)
    digest = blind_index(app.wrapper, who.tenant_id, body.kind, canonical)
    async with app.db.tenant_tx(who.tenant_id) as session:
        ids = [
            r[0]
            for r in (
                await session.execute(
                    text("SELECT incident_id FROM subject_index WHERE identifier_hmac = :h"), {"h": digest}
                )
            ).all()
        ]
        for incident_id in ids:
            params = {"i": incident_id}
            await session.execute(text("DELETE FROM incident_keys WHERE incident_id = :i"), params)
            await session.execute(
                text(
                    "UPDATE incident_text SET masked_text = NULL, raw_ciphertext = NULL, raw_nonce = NULL, "
                    "tombstoned_at = now() WHERE incident_id = :i"
                ),
                params,
            )
            await session.execute(text("DELETE FROM subject_index WHERE incident_id = :i"), params)
            await session.execute(text("DELETE FROM frames WHERE incident_id = :i"), params)
            await session.execute(text("DELETE FROM questions WHERE incident_id = :i"), params)
            await session.execute(
                text("UPDATE decisions SET payload = '{}'::jsonb WHERE incident_id = :i"), params
            )
            await session.execute(
                text(
                    "UPDATE incidents SET state = 'ERASED', clarify_deadline = NULL, version = version + 1 "
                    "WHERE id = :i"
                ),
                params,
            )
        await session.execute(
            text(
                "INSERT INTO erasure_requests (id, tenant_id, identifier_hmac, incidents_erased) "
                "VALUES (:id, :t, :h, :n)"
            ),
            {"id": uuid4(), "t": who.tenant_id, "h": digest, "n": len(ids)},
        )
    return ErasureResult(incidents_erased=len(ids))

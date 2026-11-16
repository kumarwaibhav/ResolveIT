from __future__ import annotations

from dataclasses import replace
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import HTTPException
from resolveit_core.schemas import Slot

from resolveit_api.routes.workspaces import agreement, analyze_csv

from .conftest import auth


def label(team: str = "Network") -> dict:
    return {"team": team, "slots": {slot.value: {"state": "MISSING", "value": None} for slot in Slot}}


async def audit_item(client: httpx.AsyncClient) -> str:
    app = client.app.state  # type: ignore[attr-defined]
    original = app.settings
    app.settings = replace(original, audit_rate=1.0)
    try:
        response = await client.post(
            "/v1/incidents", json={"text": f"wifi issue [{uuid4()}]"}, headers=auth("a_admin")
        )
        assert response.status_code == 201
        return str(response.json()["id"])
    finally:
        app.settings = original


async def test_distinct_human_labels_and_immutable_split(client: httpx.AsyncClient) -> None:
    incident = await audit_item(client)
    first = await client.post(f"/v1/review/{incident}/labels", json=label(), headers=auth("a_review1"))
    assert first.status_code == 200 and first.json()["status"] == "single_label"
    alias = await client.post(f"/v1/review/{incident}/labels", json=label(), headers=auth("a_review1_alias"))
    assert alias.json()["label_count"] == 1
    second = await client.post(f"/v1/review/{incident}/labels", json=label(), headers=auth("a_review2"))
    assert (
        second.status_code == 200 and second.json()["status"] == "gold" and second.json()["label_count"] == 2
    )
    changed = await client.post(
        f"/v1/review/{incident}/labels", json=label("Database"), headers=auth("a_review1")
    )
    assert changed.status_code == 409
    foreign = await client.post(f"/v1/review/{incident}/labels", json=label(), headers=auth("b_admin"))
    assert foreign.status_code == 403  # unenrolled credential denied before item lookup


async def test_model_exposure_blocks_audit_annotation(client: httpx.AsyncClient) -> None:
    incident = await audit_item(client)
    after = UUID(int=UUID(incident).int - 1)
    response = await client.get(f"/v1/review?blind=false&limit=1&after={after}", headers=auth("a_review1"))
    assert response.status_code == 200
    items = {item["incident_id"]: item for item in response.json()["items"]}
    assert items[incident]["model_exposed"] is True
    blocked = await client.post(f"/v1/review/{incident}/labels", json=label(), headers=auth("a_review1"))
    assert blocked.status_code == 403
    second = await audit_item(client)
    assert (await client.get(f"/v1/incidents/{second}", headers=auth("a_review2"))).status_code == 200
    assert (
        await client.post(f"/v1/review/{second}/labels", json=label(), headers=auth("a_review2"))
    ).status_code == 403


async def test_adjudicator_must_be_third_model_blind_human(client: httpx.AsyncClient) -> None:
    incident = await audit_item(client)
    assert (
        await client.post(f"/v1/review/{incident}/labels", json=label(), headers=auth("a_review1"))
    ).status_code == 200
    assert (
        await client.post(f"/v1/review/{incident}/labels", json=label("Database"), headers=auth("a_review2"))
    ).json()["status"] == "needs_adjudication"
    response = await client.post(f"/v1/review/{incident}/adjudication", json=label(), headers=auth("a_judge"))
    assert response.status_code == 200 and response.json()["status"] == "gold"


async def test_settings_are_versioned_and_private(client: httpx.AsyncClient) -> None:
    current = (await client.get("/v1/settings", headers=auth("a_admin"))).json()
    current["queue_mapping"] = {"Network": "IT-NETWORK"}
    saved = await client.put("/v1/settings", headers=auth("a_admin"), json=current)
    assert saved.status_code == 200 and saved.json()["version"] == current["version"] + 1
    assert saved.json()["routing_config_status"] == "pending_connector_and_recalibration"
    assert (await client.put("/v1/settings", headers=auth("a_admin"), json=current)).status_code == 409
    assert (await client.get("/v1/settings", headers=auth("a_review1"))).status_code == 403
    other = (await client.get("/v1/settings", headers=auth("b_admin"))).json()
    assert other["queue_mapping"] == {}


async def test_identity_and_evaluation_do_not_invent_metrics(client: httpx.AsyncClient) -> None:
    identity = (await client.get("/v1/me", headers=auth("demo_agent"))).json()
    assert identity["is_synthetic"] is True and identity["role"] == "agent"
    assert set(identity) == {"tenant_id", "role", "is_synthetic", "human_labeling_enrolled"}
    status = (await client.get("/v1/evaluation", headers=auth("a_admin"))).json()
    assert status["human_test_accuracy"] is None and status["auto_route_enabled"] is False
    assert (await client.get("/v1/me")).status_code == 401


def test_agreement_statistics_undefined_and_perfect() -> None:
    assert agreement([]).cohens_kappa is None
    assert agreement([("one", "two", "Network", "Network")]).cohens_kappa is None
    perfect = agreement([("one", "two", "Network", "Network"), ("one", "two", "Database", "Database")])
    assert perfect.cohens_kappa == 1 and perfect.krippendorff_alpha == 1
    mixed = agreement([("one", "two", "Network", "Network"), ("one", "three", "Database", "Database")])
    assert mixed.cohens_kappa is None and mixed.krippendorff_alpha == 1


def test_bounce_csv_computes_from_ordered_history() -> None:
    report = analyze_csv(
        "ticket_id,assignment_group,timestamp\nA,Network,2026-01-01T00:00:00Z\nA,Database,2026-01-01T01:00:00Z\nB,Network,2026-01-01T00:00:00Z\n"
    )
    assert report.tickets == 2 and report.bounced_tickets == 1 and report.bounce_rate == 0.5
    with pytest.raises(HTTPException):
        analyze_csv("ticket_id,assignment_group,timestamp\nA,Network,not-a-timestamp\n")

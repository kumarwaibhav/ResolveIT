"""One-browser sequential live six-workspace and WCAG AA checks."""

from __future__ import annotations

import re
from pathlib import Path

import httpx
from playwright.sync_api import Page, expect, sync_playwright

BASE = "http://127.0.0.1:3000"
SLOTS = (
    "service",
    "component",
    "symptom",
    "scope",
    "start_time",
    "frequency",
    "environment",
    "error_code",
    "recent_change",
    "user_role_location",
    "urgency",
)


def login(page: Page, key: str) -> None:
    page.goto(BASE + "/login")
    page.get_by_label("Individual API credential").fill(key)
    page.get_by_role("button", name="Sign in", exact=True).click()
    expect(page.get_by_role("heading", name="Make judgment visible.")).to_be_visible()


def run(env: dict[str, str], keys: list[str], incident: str, out: Path) -> dict[str, object]:
    axe_script = (Path(__file__).resolve().parents[1] / "node_modules/axe-core/axe.min.js").read_text(
        encoding="utf-8"
    )
    pages = ("/", "/review", "/bounce", "/evaluation", "/mcp", "/settings")
    checks = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True, args=["--renderer-process-limit=1", "--disable-dev-shm-usage"]
        )
        context = browser.new_context()
        page = context.new_page()
        for width, mode in ((1440, "light"), (320, "dark")):
            page.set_viewport_size({"width": width, "height": 1000})
            page.emulate_media(color_scheme=mode, reduced_motion="reduce")
            for path in pages:
                page.goto(BASE + path, wait_until="networkidle")
                expect(page.locator("main h1")).to_be_visible()
                page.add_script_tag(content=axe_script)
                result = page.evaluate(
                    "async () => await axe.run(document,{runOnly:['wcag2a','wcag2aa','wcag21aa']})"
                )
                bad = [
                    {
                        "id": violation["id"],
                        "impact": violation["impact"],
                        "targets": [node["target"] for node in violation["nodes"]],
                    }
                    for violation in result["violations"]
                ]
                if bad:
                    (out / "axe-failures.json").write_text(
                        __import__("json").dumps({"path": path, "width": width, "violations": bad}, indent=2)
                    )
                assert not bad, f"axe violations {path} {width}: {bad}"
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), (
                    f"Horizontal overflow: {path} {width}"
                )
                page.screenshot(path=str(out / f"{width}-{path.strip('/') or 'intake'}.png"), full_page=True)
                checks.append({"path": path, "width": width, "scheme": mode, "violations": 0})
        page.set_viewport_size({"width": 1440, "height": 1000})
        page.goto(BASE)
        page.get_by_label("What is going wrong?").fill(
            "database is down for the whole floor [synthetic UI intake]"
        )
        page.get_by_role("button", name="Send ticket").click()
        expect(page.locator("[data-result-heading]")).to_have_text("Sent to Database")
        page.goto(BASE + "/bounce")
        page.get_by_role("button", name="Load synthetic example").click()
        page.get_by_role("button", name="Analyze with tenant API").click()
        expect(page.get_by_role("heading", name="Connected analysis result")).to_be_visible()
        page.goto(BASE + "/mcp")
        page.get_by_role("button", name="Inspect initialize", exact=True).click()
        expect(page.get_by_text("Standard response (HTTP 200)", exact=True)).to_be_visible()
        page.get_by_role("button", name="Inspect tools/list", exact=True).click()
        expect(page.get_by_text("Standard response (HTTP 200)", exact=True)).to_be_visible()
        page.get_by_role("button", name=re.compile("Risk gate")).click()
        expect(page.get_by_role("heading", name="Know when to stop")).to_be_visible()
        page.get_by_label("The user's report, verbatim").fill("database down [synthetic MCP browser]")
        page.get_by_role("button", name="Call submit_incident").click()
        expect(page.get_by_text("Round trip 1: complete", exact=False)).to_be_visible()
        page.goto(BASE + "/settings")
        page.get_by_label("Tenant timezone").fill("Asia/Kolkata")
        page.get_by_role("button", name="Save tenant settings", exact=True).click()
        expect(page.get_by_text("Tenant configuration saved at version", exact=False)).to_be_visible()
        canary = "stage-c-erasure@example.invalid"
        with httpx.Client(
            base_url=env["RESOLVEIT_API_URL"], headers={"Authorization": f"Bearer {env['RESOLVEIT_API_KEY']}"}
        ) as client:
            erased = client.post("/v1/incidents", json={"text": f"database down contact {canary}"}).json()[
                "id"
            ]
            page.get_by_label("Exact subject identifier").fill(canary)
            page.get_by_label("I understand this permanently removes matching live incidents.").check()
            page.get_by_role("button", name="Erase matching incidents").click()
            expect(
                page.get_by_text("incident(s) erased from the live tenant store.", exact=False)
            ).to_be_visible()
            assert client.get(f"/v1/incidents/{erased}").json()["state"] == "ERASED"
        login(page, keys[0])
        expect(page.get_by_label("Incident to review")).to_be_visible()
        target = (
            page.get_by_label("Incident to review")
            .locator("option")
            .evaluate_all(
                "options => options.find(option => option.textContent.includes('unlabeled'))?.value"
            )
        )
        assert target
        for index, key in enumerate(keys):
            if index:
                login(page, key)
            page.get_by_label("Incident to review").select_option(target)
            expect(page.get_by_label("Blind audit: hide model suggestions")).to_be_checked()
            page.get_by_label("Responsible team").select_option("Database")
            for slot in SLOTS:
                page.locator(f"select#slot-{slot}").select_option("MISSING")
            page.get_by_role("button", name="Save independent label").click()
            expect(page.get_by_text("Independent label saved under your enrolled identity.")).to_be_visible()
        with httpx.Client(
            base_url=env["RESOLVEIT_API_URL"], headers={"Authorization": f"Bearer {env['RESOLVEIT_API_KEY']}"}
        ) as client:
            records = client.get("/v1/review?blind=true&limit=50").json()["items"]
            saved = next(record for record in records if record["incident_id"] == target)
            assert saved["label_count"] == 2 and saved["status"] == "synthetic_labeled"
            exported = client.get(f"/v1/review/export?split={saved['split']}&limit=100").json()
            exported_label = next(record for record in exported["records"] if record["incident_id"] == target)
            assert exported_label["provenance"] == "human_on_synthetic"
            assert "human_gold" not in str(exported), "Synthetic annotation cannot become human gold"
        context.close()
        browser.close()
    return {
        "axe": checks,
        "intake": "routed_database",
        "csv": "connected",
        "settings": "saved",
        "erasure": "verified",
        "dual_annotation": "two_enrolled_synthetic_reviewers",
        "human_gold": False,
    }

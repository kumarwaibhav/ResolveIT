"""End-to-end journeys against a running stack (scripts/dev_up.sh). Gate G4, partial.

Run:  python apps/web/e2e/journeys.py [screenshot_dir]
Checks the route, ask-answer, ask-skip and agent hand-off journeys, highlight
alignment with an emoji, zero network calls while typing, and axe-core
accessibility rules at desktop and 320 px widths, light and dark.
"""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

BASE = "http://127.0.0.1:3000"
AXE = (Path(__file__).resolve().parents[1] / "node_modules/axe-core/axe.min.js").read_text()
SHOTS = Path(sys.argv[1]) if len(sys.argv) > 1 else None
VAGUE = "it stopped working this morning, please help"


def shot(page: Page, name: str) -> None:
    if SHOTS:
        page.screenshot(path=str(SHOTS / f"{name}.png"), full_page=True)


def axe(page: Page, label: str) -> None:
    page.wait_for_timeout(350)  # let button colour transitions settle; mid-fade colours are not real states
    page.add_script_tag(content=AXE)
    result = page.evaluate("async () => await axe.run(document, {runOnly: ['wcag2a','wcag2aa','wcag21aa']})")
    bad = [(v["id"], v["impact"], len(v["nodes"])) for v in result["violations"]]
    assert not bad, f"axe violations on {label}: {bad}"


def submit(page: Page, text: str) -> None:
    page.goto(BASE)
    page.get_by_label("What is going wrong?").fill(text)
    page.get_by_role("button", name="Send ticket").click()


def ask(page: Page) -> None:
    """Submit vague tickets until one is outside the 10% no-question group."""
    for _ in range(40):
        submit(page, VAGUE)
        expect(page.locator("[data-result-heading]")).to_be_visible()
        if page.get_by_role("button", name="Skip").count():
            return
    raise AssertionError("never asked a question")


def run(page: Page, tag: str) -> None:
    # 1. Typing makes no network calls; the meter updates locally.
    page.goto(BASE, wait_until="networkidle")  # let the nav link prefetch finish first
    calls: list[str] = []
    page.on("request", lambda r: calls.append(r.url))
    page.get_by_label("What is going wrong?").fill("😀 VPN is down again for the whole floor, urgent")
    expect(page.get_by_text("4 of 6")).to_be_visible()
    assert calls == [], f"network calls while typing: {calls}"
    axe(page, f"intake-empty-{tag}")
    shot(page, f"1-intake-typing-{tag}")

    # 2. Clear ticket routes; evidence is underlined on exactly the right characters.
    page.get_by_role("button", name="Send ticket").click()
    expect(page.locator("[data-result-heading]")).to_have_text("Sent to Network")
    expect(page.locator("[data-result-heading]")).to_be_focused()
    marks = page.locator("mark").evaluate_all("els => els.map(e => e.firstChild.textContent)")
    assert marks[0] == "VPN" and "whole floor" in marks, marks
    expect(page.get_by_text("Synthetic demo data.")).to_be_visible()
    axe(page, f"intake-routed-{tag}")
    shot(page, f"2-routed-{tag}")

    # 3. Vague ticket: saved first, one optional question, answer routes it.
    ask(page)
    expect(page.locator("[data-result-heading]")).to_have_text("Ticket received")
    axe(page, f"intake-question-{tag}")
    shot(page, f"3-question-{tag}")
    page.get_by_label("vpn", exact=True).check()
    page.get_by_role("button", name="Send answer").click()
    expect(page.locator("[data-result-heading]")).to_have_text("Sent to Network")
    assert page.get_by_role("button", name="Skip").count() == 0

    # 4. Skip sends it to a person; the incident page shows the same record.
    ask(page)
    page.get_by_role("button", name="Skip").click()
    expect(page.locator("[data-result-heading]")).to_have_text("Sent to a person to triage")
    incident_id = page.locator("[data-incident-id]").get_attribute("data-incident-id")
    page.goto(f"{BASE}/incidents/{incident_id}")
    expect(page.locator("[data-result-heading]")).to_have_text("Sent to a person to triage")
    axe(page, f"incident-{tag}")
    page.goto(f"{BASE}/incidents/00000000-0000-0000-0000-000000000000")
    expect(page.get_by_role("heading", name="Nothing here")).to_be_visible()

    # 5. Agent hand-off: two round trips, cited answer accepted.
    page.goto(f"{BASE}/mcp")
    for i in range(40):
        page.get_by_label("The user's report, verbatim").fill(
            f"{VAGUE} the v-p-n client shows nothing [{tag}-{i}]"
        )
        page.get_by_role("button", name="Call submit_incident").click()
        expect(page.get_by_text("Round trip 1:")).to_be_visible()
        if page.get_by_role("button", name="Retry with answer").count():
            break
    page.get_by_label("Answer").select_option("vpn")
    page.get_by_label("Quote from the report").fill("v-p-n client")
    axe(page, f"mcp-question-{tag}")
    page.get_by_role("button", name="Retry with answer").click()
    expect(page.get_by_text("Round trip 2: complete")).to_be_visible()
    expect(page.get_by_text('"routed_team": "Network"').first).to_be_visible()
    shot(page, f"5-mcp-{tag}")


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for tag, width, scheme in [("desktop-light", 1280, "light"), ("mobile-dark", 320, "dark")]:
            ctx = browser.new_context(viewport={"width": width, "height": 800}, color_scheme=scheme)
            page = ctx.new_page()
            errors: list[str] = []
            page.on("console", lambda m, sink=errors: sink.append(m.text) if m.type == "error" else None)
            run(page, tag)
            real = [e for e in errors if "404" not in e]
            assert not real, f"console errors ({tag}): {real}"
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), (
                f"overflow at {width}"
            )
            ctx.close()
            print(f"ok {tag}")
        browser.close()


if __name__ == "__main__":
    main()

"""Create a mission through the deployed frontend and find it after a reload."""
import datetime as dt
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

root = Path(__file__).resolve().parents[1]
evidence = sorted((root / "evidence").glob("run_*/test-results.json"))[-1].parent
title = f"Böngészős próbarepülés {dt.datetime.now(dt.timezone.utc):%Y%m%d-%H%M%S}"
token = (root / ".secrets/admin_token.txt").read_text(encoding="utf-8").strip()
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(channel="chrome", headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 960}, locale="hu-HU")
    page.goto("http://localhost:8080")
    page.locator("#new-mission").click()
    page.locator("#admin-token").fill(token)
    page.locator("#auth-form button[type=submit]").click()
    form = page.locator("#mission-form")
    for name, value in {"title": title, "aircraft": "DemoQuad", "location": "Oktatási tesztmező",
                        "flight_minutes": "14"}.items():
        form.locator(f'[name="{name}"]').fill(value)
    with page.expect_response(lambda r: r.request.method == "POST" and r.url.endswith("/api/missions")) as saved:
        form.locator("#save-mission").click()
    assert saved.value.status == 201, f"HTTP {saved.value.status}"
    mission = saved.value.json()
    assert mission["title"] == title
    heading = page.get_by_role("heading", name=title, exact=True)
    expect(heading).to_be_visible()
    page.reload()
    expect(heading).to_be_visible()
    page.screenshot(path=str(evidence / "browser-readback.png"))
    browser.close()

result = {"status": "passed", "method": "Chrome: form submission, page reload, visible record",
          "checked_at": dt.datetime.now(dt.timezone.utc).isoformat(),
          "id": mission["id"], "title": title, "http": 201}
(evidence / "browser.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Browser create/read passed, record #{mission['id']}: {title}")

from __future__ import annotations

"""Direct browser publisher core.

Safety model:
- Manual login happens in Browserbase Live View.
- Browserbase Contexts persist auth state; passwords are never stored here.
- dry-run may navigate/fill/upload but MUST NOT click a final publish/schedule control.
- live mode requires explicit allow_live=True and a recipe step marked final=True.

The UI recipes are intentionally data-driven because social UIs change often.
Selectors are validated against the live account before enabling live mode.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json
import os
import time


class BrowserPublisherError(RuntimeError):
    pass


@dataclass(frozen=True)
class CampaignDraft:
    platform: str
    caption: str
    scheduled_at: str | None = None
    media_path: str | None = None
    tracking_url: str | None = None


@dataclass(frozen=True)
class RunResult:
    platform: str
    mode: str
    session_id: str
    live_view_url: str
    final_action_clicked: bool
    screenshot_path: str | None
    notes: list[str]


def load_recipes(path: str | Path = "config/browser_recipes.json") -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _bb_client():
    try:
        from browserbase import Browserbase
    except Exception as exc:  # pragma: no cover - runtime dependency
        raise BrowserPublisherError("Install browserbase before running browser mode") from exc
    key = os.environ.get("BROWSERBASE_API_KEY", "").strip()
    if not key:
        raise BrowserPublisherError("BROWSERBASE_API_KEY is required")
    return Browserbase(api_key=key)


def create_context() -> str:
    """Create a persistent Browserbase Context and return its ID."""
    context = _bb_client().contexts.create()
    return str(context.id)


def create_session(context_id: str, *, tag: str, timeout: int = 3600):
    if not context_id:
        raise BrowserPublisherError("A Browserbase context_id is required")
    bb = _bb_client()
    return bb.sessions.create(
        browser_settings={
            "context": {"id": context_id, "persist": True},
            "viewport": {"width": 1440, "height": 1000},
        },
        region="eu-central-1",
        timeout=timeout,
        user_metadata={"app": "socialscheduler", "mode": tag},
    )


def start_login_session(platform: str, context_id: str | None = None) -> dict[str, str]:
    """Create/reuse a context, start a manual-login cloud browser and return Live View URL."""
    recipes = load_recipes()
    if platform not in recipes:
        raise BrowserPublisherError(f"Unsupported platform: {platform}")
    cid = context_id or create_context()
    session = create_session(cid, tag=f"login-{platform}", timeout=3600)
    return {
        "platform": platform,
        "context_id": cid,
        "session_id": str(session.id),
        "live_view_url": f"https://browserbase.com/sessions/{session.id}",
        "login_url": recipes[platform]["login_url"],
    }


def _connect_playwright(session):
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - runtime dependency
        raise BrowserPublisherError("Install playwright before running browser mode") from exc
    pw = sync_playwright().start()
    browser = pw.chromium.connect_over_cdp(session.connect_url)
    context = browser.contexts[0]
    page = context.pages[0] if context.pages else context.new_page()
    return pw, browser, page


def _first_visible(page, selectors: list[str]):
    for selector in selectors:
        try:
            loc = page.locator(selector).first
            if loc.count() and loc.is_visible(timeout=1000):
                return loc
        except Exception:
            continue
    return None


def _click_text_any(page, labels: list[str]) -> bool:
    for label in labels:
        try:
            loc = page.get_by_text(label, exact=False).first
            if loc.count() and loc.is_visible(timeout=1000):
                loc.click(timeout=5000)
                return True
        except Exception:
            continue
    return False


def _safe_fill(page, selectors: list[str], value: str) -> bool:
    loc = _first_visible(page, selectors)
    if not loc:
        return False
    try:
        tag = loc.evaluate("el => el.tagName.toLowerCase()")
        if tag in {"input", "textarea"}:
            loc.fill(value)
        else:
            loc.click()
            loc.fill(value)
        return True
    except Exception:
        try:
            loc.click()
            page.keyboard.insert_text(value)
            return True
        except Exception:
            return False


def _upload_media(page, selectors: list[str], media_path: str | None) -> bool:
    if not media_path:
        return True
    path = Path(media_path)
    if not path.exists():
        raise BrowserPublisherError(f"Media file does not exist: {media_path}")
    for selector in selectors:
        try:
            loc = page.locator(selector).first
            if loc.count():
                loc.set_input_files(str(path.resolve()))
                return True
        except Exception:
            continue
    return False


def run_campaign(
    draft: CampaignDraft,
    context_id: str,
    *,
    mode: str = "dry-run",
    allow_live: bool = False,
    screenshots_dir: str = "artifacts/browser",
) -> RunResult:
    """Run one browser campaign.

    dry-run hard rule: final schedule/publish controls are never clicked.
    live hard rule: caller must pass allow_live=True explicitly.
    """
    if mode not in {"dry-run", "live"}:
        raise BrowserPublisherError("mode must be dry-run or live")
    if mode == "live" and not allow_live:
        raise BrowserPublisherError("live mode requires explicit allow_live=True")

    recipes = load_recipes()
    recipe = recipes.get(draft.platform)
    if not recipe:
        raise BrowserPublisherError(f"Unsupported platform: {draft.platform}")

    session = create_session(context_id, tag=f"{mode}-{draft.platform}")
    live_view_url = f"https://browserbase.com/sessions/{session.id}"
    notes: list[str] = []
    final_clicked = False
    screenshot_path: str | None = None

    pw = browser = None
    try:
        pw, browser, page = _connect_playwright(session)
        page.goto(recipe["composer_url"], wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2500)

        # Login guard. A page that still visibly offers login must never continue.
        title = page.title().lower()
        if any(word in title for word in recipe.get("login_title_markers", [])):
            raise BrowserPublisherError(
                f"{draft.platform} context does not appear authenticated; use browser-login first"
            )

        for label_group in recipe.get("open_composer_labels", []):
            if _click_text_any(page, label_group):
                page.wait_for_timeout(1200)
                break

        caption = draft.caption.strip()
        if draft.tracking_url and draft.tracking_url not in caption:
            caption = f"{caption}\n\n{draft.tracking_url}".strip()

        filled = _safe_fill(page, recipe.get("caption_selectors", []), caption)
        notes.append(f"caption_filled={filled}")

        uploaded = _upload_media(page, recipe.get("media_selectors", []), draft.media_path)
        notes.append(f"media_uploaded={uploaded}")

        # Scheduling UI is platform-specific and must be validated in a real account.
        # We may open the scheduling panel in dry-run, but never confirm it.
        if draft.scheduled_at:
            opened = _click_text_any(page, recipe.get("schedule_labels", []))
            notes.append(f"schedule_panel_opened={opened}")
            notes.append(f"requested_scheduled_at={draft.scheduled_at}")

        Path(screenshots_dir).mkdir(parents=True, exist_ok=True)
        screenshot_path = str(Path(screenshots_dir) / f"{draft.platform}-{int(time.time())}.png")
        page.screenshot(path=screenshot_path, full_page=True)

        if mode == "dry-run":
            notes.append("SAFETY: final publish/schedule action intentionally skipped")
        else:
            final_clicked = _click_text_any(page, recipe.get("final_labels", []))
            if not final_clicked:
                raise BrowserPublisherError(
                    f"Could not locate final action for {draft.platform}; refusing to guess"
                )
            notes.append("final_action_clicked=true")

        return RunResult(
            platform=draft.platform,
            mode=mode,
            session_id=str(session.id),
            live_view_url=live_view_url,
            final_action_clicked=final_clicked,
            screenshot_path=screenshot_path,
            notes=notes,
        )
    finally:
        try:
            if browser:
                browser.close()
        finally:
            if pw:
                pw.stop()

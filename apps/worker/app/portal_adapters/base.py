"""
Shared helper utilities for portal adapters.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import structlog
from playwright.async_api import Page

logger = structlog.get_logger()


class SelectorNotFoundError(Exception):
    """Raised when none of the fallback selectors match on the page."""

    def __init__(self, selectors: list[str], context: str = "") -> None:
        self.selectors = selectors
        self.context = context
        super().__init__(
            f"None of the selectors matched{f' ({context})' if context else ''}: {selectors}"
        )


async def find_first_available(
    page: Page,
    selectors: list[str],
    timeout_ms: int = 3000,
    context: str = "",
) -> str:
    """
    Try each selector in order. Returns the first one that finds an element.
    Logs which selector worked (or fell back).
    Raises SelectorNotFoundError if none match.
    """
    for idx, selector in enumerate(selectors):
        try:
            await page.wait_for_selector(selector, timeout=timeout_ms, state="attached")
            if idx > 0:
                logger.info(
                    "selector_fallback_used",
                    selector=selector,
                    fallback_index=idx,
                    context=context,
                )
            else:
                logger.debug("selector_found", selector=selector, context=context)
            return selector
        except Exception:
            continue

    raise SelectorNotFoundError(selectors, context)


async def save_screenshot(page: Page, prefix: str, screenshot_dir: str) -> str:
    """Capture screenshot, save to disk, and return a web-accessible URL path.

    Files are saved under /app/artifacts/ which is served by the API at /artifacts/.
    Returns a URL path like /artifacts/screenshots/prefix_timestamp.png.
    """
    os.makedirs(screenshot_dir, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{ts}.png"
    fs_path = os.path.join(screenshot_dir, filename)
    try:
        await page.screenshot(path=fs_path, full_page=True)
        logger.info("screenshot_saved", path=fs_path)
    except Exception as exc:
        logger.warning("screenshot_failed", error=str(exc))

    # Convert filesystem path to web URL path served by the API
    # e.g. /app/artifacts/screenshots/foo.png → /artifacts/screenshots/foo.png
    url_path = fs_path.replace("/app/artifacts", "/artifacts", 1)
    return url_path


async def save_html_snapshot(page: Page, prefix: str, snapshot_dir: str) -> str:
    """Save HTML snapshot, and return a web-accessible URL path.

    Files are saved under /app/artifacts/ which is served by the API at /artifacts/.
    Returns a URL path like /artifacts/html_snapshots/prefix_timestamp.html.
    """
    os.makedirs(snapshot_dir, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{ts}.html"
    fs_path = os.path.join(snapshot_dir, filename)
    try:
        content = await page.content()
        with open(fs_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info("html_snapshot_saved", path=fs_path)
    except Exception as exc:
        logger.warning("html_snapshot_failed", error=str(exc))

    # Convert filesystem path to web URL path
    url_path = fs_path.replace("/app/artifacts", "/artifacts", 1)
    return url_path

"""
Unit tests for find_first_available selector helper.
Uses unittest.mock to avoid needing a real browser.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.portal_adapters.base import SelectorNotFoundError, find_first_available

pytestmark = pytest.mark.asyncio


def _make_page(found_on_selector: str | None = None) -> MagicMock:
    """
    Return a mock Page where wait_for_selector succeeds only for
    `found_on_selector` (raises Exception for all others).
    """
    page = MagicMock()

    async def _wait(selector, timeout=3000, state="attached"):
        if selector == found_on_selector:
            return MagicMock()
        raise Exception(f"Selector not found: {selector}")

    page.wait_for_selector = _wait
    return page


class TestFindFirstAvailable:
    async def test_first_selector_matches(self):
        page = _make_page('[data-testid="booking-card"]')
        result = await find_first_available(
            page,
            ['[data-testid="booking-card"]', ".booking-card", ".job-row"],
        )
        assert result == '[data-testid="booking-card"]'

    async def test_fallback_to_second_selector(self):
        page = _make_page(".booking-card")
        result = await find_first_available(
            page,
            ['[data-testid="booking-card"]', ".booking-card", ".job-row"],
        )
        assert result == ".booking-card"

    async def test_fallback_to_third_selector(self):
        page = _make_page(".job-row")
        result = await find_first_available(
            page,
            ['[data-testid="booking-card"]', ".booking-card", ".job-row"],
        )
        assert result == ".job-row"

    async def test_all_selectors_fail_raises_error(self):
        page = _make_page(None)  # none will match
        with pytest.raises(SelectorNotFoundError) as exc_info:
            await find_first_available(
                page,
                ['[data-testid="x"]', ".x", "#x"],
                context="test_context",
            )
        assert '[data-testid="x"]' in exc_info.value.selectors
        assert ".x" in exc_info.value.selectors
        assert "#x" in exc_info.value.selectors

    async def test_error_includes_context(self):
        page = _make_page(None)
        with pytest.raises(SelectorNotFoundError) as exc_info:
            await find_first_available(page, [".nope"], context="login")
        assert "login" in exc_info.value.context

    async def test_error_message_contains_selector_list(self):
        page = _make_page(None)
        with pytest.raises(SelectorNotFoundError) as exc_info:
            await find_first_available(page, [".a", ".b"])
        assert ".a" in str(exc_info.value)
        assert ".b" in str(exc_info.value)

    async def test_single_selector_found(self):
        page = _make_page(".only")
        result = await find_first_available(page, [".only"])
        assert result == ".only"

    async def test_single_selector_not_found(self):
        page = _make_page(None)
        with pytest.raises(SelectorNotFoundError):
            await find_first_available(page, [".only"])

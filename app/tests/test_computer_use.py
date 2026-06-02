"""Tests for the computer use tools."""

from __future__ import annotations

import pytest

from app.tools.computer_use import ComputerUseTools


@pytest.fixture
def tools():
    return ComputerUseTools()


@pytest.fixture
def enabled_tools():
    return ComputerUseTools(enabled=True)


def test_disabled_by_default():
    tools = ComputerUseTools()
    assert tools._enabled is False


@pytest.mark.asyncio
async def test_action_when_disabled(tools):
    result = await tools.click(100, 100)
    assert result.success is False
    assert result.error == "ComputerUseTools is disabled"


@pytest.mark.asyncio
async def test_initialize_enabled(enabled_tools):
    assert enabled_tools._enabled is True
    await enabled_tools.initialize()
    assert enabled_tools._screen is not None


@pytest.mark.asyncio
async def test_click_updates_cursor(enabled_tools):
    result = await enabled_tools.click(100, 200)
    assert result.success is True
    assert result.cursor_position == (100, 200)
    assert enabled_tools._screen.cursor_x == 100
    assert enabled_tools._screen.cursor_y == 200


@pytest.mark.asyncio
async def test_type_text_appends_content(enabled_tools):
    await enabled_tools.type_text("Hello")
    assert enabled_tools._screen.content == "Hello"
    await enabled_tools.type_text(" World")
    assert enabled_tools._screen.content == "Hello World"


@pytest.mark.asyncio
async def test_screenshot_returns_state(enabled_tools):
    await enabled_tools.type_text("test content")
    result = await enabled_tools.screenshot()
    assert result.success is True
    assert result.screenshot_base64 is not None
    assert "test content" in result.screen_state


@pytest.mark.asyncio
async def test_move_cursor(enabled_tools):
    result = await enabled_tools.move_cursor(500, 300)
    assert result.success is True
    assert result.cursor_position == (500, 300)
    assert enabled_tools._screen.cursor_x == 500
    assert enabled_tools._screen.cursor_y == 300


@pytest.mark.asyncio
async def test_scroll(enabled_tools):
    await enabled_tools.move_cursor(0, 500)
    result = await enabled_tools.scroll(direction="down", amount=3)
    assert result.success is True
    assert enabled_tools._screen.cursor_y == 497

    result2 = await enabled_tools.scroll(direction="up", amount=2)
    assert result2.success is True
    assert enabled_tools._screen.cursor_y == 499


@pytest.mark.asyncio
async def test_get_screen_state(enabled_tools):
    await enabled_tools.click(100, 200)
    state = await enabled_tools.get_screen_state()
    assert "Screen(" in state
    assert "Cursor at (100, 200)" in state


@pytest.mark.asyncio
async def test_close(enabled_tools):
    await enabled_tools.type_text("data")
    await enabled_tools.close()
    assert enabled_tools._screen.content == ""
    assert enabled_tools._screen.cursor_x == 0
    assert enabled_tools._screen.cursor_y == 0

"""Computer use tools — simulated screen interaction for agents.

This module provides a simulation layer that lets agents interact with a
virtual screen (click, type, scroll, etc.) without requiring actual display
hardware. A real xdotool/scrot implementation can be swapped in later.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass

from app.utils.logging import get_logger

logger = get_logger(__name__)

_SCREEN_WIDTH = 1920
_SCREEN_HEIGHT = 1080


@dataclass
class ScreenState:
    """Current state of the simulated screen."""

    width: int = _SCREEN_WIDTH
    height: int = _SCREEN_HEIGHT
    cursor_x: int = 0
    cursor_y: int = 0
    content: str = ""


@dataclass
class ActionResult:
    """Result of a computer-use action."""

    success: bool
    screenshot_base64: str | None = None
    cursor_position: tuple[int, int] = (0, 0)
    screen_state: str = ""
    error: str | None = None


class ComputerUseTools:
    """Simulated computer interaction tools for agents.

    Provides methods that mimic mouse and keyboard input on a virtual
    screen. All actions are no-ops when *enabled* is ``False``.
    """

    def __init__(self, enabled: bool = False) -> None:
        self._enabled = enabled
        self._screen: ScreenState = ScreenState()

    async def initialize(self) -> None:
        """Set up the simulated screen state if the feature is enabled."""
        if not self._enabled:
            logger.info("ComputerUseTools disabled — skipping initialisation")
            return
        self._screen = ScreenState()
        logger.info("ComputerUseTools initialised (simulated)")

    async def click(self, x: int, y: int, button: str = "left") -> ActionResult:
        """Simulate a mouse click at the given coordinates.

        Args:
            x: Horizontal screen coordinate.
            y: Vertical screen coordinate.
            button: Mouse button (``"left"``, ``"right"``, ``"middle"``).

        Returns:
            ActionResult with updated cursor position.
        """
        if not self._enabled:
            return ActionResult(success=False, error="ComputerUseTools is disabled")
        self._screen.cursor_x = x
        self._screen.cursor_y = y
        logger.info("Simulated click at (%d, %d) with %s button", x, y, button)
        screen_repr = await self.get_screen_state()
        return ActionResult(
            success=True,
            cursor_position=(x, y),
            screen_state=screen_repr,
        )

    async def type_text(self, text: str) -> ActionResult:
        """Append text to the simulated screen content.

        Args:
            text: The string to type.

        Returns:
            ActionResult reflecting the new screen state.
        """
        if not self._enabled:
            return ActionResult(success=False, error="ComputerUseTools is disabled")
        self._screen.content += text
        logger.info("Simulated typing %d characters", len(text))
        screen_repr = await self.get_screen_state()
        return ActionResult(
            success=True,
            cursor_position=(self._screen.cursor_x, self._screen.cursor_y),
            screen_state=screen_repr,
        )

    async def screenshot(self) -> ActionResult:
        """Return a simulated screenshot of the current screen state.

        Returns:
            ActionResult with a base64-encoded placeholder and text state.
        """
        if not self._enabled:
            return ActionResult(success=False, error="ComputerUseTools is disabled")
        screen_repr = await self.get_screen_state()
        placeholder = base64.b64encode(b"simulated screenshot").decode()
        return ActionResult(
            success=True,
            screenshot_base64=placeholder,
            cursor_position=(self._screen.cursor_x, self._screen.cursor_y),
            screen_state=screen_repr,
        )

    async def scroll(self, direction: str = "down", amount: int = 1) -> ActionResult:
        """Simulate scrolling the virtual screen.

        Args:
            direction: ``"up"`` or ``"down"``.
            amount: Number of scroll steps.

        Returns:
            ActionResult with updated cursor position.
        """
        if not self._enabled:
            return ActionResult(success=False, error="ComputerUseTools is disabled")
        delta = -amount if direction == "down" else amount
        self._screen.cursor_y = max(
            0,
            min(self._screen.height - 1, self._screen.cursor_y + delta),
        )
        logger.info(
            "Simulated scroll %s by %d (cursor now at y=%d)",
            direction,
            amount,
            self._screen.cursor_y,
        )
        screen_repr = await self.get_screen_state()
        return ActionResult(
            success=True,
            cursor_position=(self._screen.cursor_x, self._screen.cursor_y),
            screen_state=screen_repr,
        )

    async def move_cursor(self, x: int, y: int) -> ActionResult:
        """Move the simulated cursor to absolute coordinates.

        Args:
            x: New horizontal position.
            y: New vertical position.

        Returns:
            ActionResult with the updated cursor position.
        """
        if not self._enabled:
            return ActionResult(success=False, error="ComputerUseTools is disabled")
        self._screen.cursor_x = x
        self._screen.cursor_y = y
        logger.info("Simulated cursor move to (%d, %d)", x, y)
        screen_repr = await self.get_screen_state()
        return ActionResult(
            success=True,
            cursor_position=(x, y),
            screen_state=screen_repr,
        )

    async def get_screen_state(self) -> str:
        """Return a text representation of the simulated screen."""
        if not self._enabled:
            return "[ComputerUseTools disabled]"
        return (
            f"Screen({self._screen.width}x{self._screen.height})\n"
            f"Cursor at ({self._screen.cursor_x}, {self._screen.cursor_y})\n"
            f"Content: {self._screen.content!r}"
        )

    async def close(self) -> None:
        """Clean up the simulated screen resources."""
        self._screen = ScreenState()
        logger.info("ComputerUseTools closed")

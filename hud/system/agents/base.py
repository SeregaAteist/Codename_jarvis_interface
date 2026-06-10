"""BaseAgent — abstract foundation for all JARVIS agents."""
from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30   # seconds
DEFAULT_RETRIES = 2


class BaseAgent(ABC):
    """Abstract base for every JARVIS agent.

    Subclasses must set `name` and `icon` as class attributes and implement
    `execute(task)`.  Sync agents should implement `ask(prompt)` instead and
    leave `execute` to call it via `asyncio.to_thread`.
    """

    name: str = "base"
    icon: str = "○"

    def __init__(
        self,
        name: str | None = None,
        config: dict[str, Any] | None = None,
        timeout: int = DEFAULT_TIMEOUT,
        retries: int = DEFAULT_RETRIES,
    ) -> None:
        if name:
            self.name = name
        self.config  = config or {}
        self.timeout = timeout
        self.retries = retries

    # ── Public API ────────────────────────────────────────────────────────────

    @abstractmethod
    async def execute(self, task: str) -> str:
        """Run the agent on *task* and return a response string."""

    def is_available(self) -> bool:
        """Return True if the agent can accept requests right now."""
        return True

    # ── Retry / timeout wrapper ───────────────────────────────────────────────

    async def run(self, task: str) -> str:
        """Call `execute` with timeout and retry logic.

        Retries up to `self.retries` times on transient errors.
        Returns the error message string on final failure so callers always
        get a displayable string.
        """
        last_error: Exception | None = None
        for attempt in range(1, self.retries + 2):  # retries + 1 total attempts
            try:
                return await asyncio.wait_for(self.execute(task), timeout=self.timeout)
            except asyncio.TimeoutError as e:
                last_error = e
                logger.warning(
                    "[%s] timeout after %ds (attempt %d/%d)",
                    self.name, self.timeout, attempt, self.retries + 1,
                )
            except Exception as e:
                last_error = e
                logger.warning(
                    "[%s] error on attempt %d/%d: %s",
                    self.name, attempt, self.retries + 1, e,
                )
            if attempt <= self.retries:
                await asyncio.sleep(min(2 ** attempt, 8))  # exponential back-off, cap 8s

        return self.handle_error(last_error)

    # ── Error handling ────────────────────────────────────────────────────────

    def handle_error(self, exc: Exception | None) -> str:
        """Format a final error into a user-visible Russian string."""
        if isinstance(exc, asyncio.TimeoutError):
            return f"Агент {self.name} не ответил за {self.timeout} секунд, сэр."
        if exc is not None:
            return f"Ошибка агента {self.name}: {exc}"
        return f"Агент {self.name} вернул пустой ответ, сэр."

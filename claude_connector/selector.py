"""Claude Connector — abstracts over multiple Claude access channels."""
from __future__ import annotations
import logging
import os
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)


class ClaudeSelector:
    """
    Tries Claude channels in priority order:
    1. Claude Code CLI (if installed)
    2. API Key (if ANTHROPIC_API_KEY set)
    3. Browser channel (claude.ai via Playwright) — future
    """

    async def query(self, prompt: str, max_tokens: int = 1000) -> Optional[str]:
        # Channel 1: API Key
        api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        if api_key:
            try:
                return await self._via_api(prompt, api_key, max_tokens)
            except Exception as e:
                logger.warning("[ClaudeSelector] API channel failed: %s", e)

        # Channel 2: Claude Code CLI
        if self._cli_available():
            try:
                return await self._via_cli(prompt)
            except Exception as e:
                logger.warning("[ClaudeSelector] CLI channel failed: %s", e)

        # Channel 3: Browser (stub — future)
        logger.warning("[ClaudeSelector] No Claude channel available")
        return None

    async def _via_api(self, prompt: str, api_key: str, max_tokens: int) -> str:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=api_key)
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    async def _via_cli(self, prompt: str) -> str:
        import asyncio
        proc = await asyncio.create_subprocess_exec(
            "claude", "--print", prompt,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        return stdout.decode().strip()

    def _cli_available(self) -> bool:
        try:
            r = subprocess.run(["claude", "--version"], capture_output=True, timeout=3)
            return r.returncode == 0
        except Exception:
            return False

    def is_available(self) -> bool:
        return bool(os.getenv("ANTHROPIC_API_KEY", "").strip()) or self._cli_available()


# Singleton
selector = ClaudeSelector()

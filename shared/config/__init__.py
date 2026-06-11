"""Единый источник правды конфигурации J.A.R.V.I.S. (слоистый, мульти-бот).

Сборка трёх слоёв:
    base.py            — пути, лог-уровни, общие дефолты
    secrets.py         — .env (токены/ключи), fail-fast
    modules/<name>.yaml — настройки конкретного бота

Каждый бот зовёт load("<name>") и получает типизированный ModuleConfig.
Для обратной совместимости media_analyzer доступен как CFG.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from shared.config import base, secrets


@dataclass(frozen=True)
class ModuleConfig:
    name: str
    # Telegram
    TELEGRAM_TOKEN: str
    TELEGRAM_CHAT_ID: int
    OWNER_USER_ID: int
    TOPIC_ID: int
    TASKS_TOPIC_ID: int
    # LLM
    GEMINI_KEYS: list[str]
    CLAUDE_KEYS: list[str]
    GROQ_API_KEY: str
    GEMINI_MODEL: str
    GEMINI_FALLBACK_MODEL: str
    CLAUDE_MODEL: str
    OLLAMA_HOST: str
    OLLAMA_MODEL: str
    # Пути и лимиты
    TASKS_DIR: Path
    DATA_DIR: Path
    BATCH_TIMEOUT: int
    MAX_IMAGE_SIZE: int
    # Executor (default ssh — рабочий поток; см. base.DEFAULTS)
    EXECUTOR: str
    # Сырой yaml бота — для секций вроде llm.roles (используется роутером, Фаза 3)
    raw: dict = field(default_factory=dict)

    def require_security_ids(self) -> None:
        """Fail-fast по обязательным ID безопасности (RCE-уровень доступа)."""
        if not self.TELEGRAM_TOKEN or self.TELEGRAM_CHAT_ID == 0 or self.OWNER_USER_ID == 0:
            raise RuntimeError(
                "CONFIG FAIL-FAST: не заданы обязательные ID безопасности "
                "(TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID / OWNER_USER_ID) в .env"
            )


def load(module: str) -> ModuleConfig:
    y = base.load_module_yaml(module)
    tg = y.get("telegram", {})
    llm = y.get("llm", {})
    media = y.get("media", {})
    d = base.DEFAULTS

    token_env = tg.get("token_env", "TELEGRAM_BOT_TOKEN")  # мульти-бот: у каждого свой токен
    return ModuleConfig(
        name=module,
        TELEGRAM_TOKEN=secrets.req(token_env),
        TELEGRAM_CHAT_ID=int(secrets.req("TELEGRAM_CHAT_ID")),
        OWNER_USER_ID=int(secrets.req("OWNER_USER_ID")),
        TOPIC_ID=int(secrets.opt("TOPIC_ID", "0")),
        TASKS_TOPIC_ID=int(secrets.opt("TASKS_TOPIC_ID", "0")),
        GEMINI_KEYS=secrets.gemini_keys(),
        CLAUDE_KEYS=secrets.claude_keys(),
        GROQ_API_KEY=secrets.opt("GROQ_API_KEY"),
        GEMINI_MODEL=secrets.opt("GEMINI_MODEL", llm.get("gemini_model", d["gemini_model"])),
        GEMINI_FALLBACK_MODEL=secrets.opt(
            "GEMINI_FALLBACK_MODEL", llm.get("gemini_fallback_model", d["gemini_fallback_model"])
        ),
        CLAUDE_MODEL=llm.get("claude_model", d["claude_model"]),
        OLLAMA_HOST=secrets.opt("OLLAMA_HOST", d["ollama_host"]),
        OLLAMA_MODEL=secrets.opt("OLLAMA_MODEL", llm.get("ollama_model", d["ollama_model"])),
        TASKS_DIR=Path(secrets.opt("TASKS_DIR", str(base.TASKS_DIR))),
        DATA_DIR=base.DATA_DIR,
        BATCH_TIMEOUT=int(secrets.opt("BATCH_TIMEOUT", str(media.get("batch_timeout", d["batch_timeout"])))),
        MAX_IMAGE_SIZE=int(secrets.opt("MAX_IMAGE_SIZE", str(media.get("max_image_size", d["max_image_size"])))),
        EXECUTOR=secrets.opt("EXECUTOR", y.get("executor", d["executor"])),
        raw=y,
    )


# Дефолтный синглтон для обратной совместимости (media_analyzer).
CFG: ModuleConfig = load("media_analyzer")

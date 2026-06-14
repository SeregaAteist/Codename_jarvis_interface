"""S-7: минимальный smoke — ловить регрессии автоматически (не coverage).

Покрывает: импорт цепочки, classify, retry (mock), get_executor, очередь, заморозку пула.
"""

import asyncio


def test_imports():
    import analyzers.gemini_video  # noqa: F401
    import bot.handlers  # noqa: F401
    import bot.task_handler  # noqa: F401
    import config  # noqa: F401
    import executor  # noqa: F401
    import pipeline.deep  # noqa: F401
    import pipeline.quick  # noqa: F401

    import core.bus  # noqa: F401
    import core.registry  # noqa: F401
    import core.scheduler  # noqa: F401
    import shared.errors  # noqa: F401
    import shared.llm.key_pool  # noqa: F401
    import shared.llm.router  # noqa: F401
    import shared.logging_setup  # noqa: F401


def test_classify():
    from shared.errors import classify, is_retriable

    assert classify(Exception("429 RESOURCE_EXHAUSTED quota")) == "GEMINI_429"
    assert classify(Exception("503 model is overloaded")) == "GEMINI_503"
    assert classify(Exception("500 internal error")) == "GEMINI_500"
    assert classify(Exception("400 invalid argument")) == "GEMINI_400"
    assert classify(Exception("ConnectionError: refused")) == "NET"
    assert classify(Exception("нечто странное")) == "SYS"
    assert is_retriable("GEMINI_503")
    assert not is_retriable("GEMINI_429")


def test_retry_backoff(monkeypatch):
    import shared.errors as E

    async def _fast(_):  # ускоряем backoff
        return None

    monkeypatch.setattr(E.asyncio, "sleep", _fast)

    async def run():
        calls = {"n": 0}

        async def att_ok():
            calls["n"] += 1
            if calls["n"] < 2:
                raise Exception("503 overloaded")
            return "ok"

        assert await E.retry_with_backoff(att_ok, max_attempts=5) == "ok"
        assert calls["n"] == 2

        c2 = {"n": 0}

        async def att_429():
            c2["n"] += 1
            raise Exception("429 quota")

        try:
            await E.retry_with_backoff(att_429, max_attempts=5)
        except Exception:
            pass
        assert c2["n"] == 1  # 429 не повторяется (анти-шторм)

    asyncio.run(run())


def test_get_executor():
    from executor import get_executor
    from executor.ssh_executor import SshExecutor

    ex = get_executor()  # default ssh
    assert isinstance(ex, SshExecutor)
    assert hasattr(ex, "get_plan") and hasattr(ex, "submit")


def test_local_queue_roundtrip(tmp_path, monkeypatch):
    import executor.local_queue as LQ

    monkeypatch.setattr(LQ, "DB", tmp_path / "q.db")
    q = LQ.LocalQueueExecutor()
    tid = q._submit({"prompt": "x"})
    assert q._status(tid) == "pending"
    nid, payload = q.next_pending()
    assert nid == tid and payload["prompt"] == "x"
    q.mark(tid, "done", "res")
    assert q._status(tid) == "done"
    assert q.result(tid) == "res"


def test_pool_freeze_no_storm():
    from shared.llm.key_pool import SimplePool

    p = SimplePool(["k1"], "gemini")
    p.report_quota_exceeded("k1")
    assert p.get() is None  # все заморожены → стоп (без реюза мёртвого ключа)
    p2 = SimplePool(["a", "b"], "gemini")
    p2.report_quota_exceeded("a")
    assert p2.get() == "b"


def test_log_mask():
    from shared.logging_setup import mask

    masked = mask(
        "POST .../bot8854500058:AAGyC7yI8NlfZHqZquRkrKc5Ewqs4OHyOmg/getUpdates"
    )
    assert "AAGyC7yI8NlfZHqZ" not in masked
    assert "***" in masked

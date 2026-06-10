"""
Jarvis Russian TTS pipeline (best available, offline-first):

Priority:
  1. Silero TTS  — deep aidar voice, fully offline
  2. edge-tts    — Microsoft ru-RU-DmitryNeural, free online, no key needed
  3. macOS say   — fallback, always works

All paths → sox FX chain → afplay
"""
import asyncio
import os
import subprocess
import tempfile
import threading

# Sox Jarvis FX: normalise → pitch drop → light reverb → bass boost → soften highs
_SOX_FX_ARGS = [
    "gain", "-n", "-6",
    "pitch", "-120",
    "reverb", "20", "15", "40",
    "bass", "+5",
    "treble", "-2",
]

# ── Silero singleton (offline, loads lazily) ──────────────────────────────────
_silero        = None
_silero_lock   = threading.Lock()
_silero_failed = False


def _try_load_silero():
    global _silero, _silero_failed
    if _silero_failed:
        return None
    if _silero is not None:
        return _silero
    with _silero_lock:
        if _silero is not None:
            return _silero
        try:
            import torch
            print("[tts] Loading Silero model…")
            m, _ = torch.hub.load(
                repo_or_dir="snakers4/silero-models",
                model="silero_tts",
                language="ru",
                speaker="v3_1_ru",
                trust_repo=True,
            )
            m.to("cpu")
            _silero = m
            print("[tts] Silero ready.")
            return _silero
        except Exception as e:
            print(f"[tts] Silero unavailable ({e}), using edge-tts.")
            _silero_failed = True
            return None


# ── edge-tts (online, free) ───────────────────────────────────────────────────

def _edge_tts_sync(text: str, raw: str) -> bool:
    """Synthesise to `raw` path. Returns True on success."""
    try:
        import edge_tts
        fd_mp3, mp3 = tempfile.mkstemp(suffix=".mp3", prefix="jarvis_edge_")
        os.close(fd_mp3)

        async def _gen():
            c = edge_tts.Communicate(text, voice="ru-RU-DmitryNeural")
            await c.save(mp3)

        asyncio.run(_gen())
        r = subprocess.run(["sox", mp3, raw], capture_output=True)
        try:
            os.unlink(mp3)
        except OSError:
            pass
        return r.returncode == 0 and os.path.exists(raw)
    except Exception as e:
        print(f"[tts] edge-tts failed: {e}")
        return False


# ── macOS say fallback ────────────────────────────────────────────────────────

def _say_fallback(text: str, voice: str, rate: int, raw: str) -> bool:
    try:
        fd_aiff, aiff = tempfile.mkstemp(suffix=".aiff", prefix="jarvis_say_")
        os.close(fd_aiff)
        subprocess.run(
            ["say", "-v", voice, "-r", str(rate), "-o", aiff, text],
            check=True, capture_output=True,
        )
        subprocess.run(["sox", aiff, raw], check=True, capture_output=True)
        try:
            os.unlink(aiff)
        except OSError:
            pass
        return True
    except Exception as e:
        print(f"[tts] say fallback error: {e}")
        return False


# ── Public API ────────────────────────────────────────────────────────────────

def speak(text: str, voice: str = "Milena", rate: int = 180) -> None:
    """Non-blocking speak — launches in daemon thread."""
    threading.Thread(target=_run, args=(text, voice, rate), daemon=True).start()


def stop() -> None:
    subprocess.run(["killall", "-q", "afplay"], check=False)


# ── Internal ──────────────────────────────────────────────────────────────────

def _run(text: str, voice: str, rate: int) -> None:
    # Per-call temp files — no race between concurrent speak() calls
    fd_raw, raw = tempfile.mkstemp(suffix=".wav", prefix="jarvis_raw_")
    fd_fx,  fx  = tempfile.mkstemp(suffix=".wav", prefix="jarvis_fx_")
    os.close(fd_raw)
    os.close(fd_fx)

    try:
        generated = False

        # 1 — Try Silero (offline)
        model = _try_load_silero()
        if model is not None:
            try:
                import soundfile as sf
                audio = model.apply_tts(text=text, speaker="aidar", sample_rate=48000)
                sf.write(raw, audio.numpy(), 48000)
                generated = True
            except Exception as e:
                print(f"[tts] Silero synthesis error: {e}")

        # 2 — Try edge-tts (online, free)
        if not generated:
            generated = _edge_tts_sync(text, raw)

        # 3 — macOS say (always works)
        if not generated:
            generated = _say_fallback(text, voice, rate, raw)

        if not generated:
            subprocess.run(["say", "-v", voice, text], check=False)
            return

        # Apply sox FX chain
        r = subprocess.run(["sox", raw, fx] + _SOX_FX_ARGS, capture_output=True)
        play = fx if r.returncode == 0 and os.path.exists(fx) else raw
        subprocess.run(["afplay", play], check=False)

    finally:
        for f in (raw, fx):
            try:
                if os.path.exists(f):
                    os.unlink(f)
            except OSError:
                pass


# ── Standalone test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Testing Jarvis TTS…")
    _run("Все системы в норме. Добро пожаловать, сэр.", "Milena", 180)
    print("Done.")

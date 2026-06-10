"""
Jarvis TTS pipeline:
  Russian text → claude CLI translation → Piper EN voice → sox FX → afplay
  Fallback (no Piper): macOS say -v Milena → sox FX → afplay
"""
import os
import re
import subprocess
import tempfile
import threading

_ROOT  = os.path.dirname(os.path.abspath(__file__))
_MODEL = os.path.join(_ROOT, "models", "jarvis.onnx")

# Sox effect chain — subtle Iron Man character without clipping
_SOX_FX = [
    "gain", "-n", "-6",   # normalize with -6 dB headroom
    "pitch", "-80",        # slight pitch drop (~0.8 semitones)
    "reverb", "10", "5", "20",  # light room reverb
    "bass", "+2",          # warm low-end boost
    "treble", "-1",        # soften harsh highs
]


def speak(text: str, voice: str = "Milena", rate: int = 180) -> None:
    """Non-blocking. Speaks text in the background."""
    threading.Thread(target=_run, args=(text, voice, rate), daemon=True).start()


def stop() -> None:
    subprocess.run(["killall", "-q", "afplay"], check=False)
    subprocess.run(["killall", "-q", "say"],    check=False)


# ── Internal ──────────────────────────────────────────────────────────────────

def _has_cyrillic(text: str) -> bool:
    return bool(re.search(r"[а-яёА-ЯЁ]", text))


def _translate(text: str) -> str:
    """Translate Russian → English via claude CLI. Returns original on failure."""
    prompt = (
        "Translate to natural English in one sentence, no explanation, "
        f"no quotes:\n{text}"
    )
    try:
        r = subprocess.run(
            ["claude", "--print"], input=prompt,
            capture_output=True, text=True, timeout=15,
        )
        result = r.stdout.strip()
        if result and r.returncode == 0:
            return result
    except Exception:
        pass
    return text  # fallback: speak original


def _run(text: str, voice: str, rate: int) -> None:
    raw = tempfile.mktemp(suffix=".wav")
    out = tempfile.mktemp(suffix=".wav")
    raw_aiff = tempfile.mktemp(suffix=".aiff")

    try:
        en_text = _translate(text) if _has_cyrillic(text) else text

        # ── Try Piper (English voice) ──────────────────────────────────
        piper_ok = False
        if os.path.exists(_MODEL):
            try:
                r = subprocess.run(
                    ["piper", "--model", _MODEL, "--output_file", raw],
                    input=en_text, capture_output=True, text=True, timeout=20,
                )
                piper_ok = r.returncode == 0 and os.path.exists(raw)
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass

        # ── Fallback: macOS say → AIFF ─────────────────────────────────
        if not piper_ok:
            subprocess.run(
                ["say", "-v", voice, "-r", str(rate), "-o", raw_aiff, text],
                check=True, capture_output=True,
            )
            # Convert AIFF → WAV for uniform sox handling
            subprocess.run(
                ["sox", raw_aiff, raw], check=True, capture_output=True,
            )

        # ── Apply sox FX ───────────────────────────────────────────────
        r2 = subprocess.run(
            ["sox", raw, out] + _SOX_FX,
            capture_output=True,
        )
        play_file = out if (r2.returncode == 0 and os.path.exists(out)) else raw
        subprocess.run(["afplay", play_file], check=False)

    except Exception:
        # Ultimate fallback — plain macOS say
        subprocess.run(["say", "-v", voice, "-r", str(rate), text], check=False)

    finally:
        for f in (raw, out, raw_aiff):
            try:
                if f and os.path.exists(f):
                    os.unlink(f)
            except OSError:
                pass

"""
Continuous wake-word listener.
Stage 1 — faster-whisper transcribes 2-second chunks,
           rapidfuzz checks for wake-word variants in Russian.
Stage 2 — command extracted from same utterance or 5-second follow-up.
"""
import threading

SAMPLE_RATE   = 16000
CHUNK_SECS    = 2          # seconds per listen window
CMD_SECS      = 5          # follow-up recording if no command after wake word
SILENCE_RMS   = 0.001      # skip near-silent chunks
MIN_CMD_RMS   = 0.002      # minimum signal to attempt transcription

# ── Wake word variants ────────────────────────────────────────────────────────
WAKE_VARIANTS = [
    "джарвис", "джарвиз", "джарви",
    "джару из", "джару",  "жарвис",
    "джарвіс", "jarvis",  "harvey",
    "харвис",  "харви",
]
FUZZY_THRESHOLD = 78   # rapidfuzz partial_ratio threshold

# Set to False to permanently disable mic input (TTS/speaker unaffected).
VOICE_ENABLED: bool = False

_status_cbs: list = []
_paused = False


def on_status(cb) -> None:
    _status_cbs.append(cb)


def _emit(state: str) -> None:
    for cb in _status_cbs:
        try:
            cb(state)
        except Exception:
            pass


def start(on_command) -> None:
    if not VOICE_ENABLED:
        print("[listener] Voice input disabled — skipping mic init")
        _emit("disabled")
        return
    threading.Thread(target=_loop, args=(on_command,), daemon=True).start()


def toggle() -> bool:
    """Toggle pause/resume. Returns True if now paused. No-op when disabled."""
    if not VOICE_ENABLED:
        return True  # treat disabled as permanently paused
    global _paused
    _paused = not _paused
    _emit("paused" if _paused else "listening")
    return _paused


def is_paused() -> bool:
    return True if not VOICE_ENABLED else _paused


def is_disabled() -> bool:
    return not VOICE_ENABLED


# ── Wake-word check ───────────────────────────────────────────────────────────

def is_wake_word(text: str) -> tuple[bool, str]:
    """
    Returns (triggered, command_tail).
    command_tail is text after the wake word (may be empty).
    """
    from rapidfuzz import fuzz

    t = text.lower().strip()

    # 1. Exact substring match
    for variant in WAKE_VARIANTS:
        idx = t.find(variant)
        if idx != -1:
            tail = t[idx + len(variant):].strip(" ,.")
            return True, tail

    # 2. Fuzzy match on each word in the transcription
    words = t.split()
    for i, word in enumerate(words):
        for variant in WAKE_VARIANTS:
            if fuzz.ratio(variant, word) >= FUZZY_THRESHOLD:
                tail = " ".join(words[i + 1:]).strip(" ,.")
                return True, tail

    # 3. Fuzzy partial match on full text
    for variant in WAKE_VARIANTS:
        if fuzz.partial_ratio(variant, t) >= FUZZY_THRESHOLD + 5:
            return True, ""

    return False, ""


# ── Main loop ─────────────────────────────────────────────────────────────────

def _loop(on_command) -> None:
    try:
        import numpy as np
        import sounddevice as sd
        from faster_whisper import WhisperModel
    except ImportError as e:
        print(f"[listener] Missing dep: {e}")
        return

    try:
        model = WhisperModel("base", device="cpu", compute_type="int8")
        print("[listener] Whisper base ready")
    except Exception as e:
        print(f"[listener] Whisper init failed: {e}")
        return

    _emit("listening")
    print("[listener] Listening for 'Джарвис'…")

    while True:
        if _paused:
            import time as _time
            _time.sleep(0.5)
            continue
        try:
            # ── Stage 1: record chunk and transcribe ──────────────────────
            audio = sd.rec(
                int(CHUNK_SECS * SAMPLE_RATE),
                samplerate=SAMPLE_RATE, channels=1, dtype="float32",
            )
            sd.wait()
            flat = audio.flatten()

            rms = float(np.sqrt(np.mean(flat ** 2)))
            if rms < SILENCE_RMS:
                continue

            segs, _ = model.transcribe(
                flat, language="ru",
                beam_size=3,
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 200},
                condition_on_previous_text=False,
                compression_ratio_threshold=2.0,
                no_speech_threshold=0.6,
            )
            text = " ".join(s.text.strip() for s in segs).strip()
            if not text:
                continue

            # ── Stage 2: check wake word ──────────────────────────────────
            triggered, command = is_wake_word(text)
            if not triggered:
                continue

            print(f"[listener] Wake word! transcript=«{text}» command=«{command}»")
            _emit("waiting")

            # If command already in the same utterance — use it
            if command and len(command) > 2:
                _emit("thinking")
                on_command(command)
                _emit("listening")
                continue

            # Otherwise record follow-up
            print("[listener] Recording command…")
            cmd_audio = sd.rec(
                int(CMD_SECS * SAMPLE_RATE),
                samplerate=SAMPLE_RATE, channels=1, dtype="float32",
            )
            sd.wait()
            cmd_flat = cmd_audio.flatten()

            if float(np.sqrt(np.mean(cmd_flat ** 2))) < MIN_CMD_RMS:
                print("[listener] Follow-up too quiet, skipping")
                _emit("listening")
                continue

            segs2, _ = model.transcribe(
                cmd_flat, language="ru",
                beam_size=3,
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 300},
                condition_on_previous_text=False,
                compression_ratio_threshold=2.0,
                no_speech_threshold=0.6,
            )
            command = " ".join(s.text.strip() for s in segs2).strip()

            if command:
                print(f"[listener] Command: «{command}»")
                _emit("thinking")
                on_command(command)

            _emit("listening")

        except Exception as e:
            print(f"[listener] Error: {e}")
            _emit("listening")

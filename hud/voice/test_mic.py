import tempfile

import numpy as np
import sounddevice as sd
import soundfile as sf
from faster_whisper import WhisperModel

SAMPLERATE = 16000
SECONDS = 5

print(f"Устройство по умолчанию: {sd.query_devices(kind='input')['name']}")
print(f"Говори что-нибудь... ({SECONDS} секунд)")

recording = sd.rec(
    int(SECONDS * SAMPLERATE), samplerate=SAMPLERATE, channels=1, dtype="float32"
)
sd.wait()

rms = float(np.sqrt(np.mean(recording**2)))
status = (
    "ОК"
    if rms >= 0.002
    else ("слабо, но попробуем" if rms >= 0.001 else "слишком тихо")
)
print(f"Записано. RMS громкость: {rms:.5f} ({status})")

print("Загружаю модель и распознаю...")
model = WhisperModel("base", device="cpu", compute_type="int8")

with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
    sf.write(f.name, recording, SAMPLERATE)
    segments, info = model.transcribe(
        f.name,
        language="ru",
        beam_size=5,
        vad_filter=True,  # back on — mic is now loud enough (RMS 0.06)
        vad_parameters={"min_silence_duration_ms": 300},
        condition_on_previous_text=False,  # prevents repetition loops
        compression_ratio_threshold=2.0,  # discard looping hallucinations
        no_speech_threshold=0.6,
    )
    text = " ".join(s.text.strip() for s in segments).strip()

print(f"Язык: {info.language} (уверенность {info.language_probability:.0%})")
print(f"Услышал: «{text}»" if text else "Услышал: [тишина]")

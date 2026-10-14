"""Local speech-to-text with faster-whisper (open weights, runs offline)."""
from __future__ import annotations

import os
import time
from functools import lru_cache

WHISPER_SIZE = os.environ.get("UDHAAR_WHISPER", "small")
LANG = os.environ.get("UDHAAR_LANG") or None  # None = auto-detect; "mr" / "hi" to force

# Biases Whisper toward the words a kirana counter actually uses.
HINT = ("Patil kaku, don kilo sakhar ani ek litre tel udhaar. Sharma ji ne 500 jama kiye. "
        "tandul, toor dal, kanda, batata, doodh, atta, maggi, sabun, udhaar, khata, jama.")


@lru_cache(maxsize=1)
def _model():
    from faster_whisper import WhisperModel
    try:
        return WhisperModel(WHISPER_SIZE, device="cuda", compute_type="int8_float16")
    except Exception:
        return WhisperModel(WHISPER_SIZE, device="cpu", compute_type="int8")


def transcribe(path: str) -> dict:
    t0 = time.perf_counter()
    segs, info = _model().transcribe(path, language=LANG, initial_prompt=HINT,
                                     vad_filter=True, beam_size=5)
    text = " ".join(s.text.strip() for s in segs).strip()
    return {"text": text, "language": info.language,
            "ms": round((time.perf_counter() - t0) * 1000)}

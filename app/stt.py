"""Local speech-to-text with faster-whisper (open weights, runs offline).

GPU first, CPU as a fallback. On Windows the GPU path often loads fine and then fails on
the first transcription (missing cuBLAS / cuDNN DLLs), so the fallback also covers that.
Force a device with UDHAAR_STT_DEVICE=cpu or cuda.
"""
from __future__ import annotations

import os
import time

WHISPER_SIZE = os.environ.get("UDHAAR_WHISPER", "small")
LANG = os.environ.get("UDHAAR_LANG") or None  # None = auto-detect; "mr" / "hi" / "es" ... to force
DEVICE = os.environ.get("UDHAAR_STT_DEVICE", "auto")

# Biases Whisper toward the words a corner-shop counter actually uses.
HINT = ("Patil kaku, don kilo sakhar ani ek litre tel udhaar. Sharma ji ne 500 jama kiye. "
        "tandul, toor dal, kanda, batata, doodh, atta, maggi, sabun, udhaar, khata, jama. "
        "Doña Rosa, fiado. Aling Nena, utang. Bu Sri, hutang, 50 ribu.")

_models: dict[str, object] = {}
_bad_gpu = False
_use_vad = os.environ.get("UDHAAR_VAD", "1") != "0"   # silence trimming; needs onnxruntime


def _model(device: str):
    if device not in _models:
        from faster_whisper import WhisperModel
        if device == "cuda":
            _models[device] = WhisperModel(WHISPER_SIZE, device="cuda", compute_type="int8_float16")
        else:
            _models[device] = WhisperModel(WHISPER_SIZE, device="cpu", compute_type="int8")
    return _models[device]


def _load(path: str):
    """WAV from the browser is read with the standard library, so faster-whisper never needs
    PyAV to decode it. Anything else (e.g. an uploaded phone recording) goes to PyAV."""
    import wave
    import numpy as np
    try:
        with wave.open(path, "rb") as w:
            if w.getsampwidth() != 2:
                return path
            sr, ch, raw = w.getframerate(), w.getnchannels(), w.readframes(w.getnframes())
    except (wave.Error, EOFError):
        return path
    a = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if ch > 1:
        a = a.reshape(-1, ch).mean(axis=1)
    if sr != 16000:  # linear resample
        a = np.interp(np.linspace(0, len(a) - 1, int(len(a) * 16000 / sr)), np.arange(len(a)), a).astype(np.float32)
    return a


def _run(device: str, path: str):
    global _use_vad
    audio = _load(path)
    try:
        segs, info = _model(device).transcribe(audio, language=LANG, initial_prompt=HINT, vad_filter=_use_vad, beam_size=5)
        text = " ".join(s.text.strip() for s in segs).strip()   # segments are lazy: errors surface here
    except Exception as e:
        if not (_use_vad and ("onnxruntime" in str(e).lower() or "vad" in str(e).lower())):
            raise
        # The VAD only trims silence. If onnxruntime can't load on this machine, Whisper works fine without it.
        print(f"[udhaar] VAD unavailable ({e}); transcribing without it")
        _use_vad = False
        segs, info = _model(device).transcribe(audio, language=LANG, initial_prompt=HINT, vad_filter=False, beam_size=5)
        text = " ".join(s.text.strip() for s in segs).strip()
    return text, info.language


def _gpu_problem(e: Exception) -> bool:
    m = str(e).lower()
    return any(k in m for k in ("cuda", "cublas", "cudnn", ".dll", "gpu", "device", "out of memory"))


def transcribe(path: str) -> dict:
    global _bad_gpu
    t0 = time.perf_counter()
    order = [DEVICE] if DEVICE in ("cpu", "cuda") else (["cpu"] if _bad_gpu else ["cuda", "cpu"])
    last = None
    for device in order:
        try:
            text, lang = _run(device, path)
            return {"text": text, "language": lang, "device": device,
                    "ms": round((time.perf_counter() - t0) * 1000)}
        except Exception as e:  # e.g. "Library cublas64_12.dll is not found"
            last = e
            if device == "cuda" and not _gpu_problem(e):
                break                                   # not a GPU issue: the CPU would fail the same way
            if device == "cuda":
                _bad_gpu = True
                _models.pop("cuda", None)
                print(f"[udhaar] Whisper on GPU failed ({e!r}); using CPU from now on")
    raise RuntimeError(f"speech-to-text failed: {last}")

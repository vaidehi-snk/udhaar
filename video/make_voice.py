"""Render the narration with Kokoro (open-weights TTS, runs offline on CPU).

    pip install kokoro-onnx soundfile
    # model files (one-time, ~120 MB) from github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0
    python video/make_voice.py --models path/to/folder --voice af_heart

Prefer your own voice? Record each line as video/voice/<scene>.wav (any sample rate,
mono or stereo) and skip this script. record.py uses whatever is in that folder.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
from script import SCENES  # noqa: E402

OUT = Path(__file__).resolve().parent / "voice"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default=".", help="folder with kokoro-v1.0.int8.onnx and voices-v1.0.bin")
    ap.add_argument("--voice", default="af_heart")
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--only", nargs="*", help="re-render only these scenes")
    a = ap.parse_args()
    from kokoro_onnx import Kokoro
    m = Path(a.models)
    k = Kokoro(str(m / "kokoro-v1.0.int8.onnx"), str(m / "voices-v1.0.bin"))
    OUT.mkdir(exist_ok=True)
    for name, text in SCENES:
        if a.only and name not in a.only:
            continue
        audio, sr = k.create(text, voice=a.voice, speed=a.speed, lang="en-us")
        audio = np.asarray(audio, dtype=np.float32)
        peak = float(np.max(np.abs(audio))) or 1.0
        audio = audio / peak * 0.89                      # even loudness across lines
        sf.write(OUT / f"{name}.wav", audio, sr)
        print(f"{name:10} {len(audio) / sr:5.1f}s")


if __name__ == "__main__":
    main()

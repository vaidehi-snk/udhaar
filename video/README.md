# Demo video

`record.py` films the real app, driven like a person would use it, and mixes in the narration. It runs its own copy of Udhaar on a throwaway database with the sample shop, so your real khata is never touched.

## Record the final version (on your laptop, with Gemma running)

```powershell
cd E:\OneDrive\Desktop\udhaar
.venv\Scripts\activate
pip install playwright soundfile
playwright install chromium
winget install Gyan.FFmpeg          # then close and reopen the terminal
ollama serve                        # if Ollama isn't already running
$env:TABPFN_TOKEN="your-key"        # if this terminal doesn't have it yet
python video/record.py
```

This takes about 3–5 minutes and writes `video/udhaar-demo.mp4` (1920×1080, about 95 seconds). With Ollama up, the video shows Gemma actually checking each entry and actually writing the Filipino reminder, and TabPFN-3.5 scoring the risk.

## Change the words

Edit `video/script.py`. Each scene waits for its line to finish, so the video re-times itself.

- **Kokoro voice (open-weights TTS):** run `pip install kokoro-onnx`, then download `kokoro-v1.0.int8.onnx` and `voices-v1.0.bin` from github.com/thewh1teagle/kokoro-onnx/releases (tag `model-files-v1.0`). Then run `python video/make_voice.py --models <that folder>`. Other voices to try: `af_bella`, `bf_emma`, `af_nicole`.
- **Your own voice (most "real"):** record each line on your phone and save it as `video/voice/<scene>.wav`, using the scene names from `script.py`. No other change is needed.

## Add your shopkeeper clip

Put it after the end card in any editor (CapCut or Clipchamp are fine), or send it to me and I'll add an intro or outro segment for it.

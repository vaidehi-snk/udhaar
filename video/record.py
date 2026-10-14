"""Record the Udhaar demo video: the real app, driven like a person would, filmed frame by frame.

    pip install playwright soundfile && playwright install chromium
    # ffmpeg must be on PATH (Windows: winget install Gyan.FFmpeg)
    python video/record.py                 # -> video/udhaar-demo.mp4

It starts its own copy of the app on a throwaway database seeded with the sample shop,
so your real khata is never touched. Run it with Ollama up (and TABPFN_TOKEN set) and
every Gemma / TabPFN moment in the video is the real model running on this laptop.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import functools
import http.server
import os
import shutil
import socketserver
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

import soundfile as sf

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from script import CAPTIONS, SCENES  # noqa: E402

VOICE = dict(SCENES)


# ------------------------------------------------------------------ helpers
def wait_url(url, timeout=120):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            urllib.request.urlopen(url, timeout=5).read()
            return
        except Exception:
            time.sleep(0.5)
    raise SystemExit(f"app did not start at {url}")


def get(url, timeout=300, data=None):
    req = urllib.request.Request(url, data=data, headers={"content-type": "application/json"} if data else {})
    return urllib.request.urlopen(req, timeout=timeout).read()


def serve_dir(path: Path, port: int):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(path))
    handler.log_message = lambda *a: None
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", port), handler)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


CURSOR_CSS = """
#vcur{position:fixed;left:0;top:0;z-index:2147483647;width:30px;height:30px;pointer-events:none;
  transform:translate(720px,700px);transition:transform .75s cubic-bezier(.2,.8,.2,1);filter:drop-shadow(0 6px 10px #0009)}
#vcur svg{width:30px;height:30px}
.vrip{position:fixed;z-index:2147483646;width:14px;height:14px;margin:-7px 0 0 -7px;border-radius:50%;pointer-events:none;
  border:2px solid #F7C35F;animation:vrip .6s ease-out forwards}
@keyframes vrip{to{transform:scale(4);opacity:0}}
"""
CURSOR_JS = """
(() => {
  const c = document.createElement('div'); c.id = 'vcur';
  c.innerHTML = '<svg viewBox="0 0 24 24"><path d="M4 2l15 9-6.5 1.6L9 19z" fill="#fff" stroke="#0B0D12" stroke-width="1.4" stroke-linejoin="round"/></svg>';
  document.body.appendChild(c);
  window.__cur = {
    to(x, y, ms) { c.style.transitionDuration = (ms || 750) + 'ms'; c.style.transform = `translate(${x - 4}px, ${y - 2}px)`; },
    tap(x, y) { const r = document.createElement('div'); r.className = 'vrip'; r.style.left = x + 'px'; r.style.top = y + 'px';
      document.body.appendChild(r); setTimeout(() => r.remove(), 700); },
  };
})();
"""


class Director:
    def __init__(self, page, app, stage_origin):
        self.page, self.app, self.o = page, app, stage_origin
        self.starts: dict[str, float] = {}

    async def stage(self, js, *args):
        return await self.page.evaluate(f"(a) => stage.{js}(...a)", list(args))

    async def center(self, sel):
        r = await self.app.locator(sel).first.evaluate(
            "e => { const r = e.getBoundingClientRect(); return {x: r.x + r.width / 2, y: r.y + r.height / 2} }")
        return r["x"], r["y"]

    async def look(self, sel, scale, ms=1400, dy=0):
        x, y = await self.center(sel)
        await self.stage("cam", self.o["x"] + x, self.o["y"] + y + dy, scale, ms)

    async def reset(self, ms=1200):
        await self.stage("reset", ms)

    async def point(self, sel, ms=520):
        x, y = await self.center(sel)
        await self.app.evaluate("([x, y, ms]) => __cur.to(x, y, ms)", [x, y, ms])
        await asyncio.sleep(ms / 1000 + 0.05)
        return x, y

    async def click(self, sel):
        x, y = await self.point(sel)
        await self.app.evaluate("([x, y]) => __cur.tap(x, y)", [x, y])
        await self.app.locator(sel).first.click()
        await asyncio.sleep(0.15)

    async def type(self, text, delay=42):
        """Types in the page itself (smooth, steady rhythm), then submits like pressing Enter."""
        await self.click("#q")
        await self.app.evaluate("""([t, d]) => new Promise(res => {
            const q = document.querySelector('#q'); q.focus(); q.value = ''; let i = 0;
            const tick = () => { q.value = t.slice(0, ++i); q.dispatchEvent(new Event('input', {bubbles: true}));
              if (i < t.length) setTimeout(tick, d * (0.6 + Math.random() * 0.8)); else res(); };
            tick(); })""", [text, delay])
        await asyncio.sleep(0.3)
        await self.app.locator("#q").press("Enter")

    async def scroll(self, sel, offset=0):
        await self.app.locator(sel).first.evaluate(
            "(e, off) => window.scrollTo({top: e.getBoundingClientRect().top + scrollY - off, behavior: 'smooth'})", offset)
        await asyncio.sleep(0.7)

    async def scene(self, name, actions, tail=0.7, cap=True):
        dur = sf.info(str(HERE / "voice" / f"{name}.wav")).duration
        self.starts[name] = time.time()
        await self.stage("cap", CAPTIONS.get(name, "") if cap else "")
        await asyncio.gather(actions(), asyncio.sleep(dur + tail))
        took = time.time() - self.starts[name]
        print(f"  {name:9} voice {dur:4.1f}s  scene {took:4.1f}s" + ("   <- actions ran long" if took > dur + tail + 0.3 else ""))


async def film(d: Director, app):
    s = d.stage

    async def title():
        await s("scene", "title")
        for i, at in enumerate([0.15, 1.75, 3.45, 5.25]):
            await asyncio.sleep(at - (0 if i == 0 else [0.15, 1.75, 3.45, 5.25][i - 1]))
            await s("title", i)
    await d.scene("title", title, cap=False)

    async def notebook():
        await s("scene", "notebook")
        for n in range(1, 8):
            await asyncio.sleep(0.95)
            await s("notebook", n)
    await d.scene("notebook", notebook)

    async def intro():
        await s("cam", 960, 540, 0.86, 1)
        await asyncio.sleep(0.05)
        await s("scene", "none")
        await s("tag", "Recorded live in the app · sample shop data")
        await s("cam", 960, 540, 1.0, 3200)
    await d.scene("intro", intro)

    async def entry():
        await d.look("#cmdWrap", 1.5, 1100)
        await asyncio.sleep(0.3)
        await d.type("Patil kaku, don kilo sakhar, 92 udhaar", delay=34)
        await app.wait_for_selector("#reply .reply")
        await d.look("#reply", 1.4, 1100)
    await d.scene("entry", entry, tail=1.0)

    async def global_():
        await d.look("#cmdWrap", 1.35, 900)
        await d.type("Doña Rosa, dos kilos de azúcar y un aceite, apúntalo, 96 pesos", delay=20)
        await asyncio.sleep(0.9)
        await d.type("Aling Nena, isang kilong bigas at dalawang itlog, 85 utang", delay=20)
        await asyncio.sleep(0.8)
        await d.reset(900)
        await d.scroll("#recent", 260)
        await d.look("#recent", 1.3, 1200)
    await d.scene("global", global_, tail=1.0)

    async def slip():
        await d.look("#cmdWrap", 1.4, 900)
        await d.type("Patil kaku, don kilo sakhar, 920 udhaar", delay=30)
        await app.wait_for_selector("#reply .price.odd", timeout=30000)
        await d.look("#reply", 1.35, 1000)
        await asyncio.sleep(0.9)
        await d.click("#pfix")
        await asyncio.sleep(0.5)
    await d.scene("slip", slip, tail=0.8)

    async def question():
        await d.reset(800)
        await app.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
        await asyncio.sleep(0.8)
        await d.look("#cmdWrap", 1.4, 1000)
        await d.type("Who owes the most?")
        await asyncio.sleep(0.6)
        await d.look("#reply", 1.35, 1100)
    await d.scene("question", question)

    async def agent():
        await d.look("#cmdWrap", 1.4, 900)
        await d.type("How much more udhaar can I give Shinde Mama?", delay=30)
        await app.wait_for_selector("#reply .ladder", timeout=30000)
        await d.look("#reply", 1.25, 1000)
        await asyncio.sleep(0.6)
        await d.click("#reply details.trace summary")
        await asyncio.sleep(0.4)
        await d.look("#reply", 1.3, 900, dy=60)
    await d.scene("agent", agent, tail=0.8)

    async def briefing():
        await d.reset(900)
        await d.scroll("#kpis", 30)
        await d.look("#brief", 1.12, 1500, dy=-90)
    await d.scene("briefing", briefing)

    async def risk():
        await d.reset(800)
        await app.evaluate("window.scrollTo({top: 0})")
        await d.click('nav.tabs button[data-view="customers"]')
        await app.wait_for_selector("#detail .risk")
        await s("cap", CAPTIONS["risk"])
        await asyncio.sleep(0.3)
        await d.look("#detail .risk", 1.45, 1100)
    await d.scene("risk", risk, tail=0.4, cap=False)

    async def forecast():
        await d.reset(800)
        await d.click('nav.tabs button[data-view="forecast"]')
        await app.wait_for_selector("#fcBody tr")
        await s("cap", CAPTIONS["forecast"])
        await d.look(".fc-grid", 1.12, 1200, dy=-60)
        await asyncio.sleep(0.8)
        await d.click('#fcBody tr[data-item="sugar"]')
    await d.scene("forecast", forecast, cap=False)

    async def reminder():
        await d.reset(800)
        await d.click('nav.tabs button[data-view="customers"]')
        await d.click("#search")
        await app.evaluate("""() => new Promise(res => { const s = document.querySelector('#search'); let i = 0, t = 'Aling';
            const tick = () => { s.value = t.slice(0, ++i); s.dispatchEvent(new Event('input')); i < t.length ? setTimeout(tick, 70) : res(); }; tick(); })""")
        await asyncio.sleep(0.4)
        await d.click("#people [data-id]")
        await app.wait_for_selector("#remBtn")
        await d.click("#remBtn")
        await app.wait_for_function("document.querySelector('#dlgText').value.length > 30", timeout=45000)
        await s("cap", CAPTIONS["reminder"])
        await d.look("#dlg", 1.45, 1100)
    await d.scene("reminder", reminder, tail=2.4, cap=False)

    async def hood():
        await d.click("#dlgClose")
        await d.reset(800)
        await d.click('nav.tabs button[data-view="hood"]')
        await app.wait_for_selector("#steps .step")
        await s("cap", CAPTIONS["hood"])
        await d.look("#steps", 1.12, 1200)
        await asyncio.sleep(2.0)
        await d.reset(900)
        await d.scroll(".priv", 40)
        await d.look(".priv", 1.12, 1300)
    await d.scene("hood", hood, cap=False)

    async def end():
        await s("cap", "")
        await s("tag", "")
        await s("scene", "end")
        await asyncio.sleep(0.3)
        await s("end", True)
    await d.scene("end", end, tail=2.6, cap=False)


async def record(app_url, stage_url, frames_dir: Path):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1920, "height": 1080})
        await page.goto(stage_url)
        app = None
        for _ in range(100):
            app = next((f for f in page.frames if f.url.startswith(app_url)), None)
            if app:
                break
            await asyncio.sleep(0.1)
        await app.wait_for_selector("#kpis .kpi:not(.skel-k)", timeout=300000)
        await app.wait_for_selector("#brief .card:not(.skel-k)", timeout=300000)
        await app.add_style_tag(content=CURSOR_CSS)
        await app.evaluate(CURSOR_JS)
        await page.evaluate("document.fonts.ready")
        await asyncio.sleep(1.0)
        origin = await page.evaluate("stage.origin()")
        await page.evaluate("stage.scene('title')")
        await asyncio.sleep(0.5)

        frames: list[tuple[float, Path]] = []
        cdp = await page.context.new_cdp_session(page)

        def on_frame(ev):
            ts = ev["metadata"]["timestamp"]
            path = frames_dir / f"{len(frames):06d}.jpg"
            path.write_bytes(base64.b64decode(ev["data"]))
            frames.append((ts, path))
            asyncio.ensure_future(cdp.send("Page.screencastFrameAck", {"sessionId": ev["sessionId"]}))

        cdp.on("Page.screencastFrame", on_frame)
        await cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 86, "maxWidth": 1920, "maxHeight": 1080})
        await asyncio.sleep(0.4)
        d = Director(page, app, origin)
        t_begin = time.time()
        await film(d, app)
        t_end = time.time()
        await cdp.send("Page.stopScreencast")
        await browser.close()
    return frames, d.starts, t_begin, t_end


def assemble(frames, starts, t_end, out: Path, work: Path):
    t0 = frames[0][0]
    lst = work / "frames.txt"
    with lst.open("w") as f:
        for i, (ts, path) in enumerate(frames):
            nxt = frames[i + 1][0] if i + 1 < len(frames) else t_end
            f.write(f"file '{path.as_posix()}'\nduration {max(nxt - ts, 0.001):.4f}\n")
        f.write(f"file '{frames[-1][1].as_posix()}'\n")
    silent = work / "video.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-preset", "medium", "-crf", "18", str(silent)], check=True)
    inputs, filters = [], []
    for k, (name, _) in enumerate(SCENES):
        inputs += ["-i", str(HERE / "voice" / f"{name}.wav")]
        delay = max(0, int((starts[name] - t0) * 1000))
        filters.append(f"[{k + 1}:a]aresample=48000,pan=stereo|c0=c0|c1=c0,adelay={delay}|{delay}[v{k}]")
    mix = "".join(f"[v{k}]" for k in range(len(SCENES)))
    filt = ";".join(filters) + f";{mix}amix=inputs={len(SCENES)}:normalize=0,alimiter=limit=0.95,apad[a]"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent), *inputs, "-filter_complex", filt,
                    "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(out)], check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8077)
    ap.add_argument("--out", default=str(HERE / "udhaar-demo.mp4"))
    ap.add_argument("--keep", action="store_true", help="keep the frame images")
    a = ap.parse_args()
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg not found on PATH (Windows: winget install Gyan.FFmpeg, then open a new terminal)")
    missing = [n for n, _ in SCENES if not (HERE / "voice" / f"{n}.wav").exists()]
    if missing:
        raise SystemExit(f"missing voice files: {missing}. Run video/make_voice.py or record your own.")

    work = Path(tempfile.mkdtemp(prefix="udhaar-video-"))
    frames_dir = work / "frames"
    frames_dir.mkdir()
    env = os.environ | {"UDHAAR_DB": str(work / "video.db")}
    print("seeding the sample shop…")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "make_demo_data.py")], env=env, cwd=ROOT, check=True)
    app_url = f"http://127.0.0.1:{a.port}"
    srv = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(a.port), "--log-level", "warning"],
                           env=env, cwd=ROOT)
    try:
        wait_url(app_url + "/api/health")
        print("warming up models (TabPFN forecast, Gemma)… this can take a minute")
        get(app_url + "/api/insights")
        try:  # loads Gemma into memory and caches the reminder the video will show
            get(app_url + "/api/reminder", data=b'{"customer":"Aling Nena","due":85,"language":"filipino"}', timeout=180)
        except Exception:
            pass
        stage_html = (HERE / "stage.html").read_text(encoding="utf-8").replace("__APP__", app_url)
        (HERE / "_stage.html").write_text(stage_html, encoding="utf-8")
        static = serve_dir(HERE, a.port + 1)
        print("recording…")
        frames, starts, _, t_end = asyncio.run(record(app_url, f"http://127.0.0.1:{a.port + 1}/_stage.html", frames_dir))
        static.shutdown()
        print(f"{len(frames)} frames; assembling…")
        assemble(frames, starts, t_end, Path(a.out), work)
        print("done:", a.out)
    finally:
        srv.terminate()
        (HERE / "_stage.html").unlink(missing_ok=True)
        if not a.keep:
            shutil.rmtree(work, ignore_errors=True)
        else:
            print("frames kept in", work)


if __name__ == "__main__":
    main()

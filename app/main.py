"""Udhaar — an offline voice ledger for kirana shops.

Run:  uvicorn app.main:app --host 0.0.0.0 --port 8000
Then open http://localhost:8000 (or the laptop's LAN IP from the shop's phone).
"""
from __future__ import annotations

import os
import tempfile
import threading
import time
import uuid
from pathlib import Path

import httpx
import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import assistant, db, parser, predict, tracing

ROOT = Path(__file__).resolve().parent.parent
DEMO = os.environ.get("UDHAAR_DEMO") == "1"  # hosted demo: sample shop, no microphone pipeline
tracing.init()   # optional: Sentry agent traces when SENTRY_DSN is set
app = FastAPI(title="Udhaar")
_cache: dict = {"key": None, "data": None}


def _warm_gemma():
    """Load Gemma into memory at startup, so the first entry or question isn't a 15 s cold start."""
    try:
        httpx.post(f"{parser.OLLAMA_URL}/api/generate", timeout=120,
                   json={"model": parser.MODEL, "prompt": "ok", "stream": False, "keep_alive": "30m",
                         "options": {"num_predict": 1, "num_ctx": parser.NUM_CTX}})
    except Exception:
        pass


@app.on_event("startup")
def _seed_demo():
    if not DEMO:
        threading.Thread(target=_warm_gemma, daemon=True).start()
    if DEMO:
        with db.connect() as con:
            empty = con.execute("SELECT COUNT(*) FROM entries").fetchone()[0] == 0
        if empty:
            from scripts import make_demo_data
            make_demo_data.main(wipe=False)


class TextIn(BaseModel):
    text: str
    save: bool = True


class AskIn(BaseModel):
    text: str
    lang: str = "en"


class EntryIn(BaseModel):
    parsed: dict
    raw_text: str = ""


class ReminderIn(BaseModel):
    customer: str
    due: float
    language: str = "marathi"


def _commit(parsed: dict, raw: str, source: str) -> list[int]:
    with db.connect() as con:
        return db.add_entries(con, parsed, raw, source)


@app.get("/api/health")
def health():
    try:
        tags = httpx.get(f"{parser.OLLAMA_URL}/api/tags", timeout=2).json()
        models = [m["name"] for m in tags.get("models", [])]
    except Exception:
        models = []
    stt_ok = True
    try:
        import faster_whisper  # noqa: F401
    except Exception:
        stt_ok = False
    return {"ollama": bool(models), "model": parser.MODEL, "model_ready": parser.MODEL in models,
            "whisper": stt_ok, "tabpfn": predict.engine_name(), "demo": DEMO, "currency": assistant.CUR,
            "shop": os.environ.get("UDHAAR_SHOP", "Shree Ganesh Kirana"), "city": os.environ.get("UDHAAR_CITY", "Aurangabad")}


@app.post("/api/text")
def from_text(body: TextIn):
    parsed = parser.parse(body.text)
    ids = _commit(parsed, body.text, "typed") if body.save else []
    return {"text": body.text, "parsed": parsed, "ids": ids}


_jobs: dict[str, dict] = {}


def _price_candidates(parsed: dict) -> list[tuple]:
    items = [i for i in (parsed.get("items") or []) if i.get("name") and i.get("qty")]
    if parsed.get("kind") == "payment" or not items:
        return []
    if len(parsed.get("items") or []) == 1:          # one item: the spoken total is its price
        i = items[0]
        return [(i["name"], float(i["qty"]), float(i.get("amount") or parsed.get("total") or 0))]
    return [(i["name"], float(i["qty"]), float(i["amount"])) for i in items if i.get("amount")]


def _check_price(parsed: dict, ids: list[int]) -> dict | None:
    """TabPFN sanity-checks the amount against what this shop usually charges."""
    cands = _price_candidates(parsed)
    if not cands:
        return None
    with db.connect() as con:
        df = pd.read_sql_query("SELECT * FROM entries", con)
    df = df[~df["id"].isin(ids)]
    last = None
    with tracing.span("gen_ai.execute_tool", "price_check", tool="price_check"):
        for c in cands:
            res = predict.price_check(df, *c)
            if res and res["odd"]:
                return res
            last = res or last
    return last


def _refine(job: str, text: str, ids: list[int], first: dict, source: str):
    """Background: Gemma re-reads the line. If it understood it differently, swap the entry."""
    try:
        with tracing.span("gen_ai.chat", "refine entry", model=parser.MODEL):
            better = parser.parse_with_gemma(text)
    except Exception:
        _jobs[job].update(status="done", changed=False, engine="rules")
        return
    same = {k: first.get(k) for k in ("kind", "customer", "items", "total")} == \
           {k: better.get(k) for k in ("kind", "customer", "items", "total")}
    if same:
        _jobs[job].update(status="done", changed=False, engine=parser.MODEL)
        return
    with db.connect() as con:
        rows = con.execute(f"SELECT ts FROM entries WHERE id IN ({','.join('?' * len(ids))})", ids).fetchall()
        if len(rows) != len(ids):  # shopkeeper already undid or edited it
            _jobs[job].update(status="done", changed=False, engine=parser.MODEL)
            return
        for i in ids:
            db.undo(con, i)
        new_ids = db.add_entries(con, better, text, source, ts=rows[0]["ts"])
    _cache["key"] = None
    try:
        check = _check_price(better, new_ids)
    except Exception:
        check = None
    _jobs[job].update(status="done", changed=True, engine=parser.MODEL, parsed=better, ids=new_ids, check=check)


def _after_write(job: str, text: str, ids: list[int], parsed: dict, source: str, refine: bool):
    """Background, so the counter never waits: (1) TabPFN price check, (2) Gemma re-read."""
    try:
        _jobs[job]["check"] = _check_price(parsed, ids)
    except Exception as e:
        print(f"[udhaar] price check skipped: {e!r}")
        _jobs[job]["check"] = None
    _jobs[job]["checked"] = True
    if refine:
        _refine(job, text, ids, parsed, source)
    else:
        _jobs[job].update(status="done", changed=False, engine="rules")


def _route(text: str, lang: str, source: str) -> dict:
    """One box for everything: questions get answered, statements get written.
    Entries are written instantly by the rules parser; Gemma checks them in the background,
    so the counter never waits on the model."""
    if assistant.is_question(text):
        return {"mode": "answer", "text": text, **assistant.answer(text, insights(), lang)}
    t0 = time.perf_counter()
    parsed = parser.parse_with_rules(text)
    parsed.update(_engine="rules", _ms=round((time.perf_counter() - t0) * 1000))
    ids = _commit(parsed, text, source)
    refine = DEMO is False and os.environ.get("UDHAAR_NO_REFINE") != "1"
    job = uuid.uuid4().hex[:12]
    _jobs[job] = {"status": "running", "refining": refine}
    threading.Thread(target=_after_write, args=(job, text, ids, parsed, source, refine), daemon=True).start()
    return {"mode": "entry", "text": text, "parsed": parsed, "ids": ids, "refine": job, "refining": refine}


@app.get("/api/refine/{job}")
def refine_status(job: str):
    return _jobs.get(job, {"status": "unknown"})


@app.post("/api/ask")
def ask(body: AskIn):
    with tracing.span("gen_ai.invoke_agent", "udhaar"):
        return _route(body.text.strip(), body.lang, "typed")


@app.get("/api/brief")
def brief(lang: str = "en"):
    return assistant.brief(insights(), lang)


@app.get("/api/order")
def order(lang: str = "en"):
    ins = insights()
    return {"plan": assistant.order_plan(ins), "text": assistant.order_message(ins, lang)}


@app.post("/api/voice")
async def from_voice(audio: UploadFile = File(...), save: bool = True, lang: str = "en"):
    from . import stt  # imported lazily so the app starts even without faster-whisper
    suffix = Path(audio.filename or "clip.wav").suffix or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
        f.write(await audio.read())
        path = f.name
    try:
        heard = stt.transcribe(path)
    except Exception as e:  # show the real reason in the app instead of a silent failure
        raise HTTPException(500, str(e)[:300])
    finally:
        os.unlink(path)
    if not heard["text"]:
        raise HTTPException(422, "Couldn't hear anything — try again closer to the mic.")
    return {**_route(heard["text"], lang, "voice"), "language": heard["language"], "stt_ms": heard["ms"]}


@app.post("/api/entries")
def save_entry(body: EntryIn):
    """Save a (possibly hand-corrected) parse."""
    return {"ids": _commit(parser.normalise(body.parsed), body.raw_text, "corrected")}


@app.delete("/api/entries/{entry_id}")
def delete_entry(entry_id: int):
    with db.connect() as con:
        db.undo(con, entry_id)
    return {"ok": True}


@app.get("/api/ledger")
def ledger():
    with db.connect() as con:
        bal = [b for b in db.balances(con) if b["due"] > 0]
        rec = db.recent(con, 60)
        today = con.execute("""SELECT
            COALESCE(SUM(CASE WHEN kind='sale' THEN amount END),0) AS cash,
            COALESCE(SUM(CASE WHEN kind='credit' THEN amount END),0) AS credit,
            COALESCE(SUM(CASE WHEN kind='payment' THEN amount END),0) AS collected
            FROM entries WHERE date(ts)=(SELECT date(MAX(ts)) FROM entries)""").fetchone()
    return {"balances": bal, "recent": rec, "total_due": round(sum(b["due"] for b in bal)),
            "today": dict(today)}


STALE_OK = float(os.environ.get("UDHAAR_INSIGHTS_TTL", "900"))  # seconds a forecast may lag the newest entries
_lock = threading.Lock()


def _compute(key):
    with db.connect() as con:
        df = pd.read_sql_query("SELECT * FROM entries", con)
        names = {r["id"]: r["name"] for r in con.execute("SELECT id,name FROM customers")}
    t0 = time.perf_counter()
    data = {"restock": predict.restock_forecast(df), "risk": predict.udhaar_risk(df, names)}
    data["ms"] = round((time.perf_counter() - t0) * 1000)
    _cache.update(key=key, data=data, at=time.time(), busy=False)
    return data


@app.get("/api/insights")
def insights(refresh: bool = False):
    """TabPFN forecasts and risk scores. One new entry barely moves a 13-month forecast, so
    a recent result is served instantly and recomputed in the background (one at a time).
    That keeps the counter fast and avoids a TabPFN API call per entry."""
    with db.connect() as con:
        key = tuple(con.execute("SELECT COUNT(*), MAX(id) FROM entries").fetchone())
    data = _cache.get("data")
    if data and not refresh:
        if _cache["key"] != key and time.time() - _cache.get("at", 0) < STALE_OK:
            with _lock:
                if not _cache.get("busy"):
                    _cache["busy"] = True
                    threading.Thread(target=_compute, args=(key,), daemon=True).start()
            return data
        if _cache["key"] == key:
            return data
    with _lock:
        return _compute(key)


@app.get("/api/customer/{cid}")
def customer(cid: int):
    with db.connect() as con:
        c = con.execute("SELECT * FROM customers WHERE id=?", (cid,)).fetchone()
        if not c:
            raise HTTPException(404, "No such customer")
        rows = [dict(r) for r in con.execute(
            "SELECT * FROM entries WHERE customer_id=? ORDER BY ts", (cid,))]
    bal, series = 0.0, []
    for r in rows:
        bal += r["amount"] if r["kind"] == "credit" else -r["amount"] if r["kind"] == "payment" else 0
        series.append({"ts": r["ts"], "balance": round(bal)})
    data = _cache["data"] or insights()  # a slightly stale score beats making the shopkeeper wait
    risk = next((x for x in (data["risk"].get("customers") or []) if x["customer"] == c["name"]), None)
    return {"id": cid, "name": c["name"], "due": round(bal), "series": series[-120:],
            "entries": list(reversed(rows))[:40], "risk": risk,
            "n_entries": len(rows), "credit_total": round(sum(r["amount"] for r in rows if r["kind"] == "credit")),
            "paid_total": round(sum(r["amount"] for r in rows if r["kind"] == "payment"))}


@app.get("/api/limit/{cid}")
def limit(cid: int, lang: str = "en"):
    """Credit-limit tool for one customer (the same tool the agent calls)."""
    with db.connect() as con:
        c = con.execute("SELECT name FROM customers WHERE id=?", (cid,)).fetchone()
    if not c:
        raise HTTPException(404, "No such customer")
    insights()
    with tracing.span("gen_ai.execute_tool", "credit_limit", tool="credit_limit"):
        r = assistant._run_step({"intent": "credit_limit", "customer": c["name"]}, c["name"], insights(), lang)
    return {k: r.get(k) for k in ("answer", "curve", "limit", "engine")}


@app.get("/api/summary")
def summary(weeks: int = 10):
    with db.connect() as con:
        df = pd.read_sql_query("SELECT ts, kind, amount FROM entries", con)
    if df.empty:
        return {"weeks": []}
    df["week"] = pd.to_datetime(df["ts"]).dt.to_period("W-SUN").dt.start_time
    g = df.pivot_table(index="week", columns="kind", values="amount", aggfunc="sum").fillna(0)
    last_day = pd.to_datetime(df["ts"]).max().normalize()
    if len(g) > 1 and g.index[-1] + pd.Timedelta(days=6) > last_day:  # drop the unfinished week
        g = g.iloc[:-1]
    g = g.tail(weeks)
    return {"weeks": [{"week": w.date().isoformat(), "sale": round(r.get("sale", 0)),
                       "credit": round(r.get("credit", 0)), "payment": round(r.get("payment", 0))}
                      for w, r in g.iterrows()]}


@app.get("/api/backtest")
def backtest():
    f = db.DB_PATH.parent / "backtest.json"
    if not f.exists():  # committed copy for the hosted demo
        f = ROOT / "static" / "backtest.json"
    if not f.exists():
        return {"available": False}
    import json
    return {"available": True, **json.loads(f.read_text())}


# Offline fallbacks, so a reminder is always one tap away even with the model off.
REMINDER_TEMPLATES = {
    "marathi": "नमस्कार {n}, आपल्या खात्यावर {c}{d} बाकी आहेत. सवडीने भरून टाका. धन्यवाद! 🙏",
    "hindi": "नमस्ते {n} जी, आपके खाते में {c}{d} बाकी हैं. जब सुविधा हो, चुका दीजिए. धन्यवाद! 🙏",
    "english": "Hello {n}, a gentle reminder that {c}{d} is pending on your account. Whenever convenient. Thank you! 🙏",
    "spanish": "Hola {n}, le recuerdo con cariño que tiene {c}{d} pendientes en su cuenta. Cuando pueda. ¡Gracias! 🙏",
    "filipino": "Magandang araw po, {n}! Paalala lang po na may {c}{d} pa po sa listahan ninyo. Salamat po! 🙏",
    "indonesian": "Halo {n}, sekadar mengingatkan ada {c}{d} yang belum dibayar di catatan warung. Terima kasih! 🙏",
}


_reminders: dict[tuple, dict] = {}


@app.post("/api/reminder")
def reminder(body: ReminderIn):
    """Gemma drafts a polite WhatsApp reminder the shopkeeper can send in one tap.
    Drafts are remembered for the session, so reopening the same reminder is instant."""
    lang = body.language.lower().replace("simple ", "")
    key = (body.customer, round(body.due), lang)
    if key in _reminders:
        return _reminders[key]
    due = f"{round(body.due):,}"
    prompt = (f"Write a short, warm WhatsApp message in {lang} (native script) from the owner of a small "
              f"neighbourhood grocery shop to a regular customer, {body.customer}, gently reminding them that "
              f"{assistant.CUR}{due} is still pending on their credit account. Respectful, never threatening, "
              f"2-3 lines, end with a thank you. Output only the message.")
    try:
        r = httpx.post(f"{parser.OLLAMA_URL}/api/generate", timeout=60, json={
            "model": parser.MODEL, "prompt": prompt, "stream": False,
            "options": {"temperature": 0.6, "num_ctx": parser.NUM_CTX, "num_predict": 200}, "keep_alive": "30m"})
        r.raise_for_status()
        out = {"text": r.json()["response"].strip(), "engine": parser.MODEL}
        _reminders[key] = out
        return out
    except Exception:
        tpl = REMINDER_TEMPLATES.get(lang, REMINDER_TEMPLATES["english"])
        return {"text": tpl.format(n=body.customer, c=assistant.CUR, d=due), "engine": "template"}


app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


@app.get("/")
def home():
    return FileResponse(ROOT / "static" / "landing.html")


@app.get("/app")
def index():
    return FileResponse(ROOT / "static" / "index.html")

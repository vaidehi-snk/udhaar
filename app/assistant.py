"""The shop's AI back-office: one input box that either writes an entry or answers a question.

Design rule: the language model decides WHAT is being asked; the numbers always come from
SQLite and TabPFN, never from the model. So an answer can be misunderstood, but not made up.
"""
from __future__ import annotations

import difflib
import json
import re
from datetime import date, datetime, timedelta

import httpx

from . import db, parser, predict, tracing
import os
import time

CUR = os.environ.get("UDHAAR_CURRENCY", "₹")

QUESTION_WORDS = {
    "kitna", "kitni", "kitne", "kiti", "kevdha", "kevdhe", "kaun", "kon", "kona", "konala", "konakade", "kuni",
    "kab", "kevha", "kya", "kay", "kaise", "how", "who", "what", "which", "when", "show", "list", "tell",
    "batao", "sang", "sanga", "dakhva", "owe", "owes", "total", "hisab", "hishob",
    "cuanto", "cuanta", "cuantos", "quien", "quienes", "que", "cual", "cuando", "dime", "muestrame",   # es
    "magkano", "sino", "ilan", "ano", "kailan", "pakita",                                            # fil
    "berapa", "siapa", "apa", "kapan", "tunjukkan", "lihat",                                         # id
}
INTENTS = ["customer_due", "customer_history", "top_due", "risky", "item_forecast", "item_sales",
           "order_plan", "sales_summary", "credit_limit", "what_if", "help"]
PERIODS = ["today", "yesterday", "week", "month"]

STEP = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": INTENTS},
        "customer": {"type": ["string", "null"]},
        "item": {"type": ["string", "null"]},
        "period": {"type": ["string", "null"], "enum": PERIODS + [None]},
        "amount": {"type": ["number", "null"]},
        "days": {"type": ["integer", "null"]},
    },
    "required": ["intent", "customer", "item", "period", "amount", "days"],
}
# The agent's plan: up to three tool calls. Gemma picks the tools; the tools compute the numbers.
Q_SCHEMA = {"type": "object", "properties": {"steps": {"type": "array", "items": STEP, "minItems": 1, "maxItems": 3}},
            "required": ["steps"]}
Q_SYSTEM = """You route questions from a small shopkeeper (Marathi, Hindi, English, Spanish, Filipino or Indonesian, often mixed) to one intent.
customer_due: how much a named person owes. customer_history: what a named person took or paid.
top_due: who owes the most. risky: who may not pay back. item_forecast: how much of an item will be needed / to order.
item_sales: how much of an item was sold. order_plan: what to order from the wholesaler.
sales_summary: cash, udhaar, collection totals for a period.
credit_limit: how much more udhaar can safely be given to a named person (or whether to give more at all).
what_if: how a named person's risk changes if they pay nothing for `days` days and/or take `amount` more on udhaar.
help: anything else.
Plan 1 to 3 steps. Use several steps only when the question really asks several things.
item in simple English (sakhar/azúcar/asukal/gula->sugar, tel/aceite/mantika/minyak->oil). period: today, yesterday, week or month.
Never answer the question yourself: only choose the steps. JSON only."""


# ---------------------------------------------------------------- routing
def _tokens(text: str) -> list[str]:
    return [parser._fold(t) for t in parser._TOKEN.findall(text.lower())]


_CRED = {parser._fold(w) for w in parser.CREDIT_WORDS}
_PAY = {parser._fold(w) for w in parser.PAYMENT_WORDS}


def is_question(text: str) -> bool:
    if "?" in text:
        return True
    toks = _tokens(text)
    if any(t in QUESTION_WORDS for t in toks):
        return True
    has_num = any(parser._numval(t) is not None or t in parser.NUM_WORDS for t in toks)
    has_signal = any(t in _CRED or t in _PAY or t in parser.GLOSSARY for t in toks)
    return not (has_num and has_signal)


_ITEM_WORDS = {**{v: v for v in parser.GLOSSARY.values()}, **parser.GLOSSARY, "dal": "toor dal", "egg": "eggs"}


def _item_in(text: str) -> str | None:
    t = " ".join(_tokens(text))
    for k in sorted(_ITEM_WORDS, key=len, reverse=True):
        if re.search(rf"\b{re.escape(k)}\b", t):
            return _ITEM_WORDS[k]
    return None


def _period_in(toks: list[str]) -> str | None:
    t = set(toks)
    if t & {"yesterday", "kal", "kaal", "ayer", "kahapon", "kemarin"}:
        return "yesterday"
    if t & {"week", "hafta", "hafte", "athavda", "aathavda", "athavdyat", "semana", "linggo", "minggu"}:
        return "week"
    if t & {"month", "mahina", "mahine", "mahinyat", "mes", "buwan", "bulan"}:
        return "month"
    if t & {"today", "aaj", "aj", "hoy", "ngayon", "hari", "ini"}:
        return "today"
    return None


IF_WORDS = {"if", "agar", "jar", "jari", "si", "kung", "kalau", "kalo", "suppose", "maan", "samjha"}
MORE_WORDS = {"more", "aur", "ajun", "aajun", "anakhi", "mas", "pa", "lagi", "tambah", "extra", "limit", "safe"}
GIVE_WORDS = {"give", "de", "du", "deu", "dyu", "dena", "deta", "du", "sakta", "sakte", "sakti", "fiar", "fio", "fiarle",
              "dar", "pautangin", "ipautang", "kasih", "beri", "kasbon", "credit", "udhaar", "udhar", "utang", "fiado",
              "hutang", "bon", "limit"}
DAY_WORDS = {"day": 1, "days": 1, "din": 1, "dinon": 1, "divas": 1, "dia": 1, "dias": 1, "araw": 1, "hari": 1,
             "week": 7, "weeks": 7, "hafte": 7, "hafta": 7, "athavde": 7, "athavda": 7, "aathavde": 7, "semana": 7,
             "semanas": 7, "linggo": 7, "minggu": 7, "month": 30, "months": 30, "mahina": 30, "mahine": 30,
             "mahinyat": 30, "mes": 30, "meses": 30, "buwan": 30, "bulan": 30}


def _scenario_in(toks: list[str]) -> tuple[int, float]:
    """'2 weeks' -> 14 days; any other number >= 10 is extra udhaar."""
    days, extra = 0, 0.0
    for i, t in enumerate(toks):
        n = parser._numval(t)
        n = n if n is not None else parser.NUM_WORDS.get(t)
        if t in DAY_WORDS and (i == 0 or (parser._numval(toks[i - 1]) is None and toks[i - 1] not in parser.NUM_WORDS)):
            days = max(days, DAY_WORDS[t] if DAY_WORDS[t] == 30 else 0)
        if n is None:
            continue
        nxt = toks[i + 1] if i + 1 < len(toks) else ""
        if nxt in DAY_WORDS:
            days = max(days, int(n * DAY_WORDS[nxt]))
        elif n >= 10:
            extra = max(extra, float(n))
    return days, extra


def route_with_rules(text: str) -> dict:
    toks = set(_tokens(text))
    item, period = _item_in(text), _period_in(list(toks))
    if toks & IF_WORDS:
        days, extra = _scenario_in(_tokens(text))
        if days or extra:
            return {"intent": "what_if", "customer": text, "item": None, "period": None, "amount": extra, "days": days}
    if toks & MORE_WORDS and toks & GIVE_WORDS and not item:
        return {"intent": "credit_limit", "customer": text, "item": None, "period": None, "amount": None, "days": None}
    who = {"who", "kaun", "kon", "konala", "kuni", "konakade", "quien", "quienes", "sino", "siapa"} & toks
    if who and toks & {"late", "risk", "dhoka", "nahi", "denge", "bharnar", "pay", "pays",
                       "no", "pagara", "pagaran", "hindi", "magbabayad", "tidak", "bayar", "telat"}:
        intent = "risky"
    elif who:
        intent = "top_due"
    elif toks & {"order", "mangva", "mangvaycha", "mangvayche", "wholesaler", "kharedi", "purchase",
                 "pedir", "pido", "surtir", "bibilhin", "kulakan", "belanja", "pesan"} and not item:
        intent = "order_plan"
    elif item and toks & {"sold", "becha", "beche", "bika", "vikla", "vikli", "sale", "vendi", "vendio", "naibenta", "terjual", "laku"}:
        intent = "item_sales"
    elif item:
        intent = "item_forecast"
    elif toks & {"sale", "sales", "vikri", "becha", "galla", "cash", "collection", "vasuli", "jama", "hisab", "hishob",
                 "ventas", "venta", "caja", "benta", "kita", "penjualan", "omzet"} or period:
        intent = "sales_summary"
    else:
        intent = "customer_due"  # resolved below; falls back to help if no customer found
    return {"intent": intent, "customer": text, "item": item, "period": period, "amount": None, "days": None}


def _shot(steps: list[dict]) -> str:
    base = {"customer": None, "item": None, "period": None, "amount": None, "days": None}
    return json.dumps({"steps": [base | st for st in steps]})


def plan_with_gemma(text: str) -> list[dict]:
    r = httpx.post(f"{parser.OLLAMA_URL}/api/chat", timeout=20, json={
        "model": parser.MODEL, "stream": False, "format": Q_SCHEMA, "options": parser.OPTS,
        "keep_alive": "30m",
        "messages": [{"role": "system", "content": Q_SYSTEM},
                     {"role": "user", "content": "Patil kaku kitna baki hai?"},
                     {"role": "assistant", "content": _shot([{"intent": "customer_due", "customer": "Patil Kaku"}])},
                     {"role": "user", "content": "pudhchya athavdyat kiti sakhar lagel"},
                     {"role": "assistant", "content": _shot([{"intent": "item_forecast", "item": "sugar", "period": "week"}])},
                     {"role": "user", "content": "Shinde mama is asking for more udhaar for Diwali, should I give it? how much does he owe?"},
                     {"role": "assistant", "content": _shot([{"intent": "customer_due", "customer": "Shinde Mama"},
                                                             {"intent": "credit_limit", "customer": "Shinde Mama"}])},
                     {"role": "user", "content": "what should I do before the festival"},
                     {"role": "assistant", "content": _shot([{"intent": "order_plan"}, {"intent": "risky"}])},
                     {"role": "user", "content": text}]})
    r.raise_for_status()
    steps = json.loads(r.json()["message"]["content"]).get("steps") or []
    return [st for st in steps if st.get("intent") in INTENTS][:3] or [{"intent": "help"}]


def resolve_customer(con, spoken: str | None) -> dict | None:
    """Match 'patil kaku' / 'Patil Kaku ne' / 'pätil' to a customer in the khata."""
    if not spoken:
        return None
    rows = [dict(r) for r in con.execute("SELECT id, name FROM customers")]
    if not rows:
        return None
    s = " ".join(_tokens(spoken))
    best, score = None, 0.0
    for r in rows:
        n = r["name"].lower()
        if n in s:
            return r
        parts = n.split()
        sc = max(difflib.SequenceMatcher(None, n, s).ratio(),
                 max((difflib.SequenceMatcher(None, n, " ".join(w)).ratio()
                      for w in zip(s.split(), s.split()[1:])), default=0),
                 0.9 if parts and parts[0] in s.split() and len(parts[0]) > 3 else 0)
        if sc > score:
            best, score = r, sc
    return best if score >= 0.72 else None


# ---------------------------------------------------------------- answers
def _period_range(con, period: str | None) -> tuple[str, str, str]:
    last = con.execute("SELECT date(MAX(ts)) FROM entries").fetchone()[0] or date.today().isoformat()
    end = datetime.fromisoformat(last).date()
    if period == "yesterday":
        d = end - timedelta(days=1); return d.isoformat(), d.isoformat(), "yesterday"
    if period == "week":
        return (end - timedelta(days=6)).isoformat(), end.isoformat(), "the last 7 days"
    if period == "month":
        return (end - timedelta(days=29)).isoformat(), end.isoformat(), "the last 30 days"
    return end.isoformat(), end.isoformat(), "today"


def _run_step(q: dict, text: str, insights: dict, lang: str) -> dict:
    """Execute one tool. Every number in the result comes from SQLite or TabPFN."""
    mr = lang == "mr"
    out = {"intent": q.get("intent"), "engine": "SQLite", "rows": [], "actions": []}
    with db.connect() as con:
        cust = resolve_customer(con, q.get("customer"))
        intent = q.get("intent")
        if cust and q.get("_rules") and intent in ("sales_summary", "help", "customer_due"):
            hist = {"liya", "ghetla", "ghetle", "history", "entries", "nondi", "kya", "kay"} & set(_tokens(text))
            intent = "customer_history" if hist else "customer_due"
        if intent in ("customer_due", "customer_history", "credit_limit", "what_if") and not cust:
            intent = "help"
        out["intent"] = intent
        out["_cust"] = cust["name"] if cust else None
        if intent in ("risky",):
            out["engine"] = insights.get("risk", {}).get("engine")
        elif intent in ("item_forecast", "order_plan"):
            out["engine"] = insights.get("restock", {}).get("engine")
        bal = {b["id"]: b for b in db.balances(con)}
        risk = {c["customer"]: c for c in (insights.get("risk", {}).get("customers") or [])}

        if intent == "customer_due":
            b = bal[cust["id"]]; r = risk.get(cust["name"])
            last = (b["last_payment"] or "")[:10]
            out["answer"] = (f"{cust['name']} यांच्याकडे {CUR}{b['due']:,.0f} बाकी आहेत." if mr else
                             f"{cust['name']} owes {CUR}{b['due']:,.0f}.") + (
                (f" शेवटचे पैसे {last} ला दिले." if mr else f" Last paid on {last}.") if last else "")
            if r:
                out["answer"] += (f" उशिरा भरण्याची शक्यता {round(r['risk']*100)}%." if mr else
                                  f" Chance of paying late: {round(r['risk']*100)}%.")
            out["customer_id"] = cust["id"]
            if b["due"] > 0:
                out["actions"].append({"type": "remind", "customer": cust["name"], "due": b["due"]})

        elif intent == "customer_history":
            rows = [dict(r) for r in con.execute(
                "SELECT ts, kind, item, qty, unit, amount FROM entries WHERE customer_id=? ORDER BY ts DESC LIMIT 8",
                (cust["id"],))]
            out["answer"] = f"{cust['name']} यांच्या शेवटच्या नोंदी:" if mr else f"Latest entries for {cust['name']}:"
            out["rows"] = [[r["ts"][:10], r["kind"], f"{r['qty'] or ''} {r['unit'] or ''} {r['item'] or ''}".strip(),
                            f"{CUR}{r['amount']:,.0f}"] for r in rows]
            out["customer_id"] = cust["id"]

        elif intent == "top_due":
            top = sorted((b for b in bal.values() if b["due"] > 0), key=lambda b: -b["due"])[:5]
            total = sum(b["due"] for b in bal.values() if b["due"] > 0)
            out["answer"] = (f"एकूण {CUR}{total:,.0f} बाकी. सर्वात जास्त:" if mr else
                             f"{CUR}{total:,.0f} is out on udhaar. Highest balances:")
            out["rows"] = [[b["name"], f"{CUR}{b['due']:,.0f}"] for b in top]

        elif intent == "risky":
            rk = [c for c in risk.values() if c["band"] != "ok"][:5]
            out["answer"] = ("हे ग्राहक उशिरा भरण्याची शक्यता आहे:" if mr else
                             "These customers are likely to pay late:") if rk else (
                "सध्या कोणीही धोकादायक नाही." if mr else "Nobody looks risky right now.")
            out["rows"] = [[c["customer"], f"{CUR}{c['due']:,.0f}", f"{round(c['risk']*100)}%"] for c in rk]
            if rk:
                out["actions"].append({"type": "remind", "customer": rk[0]["customer"], "due": rk[0]["due"]})

        elif intent in ("item_forecast", "order_plan"):
            items = insights.get("restock", {}).get("items") or []
            if intent == "item_forecast" and q.get("item"):
                it = next((i for i in items if i["item"] == parser.GLOSSARY.get(q["item"], q["item"])), None)
                if it:
                    wk = it["next_7d"]
                    out["answer"] = (f"पुढच्या ७ दिवसांत सुमारे {wk:.0f} {_unit(it['item'])} {it['item']} लागेल (नेहमी {it['normal_7d']:.0f})." if mr else
                                     f"About {wk:.0f} {_unit(it['item'])} of {it['item']} over the next 7 days (usually {it['normal_7d']:.0f}).")
                    if it.get("festival_14d") is not None:
                        out["answer"] += (f" सणाच्या दोन आठवड्यांत {it['festival_14d']:.0f} ({it['festival_change_pct']:+d}%)." if mr else
                                          f" In the 2 weeks before the festival: {it['festival_14d']:.0f} ({it['festival_change_pct']:+d}%).")
                else:
                    out["answer"] = "या मालाचा पुरेसा इतिहास नाही." if mr else "Not enough history for that item yet."
            else:
                plan = order_plan(insights)
                out["answer"] = "होलसेलरकडून हे जास्त मागवा:" if mr else "Order this extra from the wholesaler:"
                out["rows"] = [[p["item"], f"+{p['extra']} {p['unit']}"] for p in plan[:8]]
                out["actions"].append({"type": "order"})

        elif intent == "item_sales":
            item = parser.GLOSSARY.get(q.get("item") or "", q.get("item"))
            a, b_, label = _period_range(con, q.get("period") or "week")
            r = con.execute("""SELECT COALESCE(SUM(qty),0) q, COALESCE(SUM(amount),0) amt, MAX(unit) unit FROM entries
                               WHERE item=? AND kind IN ('sale','credit') AND date(ts) BETWEEN ? AND ?""", (item, a, b_)).fetchone()
            out["answer"] = (f"{label}: {r['q']:.1f} {r['unit'] or ''} {item}, {CUR}{r['amt']:,.0f}." if not mr else
                             f"{item}: {r['q']:.1f} {r['unit'] or ''} विकले, {CUR}{r['amt']:,.0f}.")

        elif intent == "sales_summary":
            a, b_, label = _period_range(con, q.get("period"))
            r = con.execute("""SELECT
                COALESCE(SUM(CASE WHEN kind='sale' THEN amount END),0) cash,
                COALESCE(SUM(CASE WHEN kind='credit' THEN amount END),0) credit,
                COALESCE(SUM(CASE WHEN kind='payment' THEN amount END),0) paid
                FROM entries WHERE date(ts) BETWEEN ? AND ?""", (a, b_)).fetchone()
            out["answer"] = (f"रोख {CUR}{r['cash']:,.0f}, उधार {CUR}{r['credit']:,.0f}, वसूल {CUR}{r['paid']:,.0f}." if mr else
                             f"{label.capitalize()}: {CUR}{r['cash']:,.0f} cash sales, {CUR}{r['credit']:,.0f} given on udhaar, {CUR}{r['paid']:,.0f} collected.")

        elif intent == "credit_limit":
            L = predict.credit_limit(cust["name"])
            out["engine"] = (L or {}).get("engine")
            if not L:
                out["answer"] = (f"{cust['name']} यांच्याकडे सध्या उधार नाही." if mr else f"{cust['name']} has no open udhaar to judge from.")
            else:
                n, p = L["customer"], round(L["risk_now"] * 100)
                if L["verdict"] == "collect":
                    out["answer"] = (f"आधी वसूल करा. {n} यांच्याकडे {CUR}{L['due']:,} बाकी, उशिरा भरण्याची शक्यता {p}%. काही भरेपर्यंत अजून उधार नको." if mr else
                                     f"Collect first. {n} owes {CUR}{L['due']:,} and is {p}% likely to pay late. Hold more udhaar until they pay something.")
                    out["actions"].append({"type": "remind", "customer": n, "due": L["due"]})
                elif L["verdict"] == "full":
                    out["answer"] = (f"सध्या नको. {n} यांच्याकडे {CUR}{L['due']:,} बाकी — त्यांनी एका महिन्यात भरलेल्या सर्वात जास्त रकमेइतके ({CUR}{L['capacity']:,})." if mr else
                                     f"Not right now. {n} owes {CUR}{L['due']:,}, about the most they have ever paid back in a month ({CUR}{L['capacity']:,}).")
                else:
                    why = ((f"त्यापलीकडे उशिरा भरण्याची शक्यता {round(L['line']*100)}% च्या वर जाते." if mr else
                            f"Beyond that, their chance of paying late goes over {round(L['line']*100)}%.") if L["binding"] == "risk" else
                           (f"त्यांनी एका महिन्यात जास्तीत जास्त {CUR}{L['capacity']:,} भरले आहेत." if mr else
                            f"The most they have paid back in a month is {CUR}{L['capacity']:,}."))
                    head = ((f"थोडेच: {n} यांना अजून {CUR}{L['limit']:,} पर्यंत. ते आधीच लक्ष ठेवण्याच्या यादीत आहेत ({p}%)." if mr else
                             f"Only a little: up to {CUR}{L['limit']:,} more for {n}. They are already on the watch list ({p}% chance of paying late).")
                            if L["verdict"] == "small" else
                            (f"{n} यांना अजून {CUR}{L['limit']:,} पर्यंत उधार देणे सुरक्षित आहे. आत्ता {CUR}{L['due']:,} बाकी." if mr else
                             f"Safe to give {n} up to {CUR}{L['limit']:,} more. They owe {CUR}{L['due']:,} now."))
                    out["answer"] = f"{head} {why}"
                pts = L["curve"][:: max(1, len(L["curve"]) // 5)][:5]
                out["rows"] = [[(("आत्ता" if mr else "As now") if not g else (f"+{CUR}{g:,} अजून" if mr else f"+{CUR}{g:,} more")),
                                 f"{round(v*100)}%"] for g, v in pts]
                out["head"] = ["Extra udhaar", "Chance of paying late"] if not mr else ["अजून उधार", "उशिरा भरण्याची शक्यता"]
                out["curve"] = L["curve"]
                out["limit"] = L["limit"]
            out["customer_id"] = cust["id"]

        elif intent == "what_if":
            days, extra = int(q.get("days") or 0), float(q.get("amount") or 0)
            W = predict.what_if(cust["name"], extra, days)
            out["engine"] = (W or {}).get("engine")
            if not W:
                out["answer"] = (f"{cust['name']} यांच्याकडे सध्या उधार नाही." if mr else f"{cust['name']} has no open udhaar right now.")
            else:
                n, a_, b2 = W["customer"], round(W["now"] * 100), round(W["then"] * 100)
                cond = (f"{days} दिवस काहीच भरले नाही" if days else "") + (" आणि " if days and extra else "") + (f"अजून {CUR}{extra:,.0f} घेतले" if extra else "")
                cond_en = (f"pays nothing for {days} days" if days else "") + (" and " if days and extra else "") + (f"takes {CUR}{extra:,.0f} more" if extra else "")
                if b2 == a_:
                    out["answer"] = (f"{n} यांनी {cond} तरी उशिरा भरण्याची शक्यता {a_}% च राहील." if mr else
                                     f"If {n} {cond_en}, their chance of paying late stays at {a_}%.")
                else:
                    out["answer"] = (f"{n} यांनी {cond} तर उशिरा भरण्याची शक्यता {a_}% वरून {b2}% होईल." if mr else
                                     f"If {n} {cond_en}, their chance of paying late goes from {a_}% to {b2}%.")
                if W["then"] >= predict.BAND_WATCH:
                    out["actions"].append({"type": "remind", "customer": n, "due": W["due"]})
            out["customer_id"] = cust["id"]

        else:
            out["answer"] = ("मी नोंद लिहू शकतो किंवा विचारू शकता: \"Patil kaku kiti baki?\", \"kon jast baki?\", \"pudhchya athavdyat kiti sakhar?\"" if mr else
                             "I can write an entry, or answer things like “how much does Patil Kaku owe?”, “who owes the most?”, “how much sugar next week?”.")
    return out


ADVICE_WORDS = {"should", "worth", "suggest", "advice", "advise", "plan", "karu", "karun", "karaycha", "chahiye",
                "deu", "dyava", "dyave", "debo", "deberia", "conviene", "dapat", "sebaiknya", "harus"}
JOIN_WORDS = {"and", "also", "ani", "aani", "aur", "va", "y", "tambien", "at", "saka", "dan", "juga"}


def needs_planner(text: str) -> bool:
    """Compound or advice-style questions go to Gemma's planner; one-liners stay on the instant rules."""
    toks = _tokens(text)
    return (text.count("?") > 1 or len(toks) >= 12 or bool(set(toks) & ADVICE_WORDS)
            or (bool(set(toks) & JOIN_WORDS) and sum(t in QUESTION_WORDS for t in toks) >= 2))


def answer(text: str, insights: dict, lang: str = "en", use_gemma: bool | None = None) -> dict:
    """A small agent. Step 1 plans (rules in under a millisecond; Gemma for the long tail and
    for questions that need several tools). Step 2 runs each tool: SQL for the ledger, TabPFN
    for risk, credit limits, what-ifs and forecasts. The trace of both is returned to the UI."""
    t0 = time.perf_counter()
    trace = []
    first = use_gemma is None
    if use_gemma is None:
        use_gemma = needs_planner(text)
    if use_gemma:
        try:
            with tracing.span("gen_ai.invoke_agent", "plan", model=parser.MODEL):
                plan, engine = plan_with_gemma(text), parser.MODEL
        except Exception:
            plan, engine = [route_with_rules(text) | {"_rules": True}], "rules"
    else:
        plan, engine = [route_with_rules(text) | {"_rules": True}], "rules"
    trace.append({"step": "plan", "engine": engine, "ms": round((time.perf_counter() - t0) * 1000),
                  "tools": [st.get("intent") for st in plan]})
    parts = []
    for st in plan:
        t1 = time.perf_counter()
        with tracing.span("gen_ai.execute_tool", st.get("intent") or "help", tool=st.get("intent")):
            part = _run_step(st, text, insights, lang)
        args = {k: st[k] for k in ("customer", "item", "period", "amount", "days")
                if st.get(k) not in (None, "", 0) and not (k == "customer" and st.get("_rules"))}
        if part.get("_cust"):
            args["customer"] = part["_cust"]
        trace.append({"step": part["intent"], "engine": part.get("engine") or "SQLite",
                      "ms": round((time.perf_counter() - t1) * 1000), "args": {k: v for k, v in args.items() if v}})
        parts.append(part)
    useful = [p for p in parts if p["intent"] != "help"] or parts[:1]
    if useful[0]["intent"] == "help" and not use_gemma and first:
        try:
            return answer(text, insights, lang, use_gemma=True)
        except Exception:
            pass
    out = {"question": text, "intent": useful[0]["intent"] if len(useful) == 1 else "plan",
           "engine": engine, "answer": " ".join(p["answer"] for p in useful),
           "rows": next((p["rows"] for p in useful if p["rows"]), []),
           "head": next((p.get("head") for p in useful if p["rows"]), None),
           "curve": next((p.get("curve") for p in useful if p.get("curve")), None),
           "limit": next((p.get("limit") for p in useful if p.get("curve")), None),
           "actions": [], "trace": trace,
           "customer_id": next((p["customer_id"] for p in useful if p.get("customer_id")), None)}
    for p in useful:
        for a_ in p["actions"]:
            if a_ not in out["actions"]:
                out["actions"].append(a_)
    out["ms"] = round((time.perf_counter() - t0) * 1000)
    return out


UNITS = {"milk": "l", "oil": "l", "groundnut oil": "l", "eggs": "dozen", "noodles": "pkt", "biscuits": "pkt",
         "tea": "pkt", "soap": "pc", "bread": "pc"}


def _unit(item: str) -> str:
    return UNITS.get(item, "kg")


def order_plan(insights: dict) -> list[dict]:
    R = insights.get("restock", {})
    plan = []
    for i in R.get("items") or []:
        f, n = (i["festival_14d"], i["normal_14d"]) if i.get("festival_14d") is not None else (i["next_7d"], i["normal_7d"])
        extra = int(-(-max(f - n, 0) // 1))
        if extra > 0 and (i.get("festival_change_pct") or i.get("week_change_pct") or 0) >= 8:
            plan.append({"item": i["item"], "extra": extra, "unit": _unit(i["item"]),
                         "pct": i.get("festival_change_pct") if i.get("festival_14d") is not None else i.get("week_change_pct")})
    return sorted(plan, key=lambda p: -(p["pct"] or 0))


def order_message(insights: dict, lang: str = "en", shop: str = "") -> str:
    plan = order_plan(insights)[:12]
    if lang == "mr":
        head = "नमस्कार, पुढच्या दोन आठवड्यांसाठी खालील माल पाठवा:"
        tail = "धन्यवाद."
    else:
        head = "Hello, please send the following for the next two weeks:"
        tail = "Thank you."
    lines = [f"• {p['item'].title()}: {p['extra']} {p['unit']}" for p in plan]
    return "\n".join([head, *lines, tail]) if lines else head


def brief(insights: dict, lang: str = "en") -> dict:
    mr = lang == "mr"
    with db.connect() as con:
        bal = db.balances(con)
        # the briefing reports the last complete day, not the half-day in progress
        last = con.execute("SELECT date(MAX(ts)) FROM entries WHERE date(ts) < ?", (date.today().isoformat(),)).fetchone()[0] \
            or con.execute("SELECT date(MAX(ts)) FROM entries").fetchone()[0]
        day = con.execute("""SELECT
            COALESCE(SUM(CASE WHEN kind='sale' THEN amount END),0) cash,
            COALESCE(SUM(CASE WHEN kind='credit' THEN amount END),0) credit,
            COALESCE(SUM(CASE WHEN kind='payment' THEN amount END),0) paid, COUNT(*) n
            FROM entries WHERE date(ts)=?""", (last,)).fetchone() if last else None
        avg = con.execute("""SELECT AVG(c) FROM (SELECT SUM(amount) c FROM entries WHERE kind='sale'
            AND date(ts) BETWEEN date(?, '-28 day') AND date(?, '-1 day') GROUP BY date(ts))""", (last, last)).fetchone()[0] if last else None
    cards = []
    risk = [c for c in (insights.get("risk", {}).get("customers") or []) if c["band"] == "high"]
    if risk:
        amt = sum(c["due"] for c in risk)
        top = max(risk, key=lambda c: c["risk"] * c["due"])
        cards.append({"kind": "collect",
                      "title": (f"{len(risk)} ग्राहकांकडून {CUR}{amt:,.0f} वसूल करा" if mr else f"Collect {CUR}{amt:,.0f} from {len(risk)} customers"),
                      "body": (f"{top['customer']} सर्वात आधी: {CUR}{top['due']:,.0f}, {top['days_since_payment']} दिवसांपासून काही भरले नाही." if mr else
                               f"Start with {top['customer']}: {CUR}{top['due']:,.0f} due, nothing paid in {top['days_since_payment']} days."),
                      "names": [c["customer"] for c in risk],
                      "action": {"type": "remind", "customer": top["customer"], "due": top["due"]}})
    plan = order_plan(insights)
    R = insights.get("restock", {})
    if plan:
        fest = R.get("days_to_festival") if (R.get("items") or [{}])[0].get("festival_14d") is not None else None
        top3 = ", ".join(f"{p['item']} +{p['extra']} {p['unit']}" for p in plan[:3])
        cards.append({"kind": "order",
                      "title": (f"सणापूर्वी {len(plan)} माल जास्त मागवा" if mr else f"Order more of {len(plan)} items") + (
                          "" if fest is None else (f" ({fest} दिवस बाकी)" if mr else f" before the festival in {fest} days")),
                      "body": top3, "action": {"type": "order"}})
    if day:
        diff = round((day["cash"] / avg - 1) * 100) if avg else None
        cards.append({"kind": "day",
                      "title": (f"{last}: रोख {CUR}{day['cash']:,.0f}" if mr else f"{_nice_day(last)}: {CUR}{day['cash']:,.0f} in cash sales"),
                      "body": ((f"नेहमीपेक्षा {diff:+d}%. " if diff is not None else "") + f"उधार {CUR}{day['credit']:,.0f}, वसूल {CUR}{day['paid']:,.0f}." if mr else
                               (f"{diff:+d}% vs a usual day. " if diff is not None else "") + f"{CUR}{day['credit']:,.0f} given on udhaar, {CUR}{day['paid']:,.0f} collected."),
                      "action": None})
    return {"cards": cards, "total_due": round(sum(b["due"] for b in bal if b["due"] > 0)),
            "accounts": sum(1 for b in bal if b["due"] > 0)}


def _nice_day(iso: str) -> str:
    d = datetime.fromisoformat(iso).date()
    return d.strftime("%a %d %b").replace(" 0", " ")

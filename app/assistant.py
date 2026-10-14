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

from . import db, parser
import os

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
           "order_plan", "sales_summary", "help"]
PERIODS = ["today", "yesterday", "week", "month"]

Q_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": INTENTS},
        "customer": {"type": ["string", "null"]},
        "item": {"type": ["string", "null"]},
        "period": {"type": ["string", "null"], "enum": PERIODS + [None]},
    },
    "required": ["intent", "customer", "item", "period"],
}
Q_SYSTEM = """You route questions from a small shopkeeper (Marathi, Hindi, English, Spanish, Filipino or Indonesian, often mixed) to one intent.
customer_due: how much a named person owes. customer_history: what a named person took or paid.
top_due: who owes the most. risky: who may not pay back. item_forecast: how much of an item will be needed / to order.
item_sales: how much of an item was sold. order_plan: what to order from the wholesaler.
sales_summary: cash, udhaar, collection totals for a period. help: anything else.
item in simple English (sakhar/azúcar/asukal/gula->sugar, tel/aceite/mantika/minyak->oil). period: today, yesterday, week or month. JSON only."""


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


def route_with_rules(text: str) -> dict:
    toks = set(_tokens(text))
    item, period = _item_in(text), _period_in(list(toks))
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
    return {"intent": intent, "customer": text, "item": item, "period": period}


def route_with_gemma(text: str) -> dict:
    r = httpx.post(f"{parser.OLLAMA_URL}/api/chat", timeout=20, json={
        "model": parser.MODEL, "stream": False, "format": Q_SCHEMA, "options": parser.OPTS,
        "keep_alive": "30m",
        "messages": [{"role": "system", "content": Q_SYSTEM},
                     {"role": "user", "content": "Patil kaku kitna baki hai?"},
                     {"role": "assistant", "content": json.dumps({"intent": "customer_due", "customer": "Patil Kaku", "item": None, "period": None})},
                     {"role": "user", "content": "pudhchya athavdyat kiti sakhar lagel"},
                     {"role": "assistant", "content": json.dumps({"intent": "item_forecast", "customer": None, "item": "sugar", "period": "week"})},
                     {"role": "user", "content": text}]})
    r.raise_for_status()
    return json.loads(r.json()["message"]["content"])


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


def answer(text: str, insights: dict, lang: str = "en", use_gemma: bool = False) -> dict:
    """Fast path first: rules understand the common phrasings in under a millisecond.
    Only when they can't (intent comes out as "help") do we pay for a Gemma call."""
    t0 = datetime.now()
    if use_gemma:
        try:
            q, engine = route_with_gemma(text), parser.MODEL
        except Exception:
            q, engine = route_with_rules(text), "rules"
    else:
        q, engine = route_with_rules(text), "rules"
    mr = lang == "mr"
    out = {"question": text, "intent": q.get("intent"), "engine": engine, "rows": [], "actions": []}
    with db.connect() as con:
        cust = resolve_customer(con, q.get("customer"))
        intent = q.get("intent")
        if engine == "rules" and cust and intent in ("sales_summary", "help", "customer_due"):
            hist = {"liya", "ghetla", "ghetle", "history", "entries", "nondi", "kya", "kay"} & set(_tokens(text))
            intent = "customer_history" if hist else "customer_due"
        if intent in ("customer_due", "customer_history") and not cust:
            intent = "help"
        out["intent"] = intent
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

        else:
            out["answer"] = ("मी नोंद लिहू शकतो किंवा विचारू शकता: \"Patil kaku kiti baki?\", \"kon jast baki?\", \"pudhchya athavdyat kiti sakhar?\"" if mr else
                             "I can write an entry, or answer things like “how much does Patil Kaku owe?”, “who owes the most?”, “how much sugar next week?”.")
    if out["intent"] == "help" and not use_gemma:
        try:
            return answer(text, insights, lang, use_gemma=True)
        except Exception:
            pass
    out["ms"] = round((datetime.now() - t0).total_seconds() * 1000)
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

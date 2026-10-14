"""Turn a shopkeeper's spoken line (Marathi / Hindi / English, usually mixed) into a ledger entry.

Primary path: Gemma running locally in Ollama, constrained to a JSON schema.
Fallback path: a small rule-based parser, so the counter never stops working if
the model is busy or not installed.
"""
from __future__ import annotations

import json
import os
import re
import time

import httpx

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MODEL = os.environ.get("UDHAAR_MODEL", "gemma3:4b")
# Our prompts are ~500 tokens. A small context means a small KV cache, so more of the
# model fits on a 4 GB laptop GPU instead of spilling onto the CPU.
NUM_CTX = int(os.environ.get("UDHAAR_NUM_CTX", "1024"))
# Cap the output: an entry is < 150 tokens. Small models sometimes keep emitting whitespace
# after the JSON under structured output; without a cap that looks like a hang.
OPTS = {"temperature": 0, "num_ctx": NUM_CTX, "num_predict": 256}

# Words a kirana counter actually hears -> canonical item names.
GLOSSARY = {
    "sakhar": "sugar", "saakhar": "sugar", "chini": "sugar", "cheeni": "sugar", "shakkar": "sugar",
    "tel": "oil", "tail": "oil", "goda tel": "oil", "shengdana tel": "groundnut oil",
    "tandul": "rice", "chawal": "rice", "chaval": "rice",
    "gahu": "wheat", "gehun": "wheat", "atta": "atta", "aata": "atta", "peeth": "atta",
    "dal": "dal", "daal": "dal", "toor dal": "toor dal", "turdal": "toor dal", "tur dal": "toor dal",
    "doodh": "milk", "dudh": "milk", "milk": "milk",
    "kanda": "onion", "pyaz": "onion", "pyaaz": "onion",
    "batata": "potato", "aloo": "potato", "alu": "potato",
    "chaha": "tea", "chai patti": "tea", "chaha patti": "tea", "chai": "tea",
    "sabun": "soap", "sabu": "soap", "biscuit": "biscuits", "parle": "biscuits",
    "anda": "eggs", "andi": "eggs", "ande": "eggs", "egg": "eggs", "eggs": "eggs",
    "mith": "salt", "namak": "salt", "poha": "poha", "rava": "rava", "suji": "rava",
    "besan": "besan", "maida": "maida", "ghee": "ghee", "tup": "ghee",
    "maggi": "noodles", "noodles": "noodles", "bread": "bread", "pav": "bread",
}

NUM_WORDS = {
    "ek": 1, "eka": 1, "one": 1, "do": 2, "don": 2, "two": 2, "teen": 3, "tin": 3, "three": 3,
    "char": 4, "chaar": 4, "four": 4, "paach": 5, "panch": 5, "five": 5, "saha": 6, "chhe": 6, "six": 6,
    "saat": 7, "sat": 7, "seven": 7, "aath": 8, "ath": 8, "eight": 8, "nau": 9, "nine": 9,
    "daha": 10, "das": 10, "ten": 10, "dozen": 12, "darjan": 12,
    "aadha": 0.5, "adha": 0.5, "ardha": 0.5, "half": 0.5, "paav": 0.25, "pav kilo": 0.25,
    "dedh": 1.5, "deed": 1.5, "dhai": 2.5, "adich": 2.5,
}

UNITS = {
    "kilo": "kg", "kg": "kg", "kilogram": "kg", "kgs": "kg",
    "gram": "g", "grams": "g", "gm": "g", "g": "g",
    "litre": "l", "liter": "l", "litres": "l", "ltr": "l", "l": "l",
    "packet": "pkt", "packets": "pkt", "pudi": "pkt", "pkt": "pkt", "puda": "pkt",
    "dozen": "dozen", "darjan": "dozen", "nag": "pc", "piece": "pc", "pcs": "pc",
}

CREDIT_WORDS = ["udhaar", "udhar", "udhari", "khate", "khata", "credit", "baki", "baaki", "lihun", "likh", "likho", "naave", "nave"]
PAYMENT_WORDS = ["jama", "dile", "diye", "paid", "payment", "bharle", "bharla", "parat", "chukavle", "wapas", "returned"]

SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": ["sale", "credit", "payment"]},
        "customer": {"type": ["string", "null"]},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "qty": {"type": ["number", "null"]},
                    "unit": {"type": ["string", "null"]},
                    "amount": {"type": ["number", "null"]},
                },
                "required": ["name"],
            },
        },
        "total": {"type": ["number", "null"]},
    },
    "required": ["kind", "customer", "items", "total"],
}

SYSTEM = """You are the bookkeeper at a small Indian kirana (grocery) shop in Maharashtra.
The shopkeeper speaks one short line, usually mixing Marathi, Hindi and English.
Convert it into ONE JSON object:
- kind: "credit" if goods were taken on udhaar/khata (to be paid later), "payment" if the customer paid back money, otherwise "sale" (paid now).
- customer: the person's name as spoken (e.g. "Patil Kaku", "Sharma ji"), or null.
- items: each item with name in simple English (sakhar->sugar, tel->oil, tandul->rice, kanda->onion), qty as a number, unit (kg, g, l, pkt, dozen, pc) and amount in rupees if said.
- total: total rupees mentioned, or the sum of item amounts. For a payment, the amount paid.
Never invent prices. If a number is not said, use null. Output JSON only."""

FEW_SHOT = [
    ("Patil kaku, don kilo sakhar ani ek litre tel, 210 udhaar",
     {"kind": "credit", "customer": "Patil Kaku", "items": [
         {"name": "sugar", "qty": 2, "unit": "kg", "amount": None},
         {"name": "oil", "qty": 1, "unit": "l", "amount": None}], "total": 210}),
    ("Sharma ji ne 500 jama kiye", {"kind": "payment", "customer": "Sharma Ji", "items": [], "total": 500}),
    ("teen packet maggi 45 rupaye", {"kind": "sale", "customer": None, "items": [
        {"name": "noodles", "qty": 3, "unit": "pkt", "amount": 45}], "total": 45}),
]


def _canon_item(name: str) -> str:
    n = name.strip().lower()
    return GLOSSARY.get(n, n)


def normalise(p: dict) -> dict:
    """Clean whatever the model produced into the shape db.add_entries expects."""
    kind = p.get("kind") if p.get("kind") in ("sale", "credit", "payment") else "sale"
    items = []
    for it in p.get("items") or []:
        if not isinstance(it, dict) or not it.get("name"):
            continue
        unit = it.get("unit")
        unit = UNITS.get(str(unit).lower(), unit) if unit else None
        items.append({"name": _canon_item(str(it["name"])), "qty": _num(it.get("qty")),
                      "unit": unit, "amount": _num(it.get("amount"))})
    total = _num(p.get("total"))
    if total is None:
        total = sum(i["amount"] or 0 for i in items) or None
    cust = p.get("customer")
    cust = " ".join(str(cust).split()).title() if cust else None
    return {"kind": kind, "customer": cust, "items": [] if kind == "payment" else items, "total": total}


def _num(x):
    if x is None or x == "":
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- Gemma path
def parse_with_gemma(text: str, timeout: float = 20) -> dict:
    msgs = [{"role": "system", "content": SYSTEM}]
    for u, a in FEW_SHOT:
        msgs += [{"role": "user", "content": u}, {"role": "assistant", "content": json.dumps(a)}]
    msgs.append({"role": "user", "content": text})
    r = httpx.post(f"{OLLAMA_URL}/api/chat", timeout=timeout, json={
        "model": MODEL, "messages": msgs, "format": SCHEMA, "stream": False,
        "options": OPTS, "keep_alive": "30m"})
    r.raise_for_status()
    return normalise(json.loads(r.json()["message"]["content"]))


# ---------------------------------------------------------------- rule fallback
_TOKEN = re.compile(r"[a-zA-Zऀ-ॿ]+|\d+(?:\.\d+)?")


def parse_with_rules(text: str) -> dict:
    t = text.lower().replace(",", " ").replace("₹", " ")
    toks = _TOKEN.findall(t)
    kind = "sale"
    if any(w in toks for w in PAYMENT_WORDS):
        kind = "payment"
    elif any(w in toks for w in CREDIT_WORDS):
        kind = "credit"

    # customer = leading words before the first number/item/keyword, if they look like a name
    stop = set(GLOSSARY) | set(NUM_WORDS) | set(UNITS) | set(CREDIT_WORDS) | set(PAYMENT_WORDS) | {
        "ne", "ni", "ani", "aur", "and", "la", "ko", "rupaye", "rupees", "rs", "che", "ka", "ki", "kiye", "diya"}
    name = []
    for tok in toks:
        if tok in stop or tok.replace(".", "").isdigit():
            break
        name.append(tok)
    customer = " ".join(name[:3]).title() if name else None

    items, money = [], []
    i = 0
    while i < len(toks):
        tok = toks[i]
        q = float(tok) if tok.replace(".", "").isdigit() else NUM_WORDS.get(tok)
        if q is not None:
            nxt = toks[i + 1] if i + 1 < len(toks) else ""
            unit = UNITS.get(nxt)
            j = i + 2 if unit else i + 1
            item = toks[j] if j < len(toks) else ""
            two = f"{item} {toks[j+1]}" if j + 1 < len(toks) else ""
            if two in GLOSSARY:
                items.append({"name": GLOSSARY[two], "qty": q, "unit": unit, "amount": None}); i = j + 2; continue
            if item in GLOSSARY:
                items.append({"name": GLOSSARY[item], "qty": q, "unit": unit, "amount": None}); i = j + 1; continue
            if not unit and tok.replace(".", "").isdigit():
                money.append(q)
        elif tok in GLOSSARY:
            items.append({"name": GLOSSARY[tok], "qty": None, "unit": None, "amount": None})
        i += 1
    total = max(money) if money else None
    if len(items) == 1 and total is not None:
        items[0]["amount"] = total
    return normalise({"kind": kind, "customer": customer, "items": items, "total": total})


def parse(text: str) -> dict:
    """Gemma first; rules if Ollama is unreachable. Returns entry + which engine ran + latency."""
    t0 = time.perf_counter()
    try:
        out, engine = parse_with_gemma(text), MODEL
    except Exception:
        out, engine = parse_with_rules(text), "rules"
    out["_engine"] = engine
    out["_ms"] = round((time.perf_counter() - t0) * 1000)
    return out

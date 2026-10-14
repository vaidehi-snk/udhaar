"""Turn a shopkeeper's spoken line into a ledger entry.

Corner shops everywhere run on credit: udhaar in India, fiado in Mexico, utang in a
Philippine sari-sari store, hutang / bon in an Indonesian warung. Lines arrive in
Marathi, Hindi, English, Spanish, Filipino or Indonesian, often mixed.

Primary path: Gemma running locally in Ollama, constrained to a JSON schema.
Fallback path: a small rule-based parser, so the counter never stops working if
the model is busy or not installed.
"""
from __future__ import annotations

import json
import os
import re
import time
import unicodedata

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
    # Spanish (tiendita, bodega)
    "azucar": "sugar", "aceite": "oil", "arroz": "rice", "frijol": "beans", "frijoles": "beans",
    "huevo": "eggs", "huevos": "eggs", "leche": "milk", "harina": "flour", "cebolla": "onion",
    "cebollas": "onion", "papa": "potato", "papas": "potato", "jabon": "soap", "sal": "salt",
    "galleta": "biscuits", "galletas": "biscuits", "cafe": "coffee", "pan": "bread", "tortillas": "tortillas",
    "refresco": "soda", "refrescos": "soda", "sopa": "noodles", "maruchan": "noodles",
    # Filipino (sari-sari store)
    "asukal": "sugar", "mantika": "oil", "bigas": "rice", "itlog": "eggs", "gatas": "milk",
    "kape": "coffee", "sabon": "soap", "asin": "salt", "sibuyas": "onion", "patatas": "potato",
    "sardinas": "sardines", "tinapay": "bread", "pandesal": "bread", "harina ng trigo": "flour",
    "pancit canton": "noodles", "lucky me": "noodles",
    # Indonesian (warung)
    "gula": "sugar", "minyak": "oil", "minyak goreng": "oil", "beras": "rice", "telur": "eggs",
    "susu": "milk", "kopi": "coffee", "garam": "salt", "bawang": "onion", "kentang": "potato",
    "mie": "noodles", "indomie": "noodles", "roti": "bread", "tepung": "flour", "teh": "tea",
    "rokok": "cigarettes", "gas": "lpg",
}

NUM_WORDS = {
    "ek": 1, "eka": 1, "one": 1, "do": 2, "don": 2, "two": 2, "teen": 3, "tin": 3, "three": 3,
    "char": 4, "chaar": 4, "four": 4, "paach": 5, "panch": 5, "five": 5, "saha": 6, "chhe": 6, "six": 6,
    "saat": 7, "sat": 7, "seven": 7, "aath": 8, "ath": 8, "eight": 8, "nau": 9, "nine": 9,
    "daha": 10, "das": 10, "ten": 10, "dozen": 12, "darjan": 12,
    "aadha": 0.5, "adha": 0.5, "ardha": 0.5, "half": 0.5, "paav": 0.25, "pav kilo": 0.25,
    "dedh": 1.5, "deed": 1.5, "dhai": 2.5, "adich": 2.5,
    # Spanish
    "un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6,
    "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "docena": 12, "medio": 0.5, "media": 0.5,
    # Filipino
    "isa": 1, "isang": 1, "dalawa": 2, "dalawang": 2, "tatlo": 3, "tatlong": 3, "apat": 4, "apat na": 4,
    "lima": 5, "limang": 5, "anim": 6, "pito": 7, "walo": 8, "siyam": 9, "sampu": 10, "kalahati": 0.5,
    # Indonesian
    "satu": 1, "dua": 2, "tiga": 3, "empat": 4, "enam": 6, "tujuh": 7,
    "delapan": 8, "sembilan": 9, "sepuluh": 10, "setengah": 0.5, "sekilo": 1, "seliter": 1,
}

UNITS = {
    "kilo": "kg", "kg": "kg", "kilogram": "kg", "kgs": "kg",
    "gram": "g", "grams": "g", "gm": "g", "g": "g",
    "litre": "l", "liter": "l", "litres": "l", "ltr": "l", "l": "l",
    "packet": "pkt", "packets": "pkt", "pudi": "pkt", "pkt": "pkt", "puda": "pkt",
    "dozen": "dozen", "darjan": "dozen", "nag": "pc", "piece": "pc", "pcs": "pc",
    "kilos": "kg", "kilong": "kg", "litro": "l", "litros": "l", "litrong": "l", "liter": "l",
    "paquete": "pkt", "paquetes": "pkt", "bolsa": "pkt", "bolsas": "pkt", "sobre": "pkt", "sobres": "pkt",
    "pakete": "pkt", "bungkus": "pkt", "bks": "pkt", "pieza": "pc", "piezas": "pc", "piraso": "pc",
    "buah": "pc", "biji": "pc", "butir": "pc", "lata": "pc", "latas": "pc", "docena": "dozen",
}

CREDIT_WORDS = ["udhaar", "udhar", "udhari", "khate", "khata", "credit", "baki", "baaki", "lihun", "likh", "likho", "naave", "nave",
                "fiado", "fiar", "fio", "apunta", "apuntale", "apuntalo", "cuenta", "debe",       # es
                "utang", "inutang", "ilista", "listahan", "lista",                                  # fil
                "hutang", "ngutang", "bon", "ngebon", "catat", "kasbon", "tempo"]                   # id
PAYMENT_WORDS = ["jama", "dile", "diye", "paid", "payment", "bharle", "bharla", "parat", "chukavle", "wapas", "returned",
                 "pago", "pagó", "abono", "abonó", "liquido", "liquidó",                          # es
                 "bayad", "nagbayad", "binayaran", "nagbigay",                                    # fil
                 "bayar", "lunas", "dibayar", "nyicil", "cicil"]                                  # id
MULTIPLIERS = {"ribu": 1000, "rb": 1000, "mil": 1000, "k": 1000, "libo": 1000, "juta": 1_000_000}
CURRENCY_WORDS = {"rupaye", "rupees", "rs", "rupee", "pesos", "peso", "piso", "rupiah", "rp", "mxn", "php", "idr"}
# Titles that start a name even when the word means something else ("don" is also Marathi for two)
HONORIFICS = {"don", "dona", "senora", "senor", "seno", "aling", "mang", "kuya", "ate", "tita", "tito",
              "bu", "ibu", "pak", "bapak", "mbak", "mas", "bang"}
LEADING = {"a", "la", "el", "para", "kay", "kina", "untuk", "buat"}
FILLER = {"de", "del", "ng", "na", "of", "ka", "ki", "ke", "y", "at", "dan", "and", "ani", "aur"}

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

SYSTEM = """You are the bookkeeper of a small neighbourhood grocery shop: an Indian kirana, a Mexican tiendita, a Filipino sari-sari store or an Indonesian warung.
The owner speaks one short line in Marathi, Hindi, English, Spanish, Filipino or Indonesian, often mixed.
Convert it into ONE JSON object:
- kind: "credit" if goods were taken to be paid later (udhaar, khata, fiado, apúntalo, utang, ilista, hutang, bon), "payment" if the customer paid money back (jama, dile, pagó, abonó, bayad, nagbayad, bayar, lunas), otherwise "sale" (paid now).
- customer: the person's name as spoken, with any title (e.g. "Patil Kaku", "Doña Rosa", "Aling Nena", "Bu Sri"), or null.
- items: each item with name in simple English (sakhar/azúcar/asukal/gula->sugar, tel/aceite/mantika/minyak->oil, bigas/beras/arroz->rice, itlog/telur/huevos->eggs), qty as a number, unit (kg, g, l, pkt, dozen, pc) and amount if said.
- total: total money mentioned as a plain number ("50 ribu" or "50rb" = 50000, "dos mil" = 2000), or the sum of item amounts. For a payment, the amount paid.
Never invent prices. If a number is not said, use null. Output JSON only."""

FEW_SHOT = [
    ("Patil kaku, don kilo sakhar ani ek litre tel, 210 udhaar",
     {"kind": "credit", "customer": "Patil Kaku", "items": [
         {"name": "sugar", "qty": 2, "unit": "kg", "amount": None},
         {"name": "oil", "qty": 1, "unit": "l", "amount": None}], "total": 210}),
    ("Sharma ji ne 500 jama kiye", {"kind": "payment", "customer": "Sharma Ji", "items": [], "total": 500}),
    ("teen packet maggi 45 rupaye", {"kind": "sale", "customer": None, "items": [
        {"name": "noodles", "qty": 3, "unit": "pkt", "amount": 45}], "total": 45}),
    ("Doña Rosa, dos kilos de azúcar y un aceite, apúntalo, 96 pesos", {"kind": "credit", "customer": "Doña Rosa", "items": [
        {"name": "sugar", "qty": 2, "unit": "kg", "amount": None}, {"name": "oil", "qty": 1, "unit": None, "amount": None}], "total": 96}),
    ("Bu Sri bayar 50 ribu", {"kind": "payment", "customer": "Bu Sri", "items": [], "total": 50000}),
]


def _canon_item(name: str) -> str:
    n = name.strip().lower()
    return GLOSSARY.get(n, GLOSSARY.get(_fold(n), n))


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
_TOKEN = re.compile(r"(?:[^\W\d_]|[\u0900-\u097F])+|\d{1,3}(?:[.,]\d{3})+(?![\d])|\d+(?:\.\d+)?")


def _fold(tok: str) -> str:
    """azúcar -> azucar, but leave Devanagari alone (its vowel signs are combining marks)."""
    if any("\u0900" <= c <= "\u097F" for c in tok):
        return tok
    return "".join(c for c in unicodedata.normalize("NFKD", tok) if not unicodedata.combining(c))


def _numval(tok: str) -> float | None:
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", tok):       # 15.000 / 15,000
        return float(re.sub(r"[.,]", "", tok))
    if re.fullmatch(r"\d+(?:\.\d+)?", tok):
        return float(tok)
    return None


def parse_with_rules(text: str) -> dict:
    raw = text.lower().replace("₹", " ").replace("$", " ")
    orig = _TOKEN.findall(raw)
    toks = [_fold(t) for t in orig]
    folded_words = set(toks)
    pay = {_fold(w) for w in PAYMENT_WORDS}; cred = {_fold(w) for w in CREDIT_WORDS}
    kind = "payment" if folded_words & pay else "credit" if folded_words & cred else "sale"

    # customer = leading words before the first number/item/keyword, kept with their accents
    stop = set(GLOSSARY) | set(NUM_WORDS) | set(UNITS) | cred | pay | CURRENCY_WORDS | FILLER | {
        "ne", "ni", "la", "ko", "che", "kiye", "diya", "kiya", "le", "liya", "ghetle", "nag", "si", "ang",
        "me", "mo", "niya", "yung", "sama", "ya", "lo", "que"}
    name = []
    start = 0
    while start < len(toks) - 1 and toks[start] in LEADING:   # "a la señora Lupita", "para Don Pepe"
        start += 1
    pairs = list(zip(orig, toks))[start:]
    quantityish = lambda t: t in UNITS or t in NUM_WORDS or _numval(t) is not None
    titled = len(pairs) > 1 and pairs[0][1] in HONORIFICS and not quantityish(pairs[1][1])
    for k, (o, tok) in enumerate(pairs):
        # a title and the word right after it are always the name ("Mas Andi", even though
        # "andi" is also Marathi for eggs), unless that word is clearly a quantity ("don kilo")
        if titled and k <= 1:
            name.append(o); continue
        if tok in stop or _numval(tok) is not None:
            break
        name.append(o)
    customer = " ".join(name[:3]).title() if name else None

    items, money = [], []
    n = len(toks)

    def lookup(j):
        """Item name at j (two-word names first), skipping 'de' / 'ng' style fillers."""
        while j < n and toks[j] in FILLER:
            j += 1
        if j + 1 < n and f"{toks[j]} {toks[j+1]}" in GLOSSARY:
            return GLOSSARY[f"{toks[j]} {toks[j+1]}"], j + 2
        if j < n and toks[j] in GLOSSARY:
            return GLOSSARY[toks[j]], j + 1
        return None, j

    def qty_at(j):
        """Quantity (+unit) at j, e.g. '2 kilo', 'dos kilos', 'isang kilong', 'sekilo'."""
        if j >= n:
            return None, None, j
        q = _numval(toks[j])
        if q is None:
            q = NUM_WORDS.get(toks[j])
        if q is None:
            return None, None, j
        u = UNITS.get(toks[j + 1]) if j + 1 < n else None
        if toks[j] in ("sekilo", "seliter"):           # "a kilo" in one word
            return q, ("kg" if toks[j] == "sekilo" else "l"), j + 1
        return q, u, j + (2 if u else 1)

    i = 0
    while i < n:
        q, unit, j = qty_at(i)
        if q is not None:
            item, k = lookup(j)
            if item:
                items.append({"name": item, "qty": q, "unit": unit, "amount": None}); i = k; continue
            if not unit and _numval(toks[i]) is not None:
                mult = MULTIPLIERS.get(toks[i + 1], 1) if i + 1 < n else 1
                money.append(q * mult)
                i += 2 if mult > 1 else 1
                continue
            i += 1
            continue
        item, k = lookup(i)
        if item and k > i:
            q2, u2, k2 = qty_at(k)                   # Indonesian order: "beras 2 kilo"
            if q2 is not None and (u2 or (k2 < n and toks[k2] not in MULTIPLIERS and _numval(toks[k - 0]) is None)):
                items.append({"name": item, "qty": q2, "unit": u2, "amount": None}); i = k2; continue
            items.append({"name": item, "qty": None, "unit": None, "amount": None}); i = k; continue
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

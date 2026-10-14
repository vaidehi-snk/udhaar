"""Score Gemma vs the rule parser on real-sounding counter lines. Put the numbers in your post.

    python scripts/eval_parser.py            (needs Ollama running for the Gemma column)
Add the shopkeeper's own lines to CASES after your user test; they're the best test set.
"""
import sys
import time

import httpx
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import parser  # noqa: E402

# (utterance, kind, customer or None, total or None, {item names})
CASES = [
    ("Patil kaku, don kilo sakhar ani ek litre tel, 210 udhaar", "credit", "Patil Kaku", 210, {"sugar", "oil"}),
    ("Sharma ji ne 500 jama kiye", "payment", "Sharma Ji", 500, set()),
    ("teen packet maggi 45 rupaye", "sale", None, 45, {"noodles"}),
    ("Jadhav bhau 2 kilo kanda 70 khate", "credit", "Jadhav Bhau", 70, {"onion"}),
    ("More kaka ek kilo tup 640 udhaar", "credit", "More Kaka", 640, {"ghee"}),
    ("Kulkarni aaji ni 300 rupaye dile", "payment", "Kulkarni Aaji", 300, set()),
    ("ardha kilo toor dal ani paav kilo chaha patti, Deshmukh vahini, lihun theva", "credit", "Deshmukh Vahini", None, {"toor dal", "tea"}),
    ("ek dozen ande 84", "sale", None, 84, {"eggs"}),
    ("Shinde mama che 1200 baki, aaj 400 parat dile", "payment", "Shinde Mama", 400, set()),
    ("Khan bhai do kilo aata aur ek sabun, khate me likh do 122", "credit", "Khan Bhai", 122, {"atta", "soap"}),
    ("paanch kilo tandul 290 cash", "sale", None, 290, {"rice"}),
    ("Pawar tai, besan ek kilo, maida ek kilo, rava ek kilo, Diwali sathi, 190 udhaar", "credit", "Pawar Tai", 190, {"besan", "maida", "rava"}),
    ("Gaikwad sir paid 1000 by phonepe", "payment", "Gaikwad Sir", 1000, set()),
    ("दोन किलो साखर पाटील काकूंच्या नावे", "credit", "Patil Kaku", None, {"sugar"}),
    ("शर्मा जी ने पाँच सौ जमा किए", "payment", "Sharma Ji", 500, set()),
    ("Joshi kaku, char litre doodh, mahinyacha khata", "credit", "Joshi Kaku", None, {"milk"}),
    ("Sayyed chacha ek kilo shakkar, do packet biscuit, 66 baad mein denge", "credit", "Sayyed Chacha", 66, {"sugar", "biscuits"}),
    ("Rathod bhai ne saare 706 chuka diye", "payment", "Rathod Bhai", 706, set()),
]

# Same shop, other countries. Written to sound like a real counter, not a textbook.
GLOBAL = {
    "Spanish (tiendita)": [
        ("Doña Rosa, dos kilos de azúcar y un aceite, apúntalo, 96 pesos", "credit", "Doña Rosa", 96, {"sugar", "oil"}),
        ("Don Pepe pagó 200 de lo que debía", "payment", "Don Pepe", 200, set()),
        ("tres refrescos y unas galletas, 58 pesos", "sale", None, 58, {"soda", "biscuits"}),
        ("a la señora Lupita, medio kilo de frijol y una docena de huevos, fiado, 70", "credit", "Señora Lupita", 70, {"beans", "eggs"}),
        ("Juanito me abonó 150 pesos", "payment", "Juanito", 150, set()),
    ],
    "Filipino (sari-sari)": [
        ("Aling Nena, isang kilong bigas at dalawang itlog, 85 utang", "credit", "Aling Nena", 85, {"rice", "eggs"}),
        ("Mang Tonyo nagbayad ng 150", "payment", "Mang Tonyo", 150, set()),
        ("Kuya Jun, tatlong sardinas, ilista mo, 66", "credit", "Kuya Jun", 66, {"sardines"}),
        ("dalawang kape at isang pandesal, 27 piso", "sale", None, 27, {"coffee", "bread"}),
        ("Ate Joy binayaran na yung 300 na utang niya", "payment", "Ate Joy", 300, set()),
    ],
    "Indonesian (warung)": [
        ("Bu Sri bayar 50 ribu", "payment", "Bu Sri", 50000, set()),
        ("Pak Budi ngutang beras 2 kilo dan minyak goreng 1 liter, 48.000", "credit", "Pak Budi", 48000, {"rice", "oil"}),
        ("dua bungkus indomie 7rb", "sale", None, 7000, {"noodles"}),
        ("Mbak Rina kasbon gula sekilo sama telur sekilo, 45 ribu", "credit", "Mbak Rina", 45000, {"sugar", "eggs"}),
        ("Mas Andi lunas 120 ribu", "payment", "Mas Andi", 120000, set()),
    ],
}


def score(fn, cases=None):
    cases = CASES if cases is None else cases
    ok = {"kind": 0, "customer": 0, "total": 0, "items": 0, "all": 0}
    ms = []
    for text, kind, cust, total, items in cases:
        t0 = time.perf_counter()
        try:
            p = fn(text)
        except httpx.ConnectError:
            return None
        except Exception as e:  # timeout or broken JSON counts as a miss, not a crash
            print(f"  miss ({type(e).__name__}): {text}")
            ms.append((time.perf_counter() - t0) * 1000)
            continue
        ms.append((time.perf_counter() - t0) * 1000)
        checks = {
            "kind": p["kind"] == kind,
            "customer": _same(p["customer"], cust),
            "total": (p["total"] is None and total is None) or (total is not None and p["total"] == total),
            "items": {i["name"] for i in p["items"]} == items,
        }
        for k, v in checks.items():
            ok[k] += v
        ok["all"] += all(checks.values())
    n = len(cases)
    return {k: f"{v}/{n}" for k, v in ok.items()} | {"median_ms": round(sorted(ms)[len(ms) // 2])}


def _same(a, b):
    f = lambda x: parser._fold((x or "").lower()).replace(" ", "")
    return f(a) == f(b)


# Held out: written after the rules were tuned on GLOBAL above, and never tuned against.
# This is the honest number for the rules parser outside India.
HELDOUT = [
    ("Doña Carmen se llevó un litro de leche y pan, lo pago el viernes, 42", "credit", "Doña Carmen", 42, {"milk", "bread"}),
    ("el señor Ramírez liquidó su cuenta, 380 pesos", "payment", "Señor Ramírez", 380, set()),
    ("cuatro huevos y medio de jamón, 55", "sale", None, 55, {"eggs", "ham"}),
    ("Tita Baby, isang litrong mantika at asukal, sa listahan, 120", "credit", "Tita Baby", 120, {"oil", "sugar"}),
    ("nagbigay si Kuya Ben ng 200 para sa utang", "payment", "Kuya Ben", 200, set()),
    ("tatlong lucky me at isang kape, 52", "sale", None, 52, {"noodles", "coffee"}),
    ("Pak Joko ambil rokok dua bungkus, bon dulu, 60 ribu", "credit", "Pak Joko", 60000, {"cigarettes"}),
    ("Ibu Ani nyicil 25 ribu", "payment", "Ibu Ani", 25000, set()),
    ("telur setengah kilo sama teh satu bungkus, 22rb", "sale", None, 22000, {"eggs", "tea"}),
]


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--global-only", action="store_true", help="skip the 18 Indian lines")
    ap.add_argument("--rules-only", action="store_true", help="skip Gemma (used by CI)")
    ap.add_argument("--markdown", action="store_true", help="print a Markdown table (for the CI summary)")
    a = ap.parse_args()
    groups = ({} if a.global_only else {"India (mr/hi/en)": CASES}) | GLOBAL | {"Held-out (es/fil/id)": HELDOUT}
    if not a.rules_only:
        try:  # load the model into memory first, so a cold start isn't scored as a miss
            print("warming up", parser.MODEL, "…")
            parser.parse_with_gemma("ek kilo sakhar 46", timeout=180)
        except Exception:
            pass
    if a.markdown:
        print("| Lines | Rules, fully correct |\n|---|---|")
    else:
        print(f"{'':22} {'rules':>8}   {parser.MODEL:>10}")
    for name, cases in groups.items():
        r = score(parser.parse_with_rules, cases)
        g = None if a.rules_only else score(parser.parse_with_gemma, cases)
        if a.markdown:
            print(f"| {name} | {r['all']} |")
            continue
        print(f"{name:22} {r['all']:>8}   {(g or {}).get('all', 'skipped' if a.rules_only else 'offline'):>10}"
              + (f"   (gemma median {g['median_ms']} ms)" if g else ""))

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


def score(fn):
    ok = {"kind": 0, "customer": 0, "total": 0, "items": 0, "all": 0}
    ms = []
    for text, kind, cust, total, items in CASES:
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
            "customer": (p["customer"] or "").lower().replace(" ", "") == (cust or "").lower().replace(" ", ""),
            "total": (p["total"] is None and total is None) or (total is not None and p["total"] == total),
            "items": {i["name"] for i in p["items"]} == items,
        }
        for k, v in checks.items():
            ok[k] += v
        ok["all"] += all(checks.values())
    n = len(CASES)
    return {k: f"{v}/{n}" for k, v in ok.items()} | {"median_ms": round(sorted(ms)[len(ms) // 2])}


if __name__ == "__main__":
    print("rules :", score(parser.parse_with_rules))
    g = score(parser.parse_with_gemma)
    print(f"{parser.MODEL}:", g or "Ollama not reachable — start it and `ollama pull gemma3:4b`")

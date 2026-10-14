"""Generate ~13 months of realistic kirana history so the predictions have something to learn from.

Clearly labelled demo data (source='demo'). Replace with the real shop's entries over time,
or wipe it with:  python scripts/make_demo_data.py --wipe
"""
import argparse
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import db  # noqa: E402
from app.predict import FESTIVALS  # noqa: E402

ITEMS = {  # item: (unit, price per unit, base daily qty, festival multiplier)
    "sugar": ("kg", 46, 6, 2.2), "oil": ("l", 165, 3, 1.8), "rice": ("kg", 58, 7, 1.3),
    "atta": ("kg", 42, 8, 1.3), "toor dal": ("kg", 160, 2.5, 1.4), "milk": ("l", 56, 18, 1.5),
    "onion": ("kg", 35, 6, 1.1), "potato": ("kg", 30, 6, 1.1), "tea": ("pkt", 120, 1.5, 1.3),
    "noodles": ("pkt", 15, 9, 1.0), "soap": ("pc", 38, 2, 1.2), "biscuits": ("pkt", 10, 12, 1.4),
    "ghee": ("kg", 640, 0.4, 3.0), "besan": ("kg", 95, 1.0, 2.6), "rava": ("kg", 50, 1.2, 2.0),
    "maida": ("kg", 45, 0.8, 2.4), "eggs": ("dozen", 84, 2, 0.9), "salt": ("kg", 25, 1.5, 1.0),
}

CUSTOMERS = {  # name: (credit visits per week, avg pay gap days, reliability 0..1)
    "Patil Kaku": (3, 10, 0.95), "Sharma Ji": (2, 14, 0.9), "Kulkarni Aaji": (1.5, 30, 0.85),
    "Shinde Mama": (4, 25, 0.55), "Jadhav Bhau": (2.5, 45, 0.35), "Deshmukh Vahini": (2, 12, 0.92),
    "Khan Bhai": (1.5, 20, 0.8), "More Kaka": (3, 40, 0.4), "Pawar Tai": (2, 15, 0.88),
    "Gaikwad Sir": (1, 30, 0.75), "Joshi Kaku": (2, 9, 0.97), "Sayyed Chacha": (2, 35, 0.5),
    "Bhosale Dada": (3.5, 50, 0.3), "Wagh Vahini": (1.5, 18, 0.82), "Rathod Bhai": (2, 28, 0.6),
}

END = date(2026, 10, 12)
START = END - timedelta(days=400)


def fest_boost(d: date) -> float:
    # demand climbs through the 12 days before a festival, peaking at 2x the day before
    near = [(f - d).days for f in FESTIVALS if 0 <= (f - d).days <= 12]
    return 1.0 + (12 - min(near)) / 12.0 if near else 1.0


def main(wipe: bool, seed: int = 7):
    random.seed(seed)
    with db.connect() as con:
        con.execute("DELETE FROM entries WHERE source='demo'")
        if wipe:
            con.execute("DELETE FROM customers WHERE id NOT IN (SELECT DISTINCT customer_id FROM entries WHERE customer_id IS NOT NULL)")
            print("demo data removed"); return
        cust_ids = {n: db.get_or_create_customer(con, n) for n in CUSTOMERS}
        balance = {n: 0.0 for n in CUSTOMERS}
        next_pay = {n: START + timedelta(days=random.randint(3, v[1])) for n, v in CUSTOMERS.items()}
        rows = 0
        d = START
        while d <= END:
            dow = d.weekday()
            wk = 1.25 if dow in (5, 6) else 1.0
            sal = 1.2 if d.day <= 7 else 1.0
            fb = fest_boost(d)
            # cash sales
            for item, (unit, price, base, fmul) in ITEMS.items():
                mult = wk * sal * (1 + (fb - 1) * max(fmul - 1, 0))
                qty = max(0, random.gauss(base * mult, base * 0.25))
                if qty < 0.2:
                    continue
                qty = round(qty * 2) / 2
                ts = datetime(d.year, d.month, d.day, random.randint(7, 21), random.randint(0, 59)).isoformat()
                con.execute("INSERT INTO entries(ts,kind,item,qty,unit,amount,source) VALUES (?,?,?,?,?,?,?)",
                            (ts, "sale", item, qty, unit, round(qty * price), "demo")); rows += 1
            # udhaar visits
            for name, (per_week, gap, rel) in CUSTOMERS.items():
                if random.random() < per_week / 7 * (1.3 if fb > 1 else 1):
                    item = random.choice(list(ITEMS))
                    unit, price, base, _ = ITEMS[item]
                    qty = max(0.5, round(random.uniform(0.5, 3) * 2) / 2)
                    amt = round(qty * price)
                    ts = datetime(d.year, d.month, d.day, random.randint(8, 21), random.randint(0, 59)).isoformat()
                    con.execute("INSERT INTO entries(ts,customer_id,kind,item,qty,unit,amount,source) VALUES (?,?,?,?,?,?,?,?)",
                                (ts, cust_ids[name], "credit", item, qty, unit, amt, "demo"))
                    balance[name] += amt; rows += 1
                if d >= next_pay[name] and balance[name] > 0:
                    if random.random() < rel:
                        amt = round(balance[name] * random.uniform(0.6, 1.0))
                    else:
                        amt = round(balance[name] * random.uniform(0.0, 0.25))
                    if amt > 0:
                        ts = datetime(d.year, d.month, d.day, random.randint(9, 20), 0).isoformat()
                        con.execute("INSERT INTO entries(ts,customer_id,kind,amount,source) VALUES (?,?,?,?,?)",
                                    (ts, cust_ids[name], "payment", amt, "demo"))
                        balance[name] -= amt; rows += 1
                    next_pay[name] = d + timedelta(days=max(3, int(random.gauss(gap, gap * 0.3))))
            d += timedelta(days=1)
    print(f"wrote {rows} demo entries ({START} → {END})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--wipe", action="store_true")
    main(ap.parse_args().wipe)

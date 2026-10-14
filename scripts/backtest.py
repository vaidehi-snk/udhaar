"""Honest backtest: hide the future, predict it, compare with what actually happened.

    python scripts/backtest.py                 # TabPFN (API if TABPFN_TOKEN, else local) vs baselines
    python scripts/backtest.py --skip-tabpfn   # baselines only

Writes data/backtest.json (shown on the "How it works" page) and prints a table for your post.
"""
import argparse
import warnings
import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import db, predict  # noqa: E402

warnings.filterwarnings("ignore", category=DeprecationWarning)

OUT = db.DB_PATH.parent / "backtest.json"

# Forecast origins: two festival build-ups and one ordinary fortnight.
RESTOCK_CUTS = [
    (date(2026, 6, 1), 14, "Ordinary fortnight (June)"),
    (date(2026, 8, 28), 18, "Ganesh Chaturthi build-up"),
    (date(2026, 9, 24), 18, "Navratri build-up"),
]


def load():
    with db.connect() as con:
        df = pd.read_sql_query("SELECT * FROM entries", con)
        names = {r["id"]: r["name"] for r in con.execute("SELECT id,name FROM customers")}
    return df, names


def wape(pred, act):
    return float(np.abs(pred - act).sum() / max(act.sum(), 1e-9))


def restock_bt(df, methods):
    daily = predict._daily_item_frame(df)
    rows = []
    for cut, h, label in RESTOCK_CUTS:
        past = df[pd.to_datetime(df["ts"]).dt.date < cut]
        future = daily[(daily["day"] >= cut) & (daily["day"] < cut + timedelta(days=h))]
        act = future.pivot(index="item", columns="day", values="qty").fillna(0)
        row = {"window": label, "from": cut.isoformat(), "days": h}
        hist = predict._daily_item_frame(past)
        naive = np.array([[hist[hist["item"] == it]["qty"].tail(28).mean()] * h for it in act.index])
        row["naive"] = round(wape(naive, act.to_numpy()), 3)
        for m in methods:
            t0 = time.perf_counter()
            r = predict.restock_forecast(past, today=cut, horizon=h, backend=m)
            P = {i["item"]: i["daily"] for i in r["items"]}
            pred = np.array([P.get(it, [0] * h) for it in act.index])
            row[m] = round(wape(pred, act.to_numpy()), 3)
            row[m + "_engine"] = r["engine"]
            row[m + "_s"] = round(time.perf_counter() - t0, 1)
        rows.append(row)
        print("restock", row)
    return rows


def risk_bt(df, names, methods):
    from sklearn.metrics import roc_auc_score
    e = df[df["customer_id"].notna() & df["kind"].isin(["credit", "payment"])].copy()
    e["ts"] = pd.to_datetime(e["ts"])
    end = e["ts"].max() - pd.Timedelta(days=30)
    cuts = pd.date_range(end - pd.Timedelta(days=168), end, freq="14D")
    y_true, scores = [], {m: [] for m in methods + ["rule"]}
    engines = {}
    for T in cuts:
        past = df[pd.to_datetime(df["ts"]) < T]
        fut = e[(e["ts"] >= T) & (e["ts"] < T + pd.Timedelta(days=30)) & (e["kind"] == "payment")]
        paid = fut.groupby("customer_id")["amount"].sum()
        snap = predict._cust_snapshot(e[e["ts"] < T], T)
        if snap.empty:
            continue
        labels = {int(c): int(paid.get(c, 0) < 0.5 * d) for c, d in zip(snap["customer_id"], snap["due"])}
        res = {}
        for m in methods:
            r = predict.udhaar_risk(past, names, today=T, backend=m)
            engines[m] = r["engine"]
            res[m] = {c["customer"]: c["risk"] for c in r["customers"]}
        for _, s in snap.iterrows():
            cid = int(s["customer_id"]); nm = names.get(cid)
            if any(nm not in res[m] for m in methods):
                continue
            y_true.append(labels[cid])
            for m in methods:
                scores[m].append(res[m][nm])
            # what a shopkeeper does today: worry once someone hasn't paid for a month
            scores["rule"].append(min(s["days_since_payment"] / 60, 1.0))
    out = {"n": len(y_true), "late_rate": round(float(np.mean(y_true)), 2)}
    for m, sc in scores.items():
        sc = np.array(sc); yt = np.array(y_true)
        top = np.argsort(-sc)[: max(1, int(yt.sum()))]  # flag as many people as are really late
        out[m] = {"auc": round(float(roc_auc_score(yt, sc)), 3),
                  "precision_at_k": round(float(yt[top].mean()), 3), "engine": engines.get(m, "rule")}
    print("risk", out)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-tabpfn", action="store_true")
    a = ap.parse_args()
    methods = ["baseline"] + ([] if a.skip_tabpfn else ["auto"])
    df, names = load()
    if df.empty:
        sys.exit("No data. Run: python scripts/make_demo_data.py")
    result = {"restock": restock_bt(df, methods), "risk": risk_bt(df, names, methods),
              "methods": methods, "ran_at": pd.Timestamp.now().isoformat(timespec="seconds"),
              "data": "demo" if (df["source"] == "demo").mean() > 0.5 else "shop"}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2))
    print(f"\nwrote {OUT}\n")
    print("| Window | Shopkeeper guess (last 4 wks avg) | Gradient boosting | TabPFN |")
    print("|---|---|---|---|")
    for r in result["restock"]:
        print(f"| {r['window']} | {r['naive']:.0%} | {r['baseline']:.0%} | {r.get('auto', float('nan')):.0%} |")
    print("(WAPE: lower is better)\n")
    rk = result["risk"]
    print("| Late-payment model | AUC | Precision@k |\n|---|---|---|")
    for m, lbl in [("rule", "'Not paid in a month' rule"), ("baseline", "Gradient boosting"), ("auto", "TabPFN")]:
        if m in rk:
            print(f"| {lbl} | {rk[m]['auc']:.2f} | {rk[m]['precision_at_k']:.0%} |")

"""TabPFN on the shop's own ledger.

1. Restock: forecast each item's demand for the next 14 days (festival-aware).
2. Udhaar risk: which credit accounts are likely NOT to be paid back within 30 days.

Backends, in order:
  - tabpfn_client (TabPFN-3.5 via Prior Labs API) if TABPFN_TOKEN is set.
    Only anonymous numeric features are sent: no names, no item text.
  - tabpfn (open weights, runs on the laptop) if installed.
  - sklearn HistGradientBoosting as a labelled last-resort fallback.
"""
from __future__ import annotations

import os
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

# Festivals that move kirana demand in Maharashtra. Verify dates each year.
FESTIVALS = [
    date(2025, 9, 22),   # Navratri start 2025
    date(2025, 10, 21),  # Diwali (Lakshmi Puja) 2025
    date(2026, 3, 19),   # Gudi Padwa 2026
    date(2026, 9, 14),   # Ganesh Chaturthi 2026
    date(2026, 10, 11),  # Navratri start 2026
    date(2026, 11, 8),   # Diwali (Lakshmi Puja) 2026
]


def _baseline(kind: str):
    from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
    return HistGradientBoostingRegressor() if kind == "reg" else HistGradientBoostingClassifier()


def _backend(kind: str, prefer: str = "auto"):
    """Return (model, engine_name). prefer: auto | api | local | baseline."""
    token = os.environ.get("TABPFN_TOKEN")
    if prefer in ("auto", "api") and token:
        try:
            import tabpfn_client as tc
            if hasattr(tc, "set_access_token"):
                tc.set_access_token(token)
            m = tc.TabPFNRegressor() if kind == "reg" else tc.TabPFNClassifier()
            return m, "TabPFN-3.5 (Prior Labs API)"
        except Exception as e:
            print(f"[udhaar] TabPFN API unavailable: {e!r}")
    elif prefer in ("auto", "api"):
        print("[udhaar] TABPFN_TOKEN not set in this terminal")
    if prefer in ("auto", "local") and os.environ.get("UDHAAR_NO_LOCAL_TABPFN") != "1":
        try:
            import tabpfn as tl
            m = tl.TabPFNRegressor() if kind == "reg" else tl.TabPFNClassifier()
            return m, "TabPFN (local, open weights)"
        except Exception as e:
            print(f"[udhaar] local tabpfn unavailable: {e!r}")
    return _baseline(kind), ("gradient boosting baseline" if prefer == "baseline"
                             else "fallback (gradient boosting — install tabpfn)")


def engine_name() -> str:
    """Which backend auto mode would pick, without building a model."""
    if os.environ.get("TABPFN_TOKEN"):
        try:
            import tabpfn_client  # noqa: F401
            return "TabPFN-3.5 (Prior Labs API)"
        except Exception:
            pass
    try:
        import tabpfn  # noqa: F401
        return "TabPFN (local, open weights)"
    except Exception:
        return "fallback (gradient boosting — install tabpfn)"


def _days_to_festival(d: date) -> int:
    ahead = [(f - d).days for f in FESTIVALS if (f - d).days >= 0]
    return min(ahead) if ahead else 60


# ------------------------------------------------------------------ restock
def _daily_item_frame(entries: pd.DataFrame) -> pd.DataFrame:
    """Quantity sold per item per day (sale + credit both take goods off the shelf)."""
    e = entries[entries["kind"].isin(["sale", "credit"]) & entries["item"].notna()].copy()
    e["day"] = pd.to_datetime(e["ts"]).dt.date
    e["qty"] = e["qty"].fillna(1.0)
    g = e.groupby(["item", "day"])["qty"].sum().reset_index()
    out = []
    for item, grp in g.groupby("item"):
        full = pd.date_range(grp["day"].min(), max(grp["day"].max(), e["day"].max()), freq="D").date
        s = grp.set_index("day")["qty"].reindex(full, fill_value=0.0)
        out.append(pd.DataFrame({"item": item, "day": full, "qty": s.values}))
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame(columns=["item", "day", "qty"])


def _features(item_code: int, target: date, h: int, hist: np.ndarray) -> list[float]:
    """Direct multi-horizon features: everything is known at the forecast origin."""
    last7 = hist[-7:] if len(hist) else np.zeros(1)
    last28 = hist[-28:] if len(hist) else np.zeros(1)
    same_dow = hist[len(hist) - 7 + (h - 1) % 7::-7][:4] if len(hist) >= 7 else last7
    return [item_code, h, target.weekday(), target.day, int(target.day <= 7),  # salary week
            min(_days_to_festival(target), 45), float(last7.mean()), float(last28.mean()),
            float(np.mean(same_dow)) if len(same_dow) else float(last7.mean())]


def restock_forecast(entries: pd.DataFrame, today: date | None = None, horizon: int | None = None,
                     max_rows: int = 6000, seed: int = 0, backend: str = "auto") -> dict:
    """Forecast daily demand per item from today up to the next festival (max 30 days),
    in ONE batched TabPFN call. Reports the coming week and the festival fortnight."""
    daily = _daily_item_frame(entries)
    if daily.empty:
        return {"engine": None, "items": []}
    today = today or daily["day"].max() + timedelta(days=1)
    nf = min((f for f in FESTIVALS if f >= today), default=None)
    if horizon is None:
        horizon = min(max((nf - today).days + 1, 14), 30) if nf else 14
    items = sorted(daily["item"].unique())
    codes = {it: i for i, it in enumerate(items)}
    rng = np.random.default_rng(seed)

    series, X, y = {}, [], []
    for it, grp in daily.groupby("item"):
        grp = grp.sort_values("day")
        q, days = grp["qty"].to_numpy(), grp["day"].tolist()
        series[it] = q
        for t in range(28, len(q) - 1, 2):                      # forecast origins
            for h in rng.choice(np.arange(1, horizon + 1), size=3, replace=False):
                if t + h - 1 < len(q):
                    X.append(_features(codes[it], days[t + h - 1], int(h), q[:t])); y.append(q[t + h - 1])
    if len(X) < 50:
        return {"engine": None, "items": []}
    X, y = np.array(X, dtype=float), np.array(y, dtype=float)
    if len(X) > max_rows:  # keep TabPFN's context small: favour recent history
        w = np.linspace(0.3, 1.0, len(X)); w /= w.sum()
        idx = np.sort(rng.choice(len(X), size=max_rows, replace=False, p=w))
        X, y = X[idx], y[idx]

    model, engine = _backend("reg", backend)
    model.fit(X, y)
    Q = [_features(codes[it], today + timedelta(days=h - 1), h, series[it])
         for it in items for h in range(1, horizon + 1)]
    P = np.clip(np.asarray(model.predict(np.array(Q, dtype=float)), dtype=float), 0, None).reshape(len(items), horizon)

    fest_lo = max((nf - today).days - 13, 0) if nf and (nf - today).days < horizon else None
    results = []
    for it, preds in zip(items, P):
        base_daily = float(np.mean(series[it][-28:]))
        week = float(preds[:7].sum())
        row = {"item": it, "next_7d": round(week, 1), "normal_7d": round(base_daily * 7, 1),
               "week_change_pct": round((week / (base_daily * 7) - 1) * 100) if base_daily else None,
               "daily": [round(float(p), 2) for p in preds]}
        if fest_lo is not None:
            fest = float(preds[fest_lo:fest_lo + 14].sum())
            row.update(festival_14d=round(fest, 1), normal_14d=round(base_daily * 14, 1),
                       festival_change_pct=round((fest / (base_daily * 14) - 1) * 100) if base_daily else None)
        results.append(row)
    key = "festival_change_pct" if fest_lo is not None else "week_change_pct"
    results.sort(key=lambda r: r.get(key) or 0, reverse=True)
    return {"engine": engine, "from": today.isoformat(), "horizon": horizon, "train_rows": int(len(y)),
            "next_festival": nf.isoformat() if nf else None,
            "days_to_festival": (nf - today).days if nf else None, "items": results}


# ------------------------------------------------------------------ udhaar risk
def _cust_snapshot(e: pd.DataFrame, at: pd.Timestamp) -> pd.DataFrame:
    past = e[e["ts"] < at]
    rows = []
    for cid, g in past.groupby("customer_id"):
        cr = g[g["kind"] == "credit"]; pay = g[g["kind"] == "payment"]
        due = cr["amount"].sum() - pay["amount"].sum()
        if due <= 0 or cr.empty:
            continue
        last_pay = pay["ts"].max() if not pay.empty else cr["ts"].min()
        recent = cr[cr["ts"] >= at - pd.Timedelta(days=30)]
        gaps = pay["ts"].sort_values().diff().dt.days.dropna()
        rows.append({
            "customer_id": cid, "due": due,
            "days_since_payment": (at - last_pay).days,
            "days_since_first_credit": (at - cr["ts"].min()).days,
            "credits_30d": len(recent), "credit_amt_30d": recent["amount"].sum(),
            "n_payments": len(pay),
            "repay_ratio": pay["amount"].sum() / max(cr["amount"].sum(), 1),
            "avg_pay_gap": gaps.mean() if len(gaps) else 90.0,
            "credit_sum": cr["amount"].sum(), "pay_sum": pay["amount"].sum(),   # for what-if, not features
        })
    return pd.DataFrame(rows)


RISK_FEATURES = ["due", "days_since_payment", "days_since_first_credit", "credits_30d",
                 "credit_amt_30d", "n_payments", "repay_ratio", "avg_pay_gap"]


def udhaar_risk(entries: pd.DataFrame, names: dict[int, str], today: pd.Timestamp | None = None,
                backend: str = "auto") -> dict:
    e = entries[entries["customer_id"].notna() & entries["kind"].isin(["credit", "payment"])].copy()
    if e.empty:
        return {"engine": None, "customers": []}
    e["ts"] = pd.to_datetime(e["ts"])
    today = today or e["ts"].max().normalize() + pd.Timedelta(days=1)

    # Training: weekly snapshots in the past; label = did they pay back >= half of due in next 30 days?
    X, y = [], []
    start = e["ts"].min() + pd.Timedelta(days=45)
    for at in pd.date_range(start, today - pd.Timedelta(days=30), freq="7D"):
        snap = _cust_snapshot(e, at)
        if snap.empty:
            continue
        fut = e[(e["ts"] >= at) & (e["ts"] < at + pd.Timedelta(days=30)) & (e["kind"] == "payment")]
        paid = fut.groupby("customer_id")["amount"].sum()
        snap["late"] = [int(paid.get(c, 0) < 0.5 * d) for c, d in zip(snap["customer_id"], snap["due"])]
        X.append(snap[RISK_FEATURES]); y.append(snap["late"])
    now = _cust_snapshot(e, today)
    if not X or now.empty:
        return {"engine": None, "customers": []}
    X = pd.concat(X).to_numpy(dtype=float); y = pd.concat(y).to_numpy()
    if len(set(y)) < 2:
        return {"engine": None, "customers": []}

    model, engine = _backend("clf", backend)
    model.fit(X, y)
    proba = model.predict_proba(now[RISK_FEATURES].to_numpy(dtype=float))[:, 1]
    out = []
    for (_, r), p in zip(now.iterrows(), proba):
        out.append({"customer": names.get(int(r["customer_id"]), f"#{int(r['customer_id'])}"),
                    "due": round(float(r["due"])), "days_since_payment": int(r["days_since_payment"]),
                    "risk": round(float(p), 2),
                    "features": {k: round(float(r[k]), 2) for k in RISK_FEATURES},
                    "band": "high" if p >= 0.6 else "watch" if p >= 0.35 else "ok"})
    out.sort(key=lambda r: r["risk"], reverse=True)
    # keep the fitted model: the agent's what-if and credit-limit tools reuse it without refitting
    _risk_state.update(model=model, engine=engine, now=now.copy(), names=dict(names), entries=e)
    return {"engine": engine, "as_of": today.date().isoformat(), "train_rows": int(len(y)),
            "customers": out}


# ------------------------------------------------------------------ agent tools on the risk model
_risk_state: dict = {}
BAND_HIGH, BAND_WATCH = 0.6, 0.35


def _risk_row(name: str):
    st = _risk_state
    if not st:
        return None
    cid = next((k for k, v in st["names"].items() if v.lower() == (name or "").lower()), None)
    r = st["now"][st["now"]["customer_id"] == cid]
    return None if r.empty else r.iloc[0]


def _scenario(r, extra: float = 0.0, days: int = 0) -> list[float]:
    """The same customer, `days` from now with no payment, after `extra` more on udhaar."""
    keep = max(0.0, 1 - days / 30)                     # the 30-day window slides forward
    s = {"due": r["due"] + extra,
         "days_since_payment": r["days_since_payment"] + days,
         "days_since_first_credit": r["days_since_first_credit"] + days,
         "credits_30d": r["credits_30d"] * keep + (1 if extra > 0 else 0),
         "credit_amt_30d": r["credit_amt_30d"] * keep + extra,
         "n_payments": r["n_payments"],
         "repay_ratio": r["pay_sum"] / max(r["credit_sum"] + extra, 1),
         "avg_pay_gap": r["avg_pay_gap"]}
    return [float(s[k]) for k in RISK_FEATURES]


def _proba(rows: list[list[float]]) -> np.ndarray:
    return np.asarray(_risk_state["model"].predict_proba(np.array(rows, dtype=float))[:, 1], dtype=float)


def what_if(name: str, extra: float = 0.0, days: int = 0) -> dict | None:
    """Re-score one customer under a scenario, in one TabPFN call (now vs then)."""
    r = _risk_row(name)
    if r is None:
        return None
    p = _proba([_scenario(r), _scenario(r, extra, days)])
    p[1] = max(p[1], p[0])   # prior: more credit or a longer silence never makes someone SAFER
    return {"customer": _risk_state["names"][int(r["customer_id"])], "due": round(float(r["due"])),
            "extra": round(extra), "days": int(days), "now": round(float(p[0]), 2),
            "then": round(float(p[1]), 2), "engine": _risk_state["engine"]}


def _monthly_capacity(cid: int) -> float:
    """The most this customer has ever paid back within 30 days."""
    e = _risk_state["entries"]
    pay = e[(e["customer_id"] == cid) & (e["kind"] == "payment")].set_index("ts")["amount"].sort_index()
    return float(pay.rolling("30D").sum().max()) if len(pay) else 0.0


def credit_limit(name: str) -> dict | None:
    """How much more udhaar can I safely give? Two limits, the tighter one wins:
    - capacity: they have never paid back more than X in a month, so dues above X pile up;
    - risk: TabPFN scores a ladder of 'what if I give Y more' in ONE batched call, and the
      limit is the last step before their late-payment risk crosses the line."""
    r = _risk_row(name)
    if r is None:
        return None
    cid, due = int(r["customer_id"]), float(r["due"])
    cap = _monthly_capacity(cid)
    headroom = max(cap - due, 0.0)
    top = max(500.0, 1.5 * headroom)
    grid = sorted({0.0, *[float(round(v / 50) * 50) for v in np.linspace(0, top, 16)]})
    p = np.maximum.accumulate(_proba([_scenario(r, g) for g in grid]))   # same prior along the ladder
    base = float(p[0])
    line = BAND_WATCH if base < BAND_WATCH else BAND_HIGH
    over = next((i for i, v in enumerate(p) if v >= line), None)
    risk_limit = grid[-1] if over is None else grid[max(over - 1, 0)]
    if base >= BAND_HIGH:
        limit, verdict = 0, "collect"          # already likely to pay late: collect before giving more
    else:
        room = headroom if line == BAND_WATCH else headroom / 2   # already on watch: be conservative
        limit = int(min(risk_limit, room) // 50 * 50)
        verdict = ("ok" if line == BAND_WATCH else "small") if limit > 0 else "full"
    return {"customer": _risk_state["names"][cid], "due": round(due), "risk_now": round(base, 2),
            "limit": limit, "verdict": verdict, "line": line,
            "capacity": round(cap), "binding": "capacity" if limit < risk_limit else "risk",
            "curve": [[int(g), round(float(v), 2)] for g, v in zip(grid, p)],
            "engine": _risk_state["engine"]}


# ------------------------------------------------------------------ price check (anomaly)
_price: dict = {}


def price_check(entries: pd.DataFrame, item: str, qty: float, amount: float, backend: str = "auto") -> dict | None:
    """Does this amount look like what THIS shop charges for this item and quantity?
    TabPFN regresses price-per-unit from the shop's own recent entries (item, quantity, unit).
    Catches the classic speech slip: '920' heard for '92'. Returns None if there's too little history."""
    if not item or not qty or not amount or qty <= 0:
        return None
    e = entries[entries["kind"].isin(["sale", "credit"]) & entries["item"].notna()
                & (entries["qty"] > 0) & (entries["amount"] > 0)].tail(2000)
    if (e["item"] == item).sum() < 5:
        return None
    t0 = datetime.now()
    key = (len(entries) // 100, backend)
    if _price.get("key") != key:
        items = sorted(e["item"].unique())
        units = sorted(e["unit"].fillna("").unique())
        codes, ucodes = {it: i for i, it in enumerate(items)}, {u: i for i, u in enumerate(units)}
        X = np.column_stack([e["item"].map(codes), e["qty"], e["unit"].fillna("").map(ucodes)]).astype(float)
        y = (e["amount"] / e["qty"]).to_numpy(dtype=float)
        model, engine = _backend("reg", backend)
        model.fit(X, y)
        _price.update(key=key, model=model, engine=engine, codes=codes, ucodes=ucodes,
                      units=e.groupby("item")["unit"].agg(lambda u: u.mode().iat[0] if len(u.mode()) else None).to_dict())
    unit = _price["units"].get(item) or ""
    x = np.array([[_price["codes"][item], qty, _price["ucodes"].get(unit, 0)]], dtype=float)
    per_unit = float(np.asarray(_price["model"].predict(x)).ravel()[0])
    expected = round(per_unit * qty)
    ratio = amount / max(expected, 1)
    odd = (ratio > 2.2 or ratio < 0.45) and abs(amount - expected) >= 20
    return {"item": item, "qty": qty, "amount": round(amount), "expected": expected, "odd": bool(odd),
            "engine": _price["engine"], "ms": round((datetime.now() - t0).total_seconds() * 1000)}

import os
import tempfile

os.environ["UDHAAR_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")
os.environ["OLLAMA_URL"] = "http://127.0.0.1:9"  # force the rules fallback in tests

import pandas as pd  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import db, parser, predict  # noqa: E402
from app.main import app  # noqa: E402
from scripts import make_demo_data  # noqa: E402


def test_rules_credit_multi_item():
    p = parser.parse_with_rules("Patil kaku, don kilo sakhar ani ek litre tel, 210 udhaar")
    assert p["kind"] == "credit" and p["customer"] == "Patil Kaku" and p["total"] == 210
    assert [(i["name"], i["qty"], i["unit"]) for i in p["items"]] == [("sugar", 2, "kg"), ("oil", 1, "l")]


def test_rules_payment_and_sale():
    assert parser.parse_with_rules("Sharma ji ne 500 jama kiye") == {
        "kind": "payment", "customer": "Sharma Ji", "items": [], "total": 500}
    s = parser.parse_with_rules("teen packet maggi 45 rupaye")
    assert s["kind"] == "sale" and s["customer"] is None and s["items"][0]["amount"] == 45


def test_normalise_cleans_model_output():
    p = parser.normalise({"kind": "udhaar", "customer": "  patil   kaku ", "items": [
        {"name": "Sakhar", "qty": "2", "unit": "kilo"}, {"qty": 1}], "total": None})
    assert p == {"kind": "sale", "customer": "Patil Kaku",
                 "items": [{"name": "sugar", "qty": 2.0, "unit": "kg", "amount": None}], "total": None}


def test_ledger_balance():
    with db.connect() as con:
        db.add_entries(con, {"kind": "credit", "customer": "Test Kaka", "items": [], "total": 300}, "x")
        db.add_entries(con, {"kind": "payment", "customer": "test kaka", "items": [], "total": 120}, "y")
        b = {r["name"]: r["due"] for r in db.balances(con)}
    assert b["Test Kaka"] == 180


def test_api_and_predictions_on_demo_data():
    make_demo_data.main(wipe=False)
    c = TestClient(app)
    r = c.post("/api/text", json={"text": "More kaka ek kilo tup 640 udhaar"}).json()
    assert r["parsed"]["kind"] == "credit" and r["parsed"]["items"][0]["name"] == "ghee"
    ins = c.get("/api/insights").json()
    top = [i["item"] for i in ins["restock"]["items"][:6]]
    assert {"ghee", "maida", "besan", "sugar"} & set(top), top  # Diwali items rise
    bands = {x["customer"]: x["band"] for x in ins["risk"]["customers"]}
    assert bands.get("Bhosale Dada") == "high"
    assert c.get("/").status_code == 200


def test_detail_summary_backtest_endpoints():
    c = TestClient(app)
    cid = c.get("/api/ledger").json()["balances"][0]["id"]
    d = c.get(f"/api/customer/{cid}").json()
    assert d["series"] and d["n_entries"] >= len(d["series"]) and "features" in (d["risk"] or {"features": 1})
    assert c.get("/api/summary").json()["weeks"]
    assert "available" in c.get("/api/backtest").json()
    assert c.get("/static/app.js").status_code == 200 and c.get("/static/fonts/geist-sans-latin-400-normal.woff2").status_code == 200


def test_ask_routes_entries_and_questions():
    c = TestClient(app)
    q = c.post("/api/ask", json={"text": "Who owes the most?"}).json()
    assert q["mode"] == "answer" and q["intent"] == "top_due" and q["rows"]
    q = c.post("/api/ask", json={"text": "how much sugar next week?"}).json()
    assert q["intent"] == "item_forecast" and "sugar" in q["answer"]
    q = c.post("/api/ask", json={"text": "Bhosale dada kiti baki"}).json()
    assert q["intent"] == "customer_due" and "Bhosale Dada" in q["answer"]
    e = c.post("/api/ask", json={"text": "Sharma ji ne 500 jama kiye"}).json()
    assert e["mode"] == "entry" and e["parsed"]["kind"] == "payment"
    b = c.get("/api/brief").json()
    assert {x["kind"] for x in b["cards"]} >= {"collect", "order"}
    assert "Hello" in c.get("/api/order").json()["text"]

"""SQLite ledger. One file on the shop's own laptop — nothing leaves it."""
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
import os

DB_PATH = Path(os.environ.get("UDHAAR_DB", Path(__file__).resolve().parent.parent / "data" / "udhaar.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT UNIQUE NOT NULL,
  phone TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS entries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  customer_id INTEGER REFERENCES customers(id),
  kind TEXT NOT NULL CHECK (kind IN ('sale','credit','payment')),
  item TEXT,
  qty REAL,
  unit TEXT,
  amount REAL NOT NULL DEFAULT 0,
  raw_text TEXT,
  source TEXT DEFAULT 'voice'
);
CREATE INDEX IF NOT EXISTS idx_entries_ts ON entries(ts);
CREATE INDEX IF NOT EXISTS idx_entries_cust ON entries(customer_id);
"""


@contextmanager
def connect(path: Path | None = None):
    p = Path(path or DB_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(p)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    try:
        yield con
        con.commit()
    finally:
        con.close()


def get_or_create_customer(con, name: str | None) -> int | None:
    if not name:
        return None
    name = " ".join(name.strip().split()).title()
    row = con.execute("SELECT id FROM customers WHERE lower(name)=lower(?)", (name,)).fetchone()
    if row:
        return row["id"]
    cur = con.execute("INSERT INTO customers(name, created_at) VALUES (?,?)",
                      (name, datetime.now().isoformat(timespec="seconds")))
    return cur.lastrowid


def add_entries(con, parsed: dict, raw_text: str, source: str = "voice", ts: str | None = None) -> list[int]:
    """Write a parsed utterance. Items become one row each; payment is its own row."""
    ts = ts or datetime.now().isoformat(timespec="seconds")
    cid = get_or_create_customer(con, parsed.get("customer"))
    kind = parsed.get("kind", "sale")
    ids = []
    items = parsed.get("items") or []
    if kind == "payment":
        cur = con.execute(
            "INSERT INTO entries(ts,customer_id,kind,amount,raw_text,source) VALUES (?,?,?,?,?,?)",
            (ts, cid, "payment", float(parsed.get("total") or 0), raw_text, source))
        return [cur.lastrowid]
    total = float(parsed.get("total") or 0)
    priced = sum(float(i.get("amount") or 0) for i in items)
    for n, it in enumerate(items):
        amt = float(it.get("amount") or 0)
        # if only a total was spoken, put it on the first item
        if priced == 0 and n == 0:
            amt = total
        cur = con.execute(
            "INSERT INTO entries(ts,customer_id,kind,item,qty,unit,amount,raw_text,source) VALUES (?,?,?,?,?,?,?,?,?)",
            (ts, cid, kind, (it.get("name") or "").strip().lower() or None,
             it.get("qty"), it.get("unit"), amt, raw_text, source))
        ids.append(cur.lastrowid)
    if not items:
        cur = con.execute(
            "INSERT INTO entries(ts,customer_id,kind,amount,raw_text,source) VALUES (?,?,?,?,?,?)",
            (ts, cid, kind, total, raw_text, source))
        ids.append(cur.lastrowid)
    return ids


def balances(con) -> list[dict]:
    rows = con.execute("""
      SELECT c.id, c.name,
        COALESCE(SUM(CASE WHEN e.kind='credit' THEN e.amount END),0) AS credit,
        COALESCE(SUM(CASE WHEN e.kind='payment' THEN e.amount END),0) AS paid,
        MAX(CASE WHEN e.kind='credit' THEN e.ts END) AS last_credit,
        MAX(CASE WHEN e.kind='payment' THEN e.ts END) AS last_payment
      FROM customers c LEFT JOIN entries e ON e.customer_id=c.id
      GROUP BY c.id ORDER BY (credit-paid) DESC""").fetchall()
    return [dict(r) | {"due": round(r["credit"] - r["paid"], 2)} for r in rows]


def recent(con, limit=30) -> list[dict]:
    rows = con.execute("""
      SELECT e.*, c.name AS customer FROM entries e LEFT JOIN customers c ON c.id=e.customer_id
      ORDER BY e.ts DESC, e.id DESC LIMIT ?""", (limit,)).fetchall()
    return [dict(r) for r in rows]


def undo(con, entry_id: int) -> None:
    con.execute("DELETE FROM entries WHERE id=?", (entry_id,))

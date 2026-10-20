"""SQLite store: every posting ever seen (so criteria changes can be re-applied offline)."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "postings.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
  url TEXT PRIMARY KEY, source TEXT, title TEXT, org TEXT, location TEXT, snippet TEXT,
  fields TEXT, site_tags TEXT, posted TEXT, deadline TEXT, rolling INTEGER DEFAULT 0,
  body TEXT, first_seen TEXT, last_seen TEXT, source_opts TEXT, also_on TEXT
);
CREATE TABLE IF NOT EXISTS runs (id INTEGER PRIMARY KEY AUTOINCREMENT, started TEXT, finished TEXT, summary TEXT);
CREATE TABLE IF NOT EXISTS health (run_id INTEGER, source TEXT, ok INTEGER, n_items INTEGER, error TEXT, verified INTEGER);
"""
COLS = ["url", "source", "title", "org", "location", "snippet", "fields", "site_tags", "posted", "deadline",
        "rolling", "body", "first_seen", "last_seen", "source_opts", "also_on"]


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    p = Path(path) if path else DB_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(p)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    cols = {r[1] for r in con.execute("PRAGMA table_info(items)")}
    if "body_checked" not in cols:            # added later: when the full page was last read
        con.execute("ALTER TABLE items ADD COLUMN body_checked TEXT")
    return con


def upsert(con: sqlite3.Connection, it: dict, today: str) -> bool:
    """Insert or refresh a listing.  Returns True when the URL is new."""
    row = con.execute("SELECT url, body FROM items WHERE url=?", (it["url"],)).fetchone()
    opts = json.dumps(it.get("source_opts") or {})
    if row is None:
        con.execute(
            "INSERT INTO items (url,source,title,org,location,snippet,fields,site_tags,posted,deadline,rolling,body,first_seen,last_seen,source_opts,also_on)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (it["url"], it.get("source"), it.get("title"), it.get("org"), it.get("location"), it.get("snippet"),
             it.get("fields"), it.get("site_tags"), it.get("posted"), it.get("deadline"), int(bool(it.get("rolling"))),
             it.get("body"), today, today, opts, "[]"))
        return True
    con.execute("UPDATE items SET last_seen=?, title=COALESCE(?,title), org=COALESCE(?,org), location=COALESCE(?,location),"
                " snippet=COALESCE(?,snippet), fields=COALESCE(?,fields), deadline=COALESCE(?,deadline), posted=COALESCE(?,posted),"
                " rolling=MAX(rolling,?) WHERE url=?",
                (today, it.get("title"), it.get("org"), it.get("location"), it.get("snippet"), it.get("fields"),
                 it.get("deadline"), it.get("posted"), int(bool(it.get("rolling"))), it["url"]))
    return False


def set_body(con, url: str, body: str, deadline: str | None, rolling: bool, location: str | None = None, org: str | None = None,
             checked: str | None = None):
    con.execute("UPDATE items SET body=?, deadline=COALESCE(?,deadline), rolling=MAX(rolling,?), "
                "location=COALESCE(location,?), org=COALESCE(org,?), body_checked=COALESCE(?,body_checked) WHERE url=?",
                (body, deadline, int(rolling), location, org, checked, url))


def all_items(con, keep_since: str | None = None) -> list[dict]:
    q = "SELECT * FROM items" + (" WHERE last_seen >= ?" if keep_since else "")
    rows = con.execute(q, (keep_since,) if keep_since else ()).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["source_opts"] = json.loads(d.get("source_opts") or "{}")
        d["also_on"] = json.loads(d.get("also_on") or "[]")
        out.append(d)
    return out

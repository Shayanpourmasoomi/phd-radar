"""CLI:  python -m agent [run|check|rescore|demo]  [--deep]"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import time
from pathlib import Path

from . import db as dbm
from .http import Http
from .logic import Config, evaluate, needs_detail
from .render import render
from .sources import fetch_detail, fetch_source
from .util import norm

ROOT = Path(__file__).resolve().parent.parent


def _dedupe_key(it: dict) -> str:
    t = re.sub(r"[^a-z0-9]+", " ", norm(it.get("title")))[:70].strip()
    o = re.sub(r"[^a-z0-9]+", " ", norm(it.get("org")))[:30].strip()
    return t + "|" + o if o else t


def evaluate_all(con, cfg: Config, today: dt.date):
    """Re-apply the criteria to everything stored.  -> (kept decisions, rejected list)"""
    s = cfg.settings
    keep_since = (today - dt.timedelta(days=s["keep_days"])).isoformat()
    items = dbm.all_items(con, keep_since)
    kept, rejected, merged = {}, [], {}
    for it in items:
        d = evaluate(it, cfg, today)
        dl = it.get("deadline")
        if d["tier"] != "rejected" and s.get("drop_past_deadlines") and dl and dl < today.isoformat():
            d["tier"], d["reason"] = "rejected", f"deadline passed ({dl})"
        row = {**it, **d}
        row["sources"] = [it["source"]]
        row["is_new"] = (it.get("first_seen") or "") >= (today - dt.timedelta(days=1)).isoformat()
        if d["tier"] == "rejected":
            rejected.append(row)
            continue
        key = _dedupe_key(it)
        if key in kept:                       # same posting on another board
            k = kept[key]
            k["sources"] = sorted(set(k["sources"] + row["sources"]))
            if row["score"] > k["score"]:
                row["sources"] = k["sources"]
                kept[key] = row
        else:
            kept[key] = row
    return list(kept.values()), rejected


def cmd_check(cfg: Config, today: dt.date) -> int:
    http = Http(cfg.settings)
    bad = 0
    print(f"{'source':58} {'items':>5}  result")
    for src in cfg.sources:
        if not src.get("enabled", True):
            continue
        items, h = fetch_source(src, http, cfg, today, first_page_only=True)
        flag = "OK " if h["ok"] else "FAIL"
        print(f"{src['name'][:58]:58} {h['n_items']:>5}  {flag} {'' if h['verified'] else '(unverified) '}{h['error'] or ''}")
        for it in items[:2]:
            print(f"      e.g. {it['title'][:90]}")
        bad += 0 if h["ok"] else 1
    http.close()
    print(f"\n{bad} source(s) need attention.  Fix the URL in config/sources.yaml or set enabled: false.")
    return 0 if bad == 0 else 1


def cmd_run(cfg: Config, today: dt.date, deep: bool) -> int:
    con = dbm.connect()
    http = Http(cfg.settings)
    started = dt.datetime.now().isoformat(timespec="seconds")
    run_id = con.execute("INSERT INTO runs (started) VALUES (?)", (started,)).lastrowid
    health, n_new = [], 0
    for src in cfg.sources:
        if not src.get("enabled", True):
            continue
        print(f"[{src['name']}] ", end="", flush=True)
        items, h = fetch_source(src, http, cfg, today, deep=deep)
        health.append(h)
        new = sum(dbm.upsert(con, it, today.isoformat()) for it in items)
        n_new += new
        con.execute("INSERT INTO health VALUES (?,?,?,?,?,?)", (run_id, h["source"], int(h["ok"]), h["n_items"], h["error"], int(h["verified"])))
        con.commit()
        print(f"{h['n_items']} read, {new} new" + (f"  !! {h['error']}" if h["error"] else ""))

    # full posting pages for candidates that need a closer look
    budget = cfg.settings["max_detail_fetches"]
    t_end = time.time() + 60 * cfg.settings.get("max_detail_minutes", 40)
    fetched = 0
    recheck_before = (today - dt.timedelta(days=cfg.settings.get("recheck_undated_days", 7))).isoformat()
    for it in dbm.all_items(con, (today - dt.timedelta(days=cfg.settings["keep_days"])).isoformat()):
        if fetched >= budget or time.time() > t_end:
            break
        d = evaluate(it, cfg, today)
        so = it.get("source_opts") or {}
        # a listed posting with no known deadline: re-read its page now and then to notice when it closes
        # ("recheck: true" sources such as PREDOC.org list no page text, but their link still shows when a post closed)
        recheck = (not it.get("deadline") and d["tier"] != "rejected" and (it.get("body_checked") or "") < recheck_before
                   and ((bool(it.get("body")) and so.get("detail") is not False) or bool(so.get("recheck"))))
        if needs_detail(it, cfg, d) or recheck:
            html, err = http.get(it["url"], delay=so.get("delay_sec"), render=so.get("render"))
            fetched += 1
            if html is None:
                continue
            info = fetch_detail(html, today)
            dbm.set_body(con, it["url"], info["body"], info["deadline"], info["rolling"], info["location"], info["org"],
                         checked=today.isoformat())
    con.commit()
    http.close()
    print(f"detail pages fetched: {fetched}")

    kept, rejected = evaluate_all(con, cfg, today)
    path = render(kept, health, rejected, cfg.settings["site_title"], today, repo=cfg.easy.get("github_repo"))
    summary = {"new_postings_listed": n_new, "strong": sum(d["tier"] == "strong" for d in kept),
               "adjacent": sum(d["tier"] == "adjacent" for d in kept), "rejected": len(rejected)}
    con.execute("UPDATE runs SET finished=?, summary=? WHERE id=?", (dt.datetime.now().isoformat(timespec="seconds"), json.dumps(summary), run_id))
    con.commit()
    print(json.dumps(summary), "->", path)
    failing = [h["source"] for h in health if not h["ok"]]
    if failing:
        print("Sources with problems:", ", ".join(failing))
    return 0


def cmd_rescore(cfg: Config, today: dt.date) -> int:
    con = dbm.connect()
    kept, rejected = evaluate_all(con, cfg, today)
    health = [dict(r) for r in con.execute(
        "SELECT source, ok, n_items, error, verified FROM health WHERE run_id=(SELECT MAX(run_id) FROM health)").fetchall()]
    for h in health:
        h["ok"] = bool(h["ok"])
        h["verified"] = bool(h["verified"])
    path = render(kept, health, rejected, cfg.settings["site_title"], today, repo=cfg.easy.get("github_repo"))
    print(f"{len(kept)} kept, {len(rejected)} rejected ->", path)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="agent")
    ap.add_argument("command", nargs="?", default="run", choices=["run", "check", "rescore"])
    ap.add_argument("--deep", action="store_true", help="read many more pages per source (first run / weekly backfill)")
    ap.add_argument("--today", help="override today's date (YYYY-MM-DD), for tests")
    a = ap.parse_args(argv)
    today = dt.date.fromisoformat(a.today) if a.today else dt.date.today()
    cfg = Config()
    if a.command == "check":
        return cmd_check(cfg, today)
    if a.command == "rescore":
        return cmd_rescore(cfg, today)
    return cmd_run(cfg, today, a.deep)


if __name__ == "__main__":
    sys.exit(main())

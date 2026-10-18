"""Builds output_demo/index.html from INVENTED sample postings, so you can see the page.
Nothing here is real - no live scraping.  Run:  python tests/make_demo.py"""
import datetime as dt
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from agent import db as dbm  # noqa: E402
from agent import main as app  # noqa: E402
from agent.logic import Config  # noqa: E402
from agent.render import render  # noqa: E402

TODAY = dt.date.today()
d = lambda n: (TODAY + dt.timedelta(days=n)).isoformat()
S = [
 ("PhD position: Renewable energy auctions and market design", "Example University Leuven", "Leuven, Belgium", "EURAXESS", d(30), 0),
 ("Pre-doctoral research assistant, urban & housing economics", "Example Institute Madrid", "Madrid, Spain", "INOMICS", d(25), 0),
 ("Doctoral researcher in health economics", "Example Univ. Rotterdam", "Rotterdam, Netherlands", "EURAXESS", d(40), 1),
 ("PhD in labour economics (causal inference)", "Example Univ. Mannheim", "Mannheim, Germany", "INOMICS", d(20), 1),
 ("PhD scholarships in Economics", "Example Univ. Southern Denmark", "Odense, Denmark", "Academic Positions", d(35), 0),
 ("Research assistant - economic history & GIS", "Example School of Economics", "Paris, France", "Academic Positions", d(15), 1),
 ("PhD candidate: climate policy & macro transition risk", "Example Kiel Institute", "Kiel, Germany", "EURAXESS", d(45), 0),
 ("PhD studentship in Economics - development & field experiments", "Example Univ. Warwick", "Coventry, United Kingdom", "jobs.ac.uk", d(28), 0),
 ("PhD position in Asset Pricing", "Example Univ. Frankfurt", "Frankfurt, Germany", "INOMICS", d(20), 0),
 ("Postdoctoral researcher in labour economics", "Example Univ. Bonn", "Bonn, Germany", "EURAXESS", d(20), 0),
 ("PhD scholarship in health economics", "Example Univ. Melbourne", "Melbourne, Australia", "Academic Positions", d(20), 0),
]
tmp = Path(tempfile.mkdtemp()) / "demo.sqlite"
con = dbm.connect(tmp)
for i, (t, org, loc, src, dl, new) in enumerate(S):
    first = TODAY if new else TODAY - dt.timedelta(days=9)
    dbm.upsert(con, {"url": f"https://example.org/sample/{i}", "title": "[SAMPLE] " + t, "org": org, "location": loc, "source": src,
                     "source_opts": {}, "deadline": dl, "snippet": t, "fields": None}, first.isoformat())
cfg = Config()
kept, rejected = app.evaluate_all(con, cfg, TODAY)
health = [{"source": "EURAXESS (sample)", "ok": True, "n_items": 4, "error": None, "verified": True},
          {"source": "Some unverified source (sample)", "ok": False, "n_items": 0, "error": "demo: 404", "verified": False}]
out = ROOT / "output_demo"
print(render(kept, health, rejected, "SAMPLE DATA - PhD & Predoc Radar (demo, not real postings)", TODAY, out, repo="you/phd-radar"))
print(len(kept), "kept,", len(rejected), "rejected:", [(r["title"][9:40], r["reason"][:40]) for r in rejected])

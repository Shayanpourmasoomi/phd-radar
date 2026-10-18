"""Parser + pipeline tests on small hand-made HTML fixtures.

IMPORTANT: the fixtures imitate the structure of each site as best I could infer it
without live access.  They prove the code is internally consistent, NOT that the real
sites still look like this - that is what `python -m agent check` is for.
"""
import datetime as dt
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent import db as dbm  # noqa: E402
from agent import main as app  # noqa: E402
from agent.logic import Config, evaluate  # noqa: E402
from agent.sources import (fetch_detail, fetch_source, parse_academicpositions, parse_euraxess,  # noqa: E402
                           parse_inomics, parse_jobsacuk, parse_phdscanner, parse_predoc, parse_rss, parse_sitemap)

TODAY = dt.date(2026, 10, 18)

EURAXESS = """
<div class="view-content">
 <article><h3><a href="/jobs/123456">PhD position in urban economics and housing</a></h3>
  <div>Posted on: 15 October 2026</div>
  <p>The Department of Economics seeks a PhD student working on housing markets.</p>
  <ul><li>Department: Economics</li>
  <li>Number of offers: 1, Netherlands, Utrecht University</li>
  <li>Work Locations: Number of offers 1 Netherlands Utrecht</li>
  <li>Research Field: Economics » Urban economics</li>
  <li>Researcher Profile: First Stage Researcher (R1)</li>
  <li>Application Deadline: 30 November 2026 - 23:59 (Europe/Brussels)</li></ul></article>
 <article><h3><a href="/jobs/123457">Postdoctoral fellow in physics</a></h3>
  <div>Posted on: 14 October 2026</div>
  <ul><li>Number of offers: 1, Germany, MPI</li><li>Research Field: Physics</li>
  <li>Application Deadline: 30 November 2026</li></ul></article>
</div>"""

INOMICS = """
<a href="/job/phd-candidate-in-labour-economics-1234567">PhD Candidate Job Posted 2 days ago PhD Candidate in Labour Economics At University of Mannheim in Mannheim, Germany</a>
<a href="/job/phd-position-in-asset-pricing-1234568">PhD Candidate Job Posted 3 days ago PhD position in Asset Pricing At Goethe University in Frankfurt, Germany</a>
"""

JOBSAC = """
<div class="j-search-result__text">
 <a href="/job/DAB123/phd-studentship-in-economics">PhD Studentship in Economics - causal inference</a>
 <div class="j-search-result__employer"><b>University of Warwick</b></div>
 <div>Salary: £20,000 Placed on: 10/10/2026 Closes: 20/11/2026</div></div>
"""

AP = """
<div class="list-item"><a href="/ad/phd-position-in-health-economics-123">PhD Position in Health Economics</a>
 <span>Erasmus University Rotterdam</span> <span>Deadline: 1 Dec 2026</span> Apply</div>
"""

PREDOC = """
<div><h3><a href="https://example.org/a">Pre-Doctoral Research Assistant - Urban Economics</a></h3>
<p>Sponsoring Institution: University of Zurich</p><p>Fields of Research: Urban Economics, Public Economics</p>
<p>Deadline: December 15, 2026</p><p>Location: Zurich, Switzerland</p></div>
<div><h3><a href="https://example.org/b">Predoctoral Fellow</a></h3>
<p>Sponsoring Institution: Federal Reserve Bank of Chicago</p><p>Fields of Research: Macroeconomics</p>
<p>Deadline: Rolling</p><p>Location: Chicago, IL</p></div>
"""

DETAIL = """
<html><head><script type="application/ld+json">
{"@type":"JobPosting","description":"<p>We offer a PhD position in climate economics.</p>",
 "hiringOrganization":{"name":"Uni X"},"validThrough":"2026-12-01",
 "jobLocation":{"address":{"addressLocality":"Leuven","addressCountry":"Belgium"}}}
</script></head><body><nav>menu</nav><main>Climate economics PhD. Apply by 1 December 2026.</main></body></html>"""

RSS = """<rss><channel><item><title>PhD in Economics</title><link>https://x.org/1</link>
<description>&lt;p&gt;Deadline: 5 Dec 2026&lt;/p&gt;</description></item></channel></rss>"""


PHDSCANNER = """{"data":[
 {"id":"a1","title":"Housing markets and commuting: a causal analysis","university":"Example University","city":"Utrecht","country":"Netherlands",
  "department":"Economics","ai_summary":"PhD project on urban economics.","opportunity_url":"https://example.org/job/1","created_at":1792287721,"closing_date":"1797206340"},
 {"id":"a2","title":"Quantum algorithms","university":"Univ Y","city":"Bordeaux","country":"France","department":"Physics and Astronomy",
  "ai_summary":"Quantum.","opportunity_url":"","created_at":1792287721,"closing_date":""}]}"""

SITEMAP = """<urlset>
<url><loc>https://www.academictransfer.com/nl/jobs/361178/promovendus-governance-vertrouwen-10-fte/</loc></url>
<url><loc>https://www.academictransfer.com/en/jobs/361178/phd-governance-and-trust/</loc></url>
<url><loc>https://www.academictransfer.com/en/jobs/364702/assistant-professor-in-economics/</loc></url>
<url><loc>https://www.academictransfer.com/en/jobs/360001/operating-room-assistant/</loc></url>
<url><loc>https://www.academictransfer.com/en/jobs/360002/phd-position-in-labour-economics/</loc></url></urlset>"""

DETAIL_NESTED = """<html><head><script type="application/ld+json">
{"@type":"WebPage","mainEntity":{"@type":"JobPosting","datePosted":"2026-10-13","validThrough":"2026-11-15T23:59:59+01:00",
 "title":"PhD in labour economics","description":"PhD project. &lt;br&gt; Labour economics.","hiringOrganization":{"name":"Utrecht University"}}}
</script></head><body><main>PhD in labour economics at Utrecht</main></body></html>"""


REAL_PHDSCANNER = """{"data":[{"id":"6001b9d1-5058-4356-9157-442e854076ec","title":"Applications of quantum algorithms to physics","university":"University of Bordeaux","university_url":"u-bordeaux.fr","city":"Bordeaux","country":"France","category":"","department":"Physics and Astronomy","description":"","ai_summary":"Quantum.","opportunity_url":"https://adum.fr/as/ed/voirproposition.pl?langue=&site=UBx&matricule_prop=77173","open_to":"","status":"","views":"11","supervisor":"x@y.fr","supervisor_url":"mailto:x@y.fr","fully_funded":true,"funded_amount":"","created_at":1792287721,"closing_date":"1797206340","plan_type":"","collect_resumes":false},
{"id":"a2970911-a9b4-4df3-9556-aa128e8049d3","title":"Designing for Adoption","university":"University College London","city":"London","country":"United Kingdom","department":"Department of Physics and Astronomy","ai_summary":"x","opportunity_url":"https://www.ucl.ac.uk/study/prospective-students/graduate/funded-research-opportunities","created_at":1792283829,"closing_date":"1795910400"},
{"id":"b3333333-a9b4-4df3-9556-aa128e8049d3","title":"Another UCL project","university":"University College London","city":"London","country":"United Kingdom","department":"Economics","ai_summary":"y","opportunity_url":"https://www.ucl.ac.uk/study/prospective-students/graduate/funded-research-opportunities","created_at":1792283800,"closing_date":"1795910400"}],"pagination":{}}"""


class Parsers(unittest.TestCase):
    def test_phdscanner_real_shape_and_shared_links(self):
        its = parse_phdscanner(REAL_PHDSCANNER, "", TODAY)
        self.assertEqual(len(its), 3)
        self.assertEqual(len({i["url"] for i in its}), 3)          # shared UCL link must not collapse postings
        self.assertEqual(its[0]["posted"], "2026-10-18")
        self.assertEqual(its[0]["deadline"], "2026-12-13")

    def test_phdscanner(self):
        its = parse_phdscanner(PHDSCANNER, "", TODAY)
        self.assertEqual(len(its), 2)
        a = its[0]
        self.assertEqual(a["url"], "https://example.org/job/1#phdscanner-a1")
        self.assertEqual(a["location"], "Utrecht, Netherlands")
        self.assertEqual(a["fields"], "Economics")
        self.assertTrue(a["deadline"].startswith("20"))
        self.assertIn("phdscanner.com", its[1]["url"])      # no external link -> fallback key
        self.assertNotEqual(parse_phdscanner(PHDSCANNER.replace("a2", "a1"), "", TODAY)[1]["url"], its[0]["url"])
        self.assertIsNone(its[1]["deadline"])
        self.assertEqual(parse_phdscanner("not json", "", TODAY), [])

    def test_sitemap(self):
        its = parse_sitemap(SITEMAP, "", TODAY, r"phd|promovend|econom")
        urls = {i["url"] for i in its}
        self.assertIn("https://www.academictransfer.com/en/jobs/361178/phd-governance-and-trust/", urls)   # English preferred
        self.assertEqual(len(its), 3)                                                                       # dup id merged, nurse dropped
        self.assertEqual(next(i for i in its if "360002" in i["url"])["title"], "Phd position in labour economics")

    def test_detail_nested_jsonld(self):
        d = fetch_detail(DETAIL_NESTED, TODAY)
        self.assertEqual(d["deadline"], "2026-11-15")
        self.assertEqual(d["org"], "Utrecht University")


    def test_euraxess(self):
        its = parse_euraxess(EURAXESS, "https://euraxess.ec.europa.eu/jobs/search", TODAY)
        self.assertEqual(len(its), 2)
        a = its[0]
        self.assertEqual(a["url"], "https://euraxess.ec.europa.eu/jobs/123456")
        self.assertEqual(a["deadline"], "2026-11-30")
        self.assertEqual(a["posted"], "2026-10-15")
        self.assertIn("Urban economics", a["fields"])
        self.assertIn("Utrecht", (a["org"] or "") + (a["location"] or ""))

    def test_inomics(self):
        its = parse_inomics(INOMICS, "https://inomics.com/", TODAY)
        self.assertEqual(len(its), 2)
        self.assertEqual(its[0]["title"], "PhD Candidate in Labour Economics")
        self.assertEqual(its[0]["org"], "University of Mannheim")
        self.assertEqual(its[0]["location"], "Mannheim, Germany")
        self.assertEqual(its[0]["posted"], "2026-10-16")

    def test_jobsacuk(self):
        its = parse_jobsacuk(JOBSAC, "https://www.jobs.ac.uk/", TODAY)
        self.assertEqual(len(its), 1)
        self.assertEqual(its[0]["org"], "University of Warwick")
        self.assertEqual(its[0]["deadline"], "2026-11-20")

    def test_academicpositions(self):
        its = parse_academicpositions(AP, "https://academicpositions.com/jobs", TODAY)
        self.assertEqual(len(its), 1)
        self.assertEqual(its[0]["deadline"], "2026-12-01")

    def test_predoc(self):
        its = parse_predoc(PREDOC, "https://predoc.org/opportunities", TODAY)
        self.assertEqual(len(its), 2)
        self.assertEqual(its[0]["org"], "University of Zurich")
        self.assertEqual(its[0]["deadline"], "2026-12-15")
        self.assertTrue(its[1]["rolling"])

    def test_rss(self):
        its = parse_rss(RSS, "", TODAY, "Germany")
        self.assertEqual(its[0]["deadline"], "2026-12-05")

    def test_detail(self):
        d = fetch_detail(DETAIL, TODAY)
        self.assertEqual(d["deadline"], "2026-12-01")
        self.assertEqual(d["org"], "Uni X")
        self.assertIn("Leuven", d["location"])
        self.assertIn("climate economics", d["body"].lower())
        self.assertNotIn("menu", d["body"])


class FakeHttp:
    def __init__(self, pages):
        self.pages = pages

    def get(self, url, delay=None, headers=None):
        for k, v in self.pages.items():
            if url.startswith(k):
                return v, None
        return None, "404"


class Pipeline(unittest.TestCase):
    def test_end_to_end(self):
        cfg = Config()
        src_e = next(s for s in cfg.sources if s["name"].startswith("EURAXESS"))
        src_p = next(s for s in cfg.sources if s["name"].startswith("PREDOC"))
        http = FakeHttp({"https://euraxess.ec.europa.eu/jobs/search": EURAXESS, "https://www.predoc.org": PREDOC})
        con = dbm.connect(Path(tempfile.mkdtemp()) / "t.sqlite")
        for src in (src_e, src_p):
            items, h = fetch_source(src, http, cfg, TODAY)
            self.assertTrue(h["ok"], h)
            for it in items:
                dbm.upsert(con, it, TODAY.isoformat())
        kept, rejected = app.evaluate_all(con, cfg, TODAY)
        titles = {k["title"] for k in kept}
        self.assertIn("PhD position in urban economics and housing", titles)
        self.assertIn("Pre-Doctoral Research Assistant - Urban Economics", titles)
        rej = {r["title"]: r["reason"] for r in rejected}
        self.assertIn("Postdoctoral fellow in physics", rej)
        self.assertIn("Predoctoral Fellow", rej)            # Chicago -> outside Europe
        self.assertTrue(rej["Predoctoral Fellow"].startswith("outside Europe"))

    def test_phdscanner_paging_uses_offset(self):
        cfg = Config()
        src = next(s for s in cfg.sources if s["name"] == "PhDScanner")
        seen = []

        class H:
            def get(self, url, delay=None, headers=None):
                seen.append(url)
                return (PHDSCANNER, None) if "offset=0" in url else ('{"data":[]}', None)
        items, h = fetch_source(src, H(), cfg, TODAY)
        self.assertTrue(h["ok"], h)
        self.assertTrue(seen[0].endswith("limit=30&offset=0"))
        self.assertTrue(seen[1].endswith("limit=30&offset=30"))

    def test_past_deadline_dropped(self):
        cfg = Config()
        con = dbm.connect(Path(tempfile.mkdtemp()) / "t.sqlite")
        dbm.upsert(con, {"url": "u1", "title": "PhD in labour economics", "org": "X", "location": "Paris, France", "source": "t",
                         "source_opts": {}, "deadline": "2026-09-01", "snippet": None, "fields": None}, TODAY.isoformat())
        kept, rejected = app.evaluate_all(con, cfg, TODAY)
        self.assertEqual(kept, [])
        self.assertIn("deadline passed", rejected[0]["reason"])


if __name__ == "__main__":
    unittest.main()

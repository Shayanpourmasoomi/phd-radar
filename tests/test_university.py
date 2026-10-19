"""University vacancy pages: parser on static HTML + the headless-browser path on a local JavaScript page."""
import datetime as dt
import http.server
import sys
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.http import Http  # noqa: E402
from agent.logic import Config, evaluate  # noqa: E402
from agent.sources import fetch_source, parse_oraclehcm, parse_university  # noqa: E402

TODAY = dt.date(2026, 10, 19)

STATIC = """<html><body><nav><a href="/jobs/1">PhD in Nav Link Should Be Ignored</a></nav>
<ul>
 <li><a href="/vacancies/123">PhD Studentship in Labour Economics</a><span>Closing date: 30 November 2026</span></li>
 <li><a href="/vacancies/124">Professor of Finance</a><span>Closing 1 Dec 2026</span></li>
 <li><a href="/vacancies/125">Research Assistant - Urban Economics</a></li>
 <li><a href="/vacancies/126">Doktorand i nationalekonomi</a><span>Sista ansökningsdag 2026-11-20</span></li>
 <li><a href="mailto:hr@x.edu">PhD enquiries by email please</a></li>
 <li><a href="/vacancies/127">Cleaner</a><span>Mentions a PhD in passing? no, but card text has Doctoral supervisor</span></li>
</ul></body></html>"""

JS_PAGE = """<html><body><div id="l"></div><button id="more" onclick="more()">Load more results</button>
<script>
let n=0;function more(){const l=document.getElementById('l');for(let i=0;i<2;i++){n++;l.insertAdjacentHTML('beforeend',
 '<div class="card"><a href="/job/'+n+'">PhD position in health economics number '+n+'</a> <span>Deadline: 15 Dec 2026</span></div>');}
 if(n>=4)document.getElementById('more').remove();}
setTimeout(more,300);
</script></body></html>"""


class Static(unittest.TestCase):
    def test_parse_university(self):
        its = parse_university(STATIC, "https://uni.example/vacancies", TODAY, org="Example Uni", country="Sweden")
        titles = [i["title"] for i in its]
        self.assertIn("PhD Studentship in Labour Economics", titles)
        self.assertIn("Research Assistant - Urban Economics", titles)
        self.assertIn("Doktorand i nationalekonomi", titles)
        self.assertNotIn("PhD in Nav Link Should Be Ignored", titles)      # navigation ignored
        self.assertFalse(any("enquiries" in t for t in titles))            # mailto ignored
        self.assertNotIn("Professor of Finance", titles)
        a = next(i for i in its if "Labour" in i["title"])
        self.assertEqual(a["url"], "https://uni.example/vacancies/123")
        self.assertEqual(a["deadline"], "2026-11-30")
        self.assertEqual(a["org"], "Example Uni")
        d = evaluate({**a, "source_opts": {}}, Config(), TODAY)
        self.assertNotEqual(d["tier"], "rejected", d["reason"])


class Oracle(unittest.TestCase):
    def test_parse_oraclehcm(self):
        js = '{"items":[{"requisitionList":[{"Id":"15099","Title":"PhD Studentship in Labour Economics","PostedDate":"2026-10-15","PostingEndDate":"2026-11-27","Department":"Economics","PrimaryLocation":"Edinburgh - Central Area, Midlothian, United Kingdom","ShortDescriptionStr":"Fully funded PhD in applied economics."},{"Id":"","Title":"x"}]}]}'
        its = parse_oraclehcm(js, "https://h/api", TODAY, "https://h/job/{id}", "University of Edinburgh")
        self.assertEqual(len(its), 1)
        self.assertEqual(its[0]["url"], "https://h/job/15099")
        self.assertEqual(its[0]["deadline"], "2026-11-27")
        self.assertEqual(its[0]["org"], "University of Edinburgh")
        d = evaluate({**its[0], "source_opts": {"default_country": "United Kingdom"}}, Config(), TODAY)
        self.assertNotEqual(d["tier"], "rejected", d["reason"])
        self.assertEqual(parse_oraclehcm("not json", "u", TODAY), [])


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/robots.txt"):
            self.send_response(404); self.end_headers(); return
        self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers()
        self.wfile.write((JS_PAGE if self.path.startswith("/js") else STATIC).encode())

    def log_message(self, *a):
        pass


def _browser_available():
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            p.chromium.launch().close()
        return True
    except Exception:
        return False


@unittest.skipUnless(_browser_available(), "Chromium / Playwright not available")
class Rendered(unittest.TestCase):
    def test_js_page_with_load_more(self):
        srv = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        cfg = Config()
        cfg.settings = {**cfg.settings, "request_delay_sec": 0}
        http_ = Http(cfg.settings)
        try:
            src = {"name": "t", "type": "university", "url": f"http://127.0.0.1:{srv.server_port}/js", "org": "JS Uni", "country": "Denmark",
                   "render": {"click_text": "load more", "max_clicks": 5}}
            items, h = fetch_source(src, http_, cfg, TODAY)
            self.assertTrue(h["ok"], h)
            self.assertEqual(len(items), 4, [i["title"] for i in items])      # 2 initial + 2 after the click
            # without clicking, only the first batch is visible
            src2 = {**src, "render": {}}
            items2, _ = fetch_source(src2, http_, cfg, TODAY)
            self.assertEqual(len(items2), 2)
        finally:
            http_.close()
            srv.shutdown()


if __name__ == "__main__":
    unittest.main()

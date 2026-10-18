"""Site adapters.  Each `parse_*` takes one page of HTML and returns listing dicts;
`fetch_source` pages through a source; `fetch_detail` reads one full posting."""
from __future__ import annotations

import datetime as dt
import json
import re
import xml.etree.ElementTree as ET
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .util import ago_to_date, find_deadline, parse_date

LABELS = ("Department:", "Work Locations:", "Research Field:", "Researcher Profile:", "Funding Programme:", "Application Deadline:")


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def _text(el, sep=" ", limit=900) -> str:
    return re.sub(r"[ \t]+", " ", el.get_text(sep, strip=True))[:limit]


def _container(a, must: tuple[str, ...], levels: int = 6):
    """Climb from a link to the smallest ancestor whose text contains one of `must`."""
    el = a
    for _ in range(levels):
        if el.parent is None:
            break
        el = el.parent
        t = el.get_text(" ", strip=True)
        if any(m in t for m in must):
            return el
    return a.parent or a


def _iso(d: dt.date | None) -> str | None:
    return d.isoformat() if d else None


# --------------------------------------------------------------------------- EURAXESS
def parse_euraxess(html: str, base: str, today: dt.date) -> list[dict]:
    soup = _soup(html)
    items, seen = [], set()
    for a in soup.find_all("a", href=re.compile(r"/jobs/\d+/?$")):
        url = urljoin(base, a["href"]).split("#")[0]
        title = a.get_text(" ", strip=True)
        if not title or url in seen:
            continue
        seen.add(url)
        box = _container(a, ("Application Deadline", "Posted on"))
        raw = box.get_text("\n", strip=True)
        flat = re.sub(r"\s+", " ", raw)
        m = re.search(r"Posted on:?\s*(\d{1,2}\s+[A-Za-z]+\s+\d{4})", flat)
        posted = parse_date(m[1], today) if m else None
        m = re.search(r"Number of offers:\s*\d+,\s*([^,]+),\s*([^,]+)", flat)
        country, org = (m[1].strip(), m[2].strip()) if m else (None, None)
        m = re.search(r"Research Field:\s*(.*?)\s*(?:Researcher Profile:|Funding Programme:|Application Deadline:|$)", flat)
        fields = m[1].strip() if m else None
        m = re.search(r"Application Deadline:\s*(\d{1,2}\s+[A-Za-z]+\s+\d{4})", flat)
        deadline = parse_date(m[1], today) if m else None
        m = re.search(re.escape(title) + r"\s*(.*?)\s*(?:Department:|Work Locations:|Research Field:)", flat)
        snippet = m[1].strip() if m else None
        m = re.search(r"Work Locations:\s*(.*?)\s*(?:Research Field:|Researcher Profile:|$)", flat)
        location = m[1].strip() if m else country
        items.append({"url": url, "title": title, "org": org, "location": location, "snippet": snippet, "fields": fields,
                      "posted": _iso(posted), "deadline": _iso(deadline), "rolling": False})
    return items


# --------------------------------------------------------------------------- INOMICS
_INOMICS = re.compile(
    r"^(?P<tags>.*?)Posted\s+(?P<ago>(?:\d+|a|an)\s+\w+)\s+ago\s+(?P<title>.+?)\s+At\s+(?P<org>.+?)\s+in\s+(?P<city>[^,]+),\s*(?P<country>[^,]+?)(?:\s+Logo for.*)?$")


def parse_inomics(html: str, base: str, today: dt.date) -> list[dict]:
    soup = _soup(html)
    items, seen = [], set()
    for a in soup.find_all("a", href=re.compile(r"/job/[^/]+-\d+/?$")):
        url = urljoin(base, a["href"]).split("#")[0]
        url = re.sub(r"https://inomics\.com/(?:de|fr|es|it)/", "https://inomics.com/", url)
        text = a.get_text(" ", strip=True)
        if len(text) < 15 or url in seen:
            continue
        seen.add(url)
        text = re.sub(r"\(Hybrid\)\s*\*?\s*", "", text)
        text = text.replace("*", " ").strip()
        m = _INOMICS.match(re.sub(r"\s+", " ", text))
        if m:
            tags = m["tags"].strip(" *")
            title, org = m["title"].strip(), m["org"].strip()
            location = f"{m['city'].strip()}, {m['country'].strip()}"
            posted = ago_to_date(m["ago"] + " ago", today)
        else:
            mm = re.search(r"Posted\s+((?:\d+|a|an)\s+\w+)\s+ago\s+(.*)$", text)
            tags = text.split("Posted")[0].strip(" *")
            title, org, location = (mm[2] if mm else text), None, None
            posted = ago_to_date((mm[1] + " ago") if mm else "", today)
        items.append({"url": url, "title": title, "org": org, "location": location, "site_tags": tags, "snippet": None,
                      "posted": _iso(posted), "deadline": None, "rolling": False})
    return items


# --------------------------------------------------------------------------- jobs.ac.uk
def parse_jobsacuk(html: str, base: str, today: dt.date) -> list[dict]:
    soup = _soup(html)
    items, seen = [], set()
    for a in soup.find_all("a", href=re.compile(r"/job/[A-Za-z0-9]+/")):
        url = urljoin("https://www.jobs.ac.uk", a["href"]).split("#")[0]
        title = a.get_text(" ", strip=True)
        if not title or url in seen:
            continue
        seen.add(url)
        box = _container(a, ("Placed on", "Closes"))
        flat = re.sub(r"\s+", " ", box.get_text(" ", strip=True))
        strong = box.find(["strong", "b"])
        org = strong.get_text(" ", strip=True) if strong else None
        m = re.search(r"Placed on:?\s*(\d{1,2}/\d{1,2}/\d{4})", flat)
        posted = parse_date(m[1], today) if m else None
        deadline, rolling = find_deadline(flat[flat.find("Closes"):] if "Closes" in flat else "", today)
        m = re.search(r"Salary:\s*(.*?)\s*Closes", flat)
        items.append({"url": url, "title": title, "org": org, "location": None, "snippet": flat[:500],
                      "posted": _iso(posted), "deadline": _iso(deadline), "rolling": rolling})
    return items


# --------------------------------------------------------------------------- Academic Positions
def parse_academicpositions(html: str, base: str, today: dt.date) -> list[dict]:
    soup = _soup(html)
    items, seen = [], set()
    for a in soup.find_all("a", href=re.compile(r"/ad/")):
        url = urljoin("https://academicpositions.com", a["href"]).split("#")[0].split("?")[0]
        title = a.get_text(" ", strip=True)
        if not title or url in seen or len(title) < 6:
            continue
        seen.add(url)
        box = _container(a, ("Posted", "Deadline", "days", "Apply"), levels=4)
        flat = re.sub(r"\s+", " ", box.get_text(" ", strip=True))
        deadline, rolling = find_deadline(flat, today)
        items.append({"url": url, "title": title, "org": None, "location": None, "snippet": flat[:500],
                      "posted": None, "deadline": _iso(deadline), "rolling": rolling})
    return items


# --------------------------------------------------------------------------- PREDOC.org
def parse_predoc(html: str, base: str, today: dt.date) -> list[dict]:
    soup = _soup(html)
    items = []
    for h in soup.find_all(["h2", "h3"]):
        a = h.find("a", href=True)
        if not a:
            continue
        title = a.get_text(" ", strip=True)
        chunk = []
        for sib in h.next_siblings:
            if getattr(sib, "name", None) in ("h2", "h3"):
                break
            chunk.append(sib.get_text("\n", strip=True) if hasattr(sib, "get_text") else str(sib).strip())
        flat = re.sub(r"[ \t]+", " ", "\n".join(c for c in chunk if c))
        if "Institution" not in flat and h.parent is not None:      # fallback: the wrapping element
            flat = re.sub(r"[ \t]+", " ", h.parent.get_text("\n", strip=True))
        if "Institution" not in flat and "Fields of Research" not in flat:
            continue
        one = re.sub(r"\s+", " ", flat)
        m = re.search(r"Sponsoring Institutions?:?\s*(.*?)\s*(?:Fields? of [Rr]esearch|Project Scope|Deadline|Visa|Location|$)", one)
        org = m[1].strip(" *") if m else None
        m = re.search(r"Fields? of [Rr]esearch:?\s*(.*?)\s*(?:Deadline|Project Scope|Visa|Start Date|Location|Email|$)", one)
        fields = m[1].strip(" *") if m else None
        m = re.search(r"Deadline(?:/First Review Date)?:?\s*(.*?)\s*(?:Visa|Start Date|Location|Email|Note|$)", one)
        dl_text = m[1] if m else ""
        deadline, rolling = find_deadline("Deadline: " + dl_text, today)
        m = re.search(r"Location:?\s*(.*?)\s*(?:\(|Email|Visa|$)", one)
        location = m[1].strip() if m else None
        researchers = re.search(r"Sponsoring Researcher\(?s?\)?:?\s*(.*?)\s*Sponsoring Institution", one)
        items.append({"url": a["href"], "title": title, "org": org, "location": location, "fields": fields,
                      "snippet": (("Sponsoring researchers: " + researchers[1]) if researchers else "") + " | " + one[:350],
                      "posted": None, "deadline": _iso(deadline), "rolling": rolling or "rolling" in dl_text.lower()})
    return items



# --------------------------------------------------------------------------- PhDScanner (JSON API used by its own site; allowed by robots.txt)
def parse_phdscanner(text: str, base: str, today: dt.date) -> list[dict]:
    try:
        data = json.loads(text)
    except ValueError:
        return []
    items = []
    for r in data.get("data") or []:
        title = (r.get("title") or "").strip()
        if not title:
            continue
        url = (r.get("opportunity_url") or "").strip()
        if not url.startswith("http"):
            url = "https://www.phdscanner.com/phd-vacancies/standard"
        # several postings share one generic link (e.g. a university's "funded projects" page), so the
        # posting id is appended as a fragment: harmless for the browser, unique for our database
        url = f"{url.split('#')[0]}#phdscanner-{str(r.get('id'))[:8]}"
        def _d(v):
            try:
                return dt.datetime.fromtimestamp(int(v), dt.timezone.utc).date()
            except (TypeError, ValueError, OSError):
                return None
        loc = ", ".join(x for x in (r.get("city"), r.get("country")) if x)
        snippet = " ".join(x for x in (r.get("ai_summary"), r.get("description")) if x)[:900]
        items.append({"url": url, "title": title, "org": r.get("university"), "location": loc or None, "snippet": snippet or None,
                      "fields": r.get("department") or None, "posted": _iso(_d(r.get("created_at"))),
                      "deadline": _iso(_d(r.get("closing_date"))), "rolling": False})
    return items


# --------------------------------------------------------------------------- sitemap of vacancies (AcademicTransfer)
def parse_sitemap(xml: str, base: str, today: dt.date, slug_include: str | None = None, id_regex: str = r"/jobs/(\d+)/") -> list[dict]:
    """One item per vacancy id (English page preferred).  The title is rebuilt from the URL slug, which is
    enough for a first screen; the full posting is fetched later only for candidates."""
    inc = re.compile(slug_include, re.I) if slug_include else None
    idrx = re.compile(id_regex)
    best: dict[str, str] = {}
    for u in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml):
        m = idrx.search(u)
        if not m:
            continue
        slug = u.rstrip("/").rsplit("/", 1)[-1]
        if inc and not inc.search(slug):
            continue
        vid = m[1]
        if vid not in best or ("/en/" in u and "/en/" not in best[vid]):
            best[vid] = u
    items = []
    for vid, u in best.items():
        slug = u.rstrip("/").rsplit("/", 1)[-1]
        title = re.sub(r"\s+", " ", slug.replace("-", " ")).strip().capitalize()
        title = re.sub(r"\s(\d{1,2}) (\d) fte$", "", title)
        items.append({"url": u, "title": title, "org": None, "location": None, "snippet": None,
                      "posted": None, "deadline": None, "rolling": False})
    return items

# --------------------------------------------------------------------------- generic + RSS
def parse_generic(html: str, base: str, today: dt.date, link_regex: str, country: str | None) -> list[dict]:
    soup = _soup(html)
    rx = re.compile(link_regex)
    items, seen = [], set()
    for a in soup.find_all("a", href=True):
        url = urljoin(base, a["href"]).split("#")[0]
        title = a.get_text(" ", strip=True)
        if not rx.search(url) or len(title) < 8 or url in seen:
            continue
        seen.add(url)
        box = a.parent or a
        flat = re.sub(r"\s+", " ", box.get_text(" ", strip=True))[:500]
        deadline, rolling = find_deadline(flat, today)
        items.append({"url": url, "title": title, "org": None, "location": country, "snippet": flat,
                      "posted": None, "deadline": _iso(deadline), "rolling": rolling})
    return items


def parse_rss(xml: str, base: str, today: dt.date, country: str | None) -> list[dict]:
    items = []
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return items
    ns = {"a": "http://www.w3.org/2005/Atom"}
    for e in list(root.iter("item")) + list(root.iter("{http://www.w3.org/2005/Atom}entry")):
        title = (e.findtext("title") or e.findtext("a:title", namespaces=ns) or "").strip()
        link = e.findtext("link") or ""
        if not link:
            le = e.find("a:link", ns)
            link = le.get("href") if le is not None else ""
        desc = re.sub(r"<[^>]+>", " ", e.findtext("description") or e.findtext("a:summary", namespaces=ns) or "")
        if title and link:
            deadline, rolling = find_deadline(desc, today)
            items.append({"url": link.strip(), "title": title, "org": None, "location": country, "snippet": re.sub(r"\s+", " ", desc)[:500],
                          "posted": None, "deadline": _iso(deadline), "rolling": rolling})
    return items


PARSERS = {"euraxess": parse_euraxess, "inomics": parse_inomics, "jobsacuk": parse_jobsacuk,
           "academicpositions": parse_academicpositions, "predoc": parse_predoc, "phdscanner": parse_phdscanner}


def parse_page(src: dict, html: str, today: dt.date) -> list[dict]:
    t = src["type"]
    base = src["url"]
    if t == "generic":
        return parse_generic(html, base, today, src.get("link_regex", r"."), src.get("country"))
    if t == "rss":
        return parse_rss(html, base, today, src.get("country"))
    if t == "sitemap":
        return parse_sitemap(html, base, today, src.get("slug_include"), src.get("id_regex", r"/jobs/(\d+)/"))
    return PARSERS[t](html, base, today)


def source_opts(src: dict) -> dict:
    return {k: src[k] for k in ("econ_specific", "default_country", "assume_type", "detail", "delay_sec") if k in src}


def fetch_source(src: dict, http, cfg, today: dt.date, deep: bool = False, first_page_only: bool = False):
    """-> (items, health dict).  Never raises."""
    pages = 1 if first_page_only else (src.get("deep_pages", src.get("pages", 1)) if deep else src.get("pages", 1))
    first = src.get("first_page", 1)
    lookback = dt.timedelta(days=cfg.settings["lookback_days"])
    all_items, seen_urls, err, empty_pages = [], set(), None, 0
    for i in range(pages):
        url = src["url"].format(page=first + i, offset=i * int(src.get("offset_step", 0))) if ("{page}" in src["url"] or "{offset}" in src["url"]) else src["url"]
        html, e = http.get(url, delay=src.get("delay_sec"), headers=src.get("headers"))
        if html is None:
            err = f"{url} -> {e}"
            break
        try:
            batch = parse_page(src, html, today)
        except Exception as ex:                       # layout changed -> report, keep going
            err = f"parse error on {url}: {type(ex).__name__}: {ex}"
            break
        new = [b for b in batch if b["url"] not in seen_urls]
        for b in new:
            seen_urls.add(b["url"])
            b["source"] = src["name"]
            b["source_opts"] = source_opts(src)
        all_items.extend(new)
        if not new:
            empty_pages += 1
            if empty_pages >= 1:
                break
        if src.get("newest_first") and not deep and new:
            dated = [dt.date.fromisoformat(b["posted"]) for b in new if b.get("posted")]
            if dated and all(d < today - lookback for d in dated):
                break
    ok = err is None and len(all_items) > 0
    if err is None and not all_items:
        err = "page loaded but 0 postings parsed (layout changed or wrong URL?)"
    return all_items, {"source": src["name"], "ok": ok, "n_items": len(all_items), "error": err, "verified": bool(src.get("verified"))}


# --------------------------------------------------------------------------- detail pages
def fetch_detail(html: str, today: dt.date) -> dict:
    """-> {body, deadline, rolling, location, org}"""
    soup = _soup(html)
    ld_desc, ld_loc, ld_org, ld_deadline = "", None, None, None

    def _postings(node):
        """JobPosting objects anywhere inside a JSON-LD blob (also under mainEntity / @graph)."""
        if isinstance(node, list):
            for n in node:
                yield from _postings(n)
        elif isinstance(node, dict):
            t = node.get("@type")
            if t == "JobPosting" or (isinstance(t, list) and "JobPosting" in t):
                yield node
            for k in ("mainEntity", "@graph"):
                if k in node:
                    yield from _postings(node[k])

    for s in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(s.string or s.get_text() or "")
        except Exception:
            continue
        for d in _postings(data):
            ld_desc = re.sub(r"<[^>]+>", " ", d.get("description") or "")
            org = d.get("hiringOrganization")
            ld_org = org.get("name") if isinstance(org, dict) else (org if isinstance(org, str) else None)
            loc = d.get("jobLocation")
            if isinstance(loc, list) and loc:
                loc = loc[0]
            if isinstance(loc, dict):
                addr = loc.get("address") or {}
                if isinstance(addr, dict):
                    ld_loc = ", ".join(str(addr.get(k)) for k in ("addressLocality", "addressRegion", "addressCountry") if addr.get(k))
            ld_deadline = parse_date(d.get("validThrough"), today)
    for tag in soup(["script", "style", "nav", "header", "footer", "noscript", "form", "aside"]):
        tag.decompose()
    main = soup.find("main") or soup.find("article") or soup.body or soup
    page_text = re.sub(r"\s+", " ", main.get_text(" ", strip=True))
    body = (ld_desc + " " + page_text if ld_desc else page_text)[:9000]
    body = re.sub(r"\s+", " ", body)
    deadline, rolling = find_deadline(body, today)
    return {"body": body, "deadline": _iso(ld_deadline or deadline), "rolling": rolling, "location": ld_loc, "org": ld_org}

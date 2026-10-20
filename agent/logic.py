"""Decide, for one posting, whether it is kept and how well it fits.

Pure functions on plain dicts - no network - so criteria changes can be re-applied
to everything already collected (python -m agent rescore) and unit-tested.
"""
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import yaml

from .util import any_term, norm, term_regex

ROOT = Path(__file__).resolve().parent.parent


def load_yaml(name: str) -> dict:
    with open(ROOT / "config" / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


class Config:
    def __init__(self, root: Path | None = None):
        self.settings = load_yaml("settings.yaml")
        self.profiles = load_yaml("profiles.yaml")
        self.geo = load_yaml("geography.yaml")
        self.sources = load_yaml("sources.yaml")["sources"]
        self.people = self.profiles["people"]
        self.easy = load_yaml("easy.yaml") or {}
        self._apply_easy()

    def _apply_easy(self):
        """Merge the friendly settings file (config/easy.yaml) into the full configuration."""
        e = self.easy
        if e.get("contact_email"):
            self.settings["user_agent"] = f"phd-agent/1.0 (personal research use; contact: {e['contact_email']})"
        hard = self.settings.setdefault("hard_exclude_in_title", [])
        hard.extend(w for w in (e.get("block_title_words") or []) if w)
        self.blocked_orgs = [norm(o) for o in (e.get("block_orgs") or []) if o]
        by_who: dict[str, list[str]] = {}
        for k in e.get("my_keywords") or []:
            if isinstance(k, dict) and k.get("term"):
                by_who.setdefault(k.get("who", "both"), []).append(k["term"])
        for who, terms in by_who.items():
            ids = ["shayan", "zahra"] if who == "both" else [who]
            self.profiles["fields"].append({"id": f"my_{who}", "label": "My keywords", "who": ids, "weight": 3, "strong": terms, "support": []})


# --------------------------------------------------------------------------- position type
def detect_type(title: str, body: str, cfg: Config, assume: str | None = None) -> tuple[str | None, str]:
    """-> (type name or None, reason).  Title decides; body only for generic titles."""
    s = cfg.settings
    t = norm(title)
    b = norm(body)
    head = b[: s["body_check_chars"]]
    hard = any_term(t, s.get("hard_exclude_in_title", []))
    if hard:
        return None, f"position type excluded (title: '{hard}')"
    exc_title = any_term(t, s["exclude_in_title"])
    # 1) title says it ("PhD ...", "Pre-doctoral ...").  Generic titles such as
    #    "Wissenschaftliche*r Mitarbeiter*in" also need a PhD word in the posting.
    for pt in s["position_types"]:
        if any_term(t, pt["include"]):
            if pt.get("needs_body_evidence") and not any_term(head, s["phd_evidence"]):
                continue
            return pt["name"], "ok"
    if assume and not exc_title:
        return assume, "ok (source-assumed)"
    if exc_title:
        return None, f"position type excluded (title: '{exc_title}')"
    # 2) title silent: look at the start of the posting
    if any_term(b[: s["body_exclude_chars"]], ["postdoc*", "post doc*", "postdoctoral", "professor*", "lecturer", "tenure*"]):
        return None, "position type excluded (postdoc/professor wording at top of posting)"
    for pt in s["position_types"]:
        if pt.get("needs_body_evidence"):
            continue
        hit = any_term(head, pt["include"])
        if hit:
            return pt["name"], f"ok (from body: '{hit}')"
    return None, "not a PhD / predoc / RA / doctoral-researcher posting"


def needs_detail(item: dict, cfg: Config, decision: dict) -> bool:
    """Should the full posting page be fetched to decide properly?"""
    if item.get("body") or (item.get("source_opts") or {}).get("detail") is False:
        return False
    r = decision.get("reason", "")
    if r.startswith("outside Europe") or r.startswith("position type excluded"):
        return False
    opts = item.get("source_opts") or {}
    if opts.get("econ_specific") or opts.get("detail") == "always":
        return True
    pre = norm(" ".join(filter(None, [item.get("title"), item.get("org"), item.get("fields"), item.get("snippet")])))
    if any(sub in pre for sub in cfg.profiles["economics_anchor"]["title_or_org_substrings"]):
        return True
    return any(rx.search(pre) for f in _compiled_fields(cfg) for rx, _t, _g in f["strong"])


# --------------------------------------------------------------------------- geography
def _geo_index(cfg: Config):
    if getattr(cfg, "_geo_idx", None):
        return cfg._geo_idx
    eu = []
    for country, d in cfg.geo["europe"].items():
        eu.append((country, d["tier"], [term_regex(n) for n in d["names"]], [term_regex(p) for p in d["places"]]))
    ne = cfg.geo["non_europe"]
    cfg._geo_idx = (eu, [term_regex(n) for n in ne["names"]], [term_regex(p) for p in ne["places"]])
    return cfg._geo_idx


def detect_country(location: str, text: str, cfg: Config, default: str | None = None) -> tuple[str, str]:
    """-> (country label, tier) where tier in west | other | non_europe | unknown."""
    eu, ne_names, ne_places = _geo_index(cfg)

    def score(s: str):
        s = norm(s)
        res = {}
        for country, tier, names, places in eu:
            v = 3 * sum(1 for r in names if r.search(s)) + sum(1 for r in places if r.search(s))
            if v:
                res[country] = (v, tier)
        ne = 3 * sum(1 for r in ne_names if r.search(s)) + sum(1 for r in ne_places if r.search(s))
        return res, ne

    for src in (location, None):
        s = location if src is not None else text
        if not s:
            continue
        if src is None:                       # free text: weight the first 400 chars double
            s = s[:400] + " " + s[:400] + " " + s[400:3000]
        res, ne = score(s)
        best = max(res.items(), key=lambda kv: kv[1][0]) if res else None
        if best and best[1][0] > ne:
            return best[0], best[1][1]
        if ne and (not best or ne > best[1][0]):
            return "Outside Europe", "non_europe"
        if best:                              # tie: prefer Europe
            return best[0], best[1][1]
    if default:
        d = norm(default)
        for country, tier, names, _ in eu:
            if norm(country) == d:
                return country, tier
        return default, "non_europe"
    return "Location unknown", "unknown"


# --------------------------------------------------------------------------- relevance
def _anchor(title_org: str, rest: str, cfg: Config) -> bool:
    a = cfg.profiles["economics_anchor"]
    if any(sub in title_org for sub in a["title_or_org_substrings"]):
        return True
    if any_term(title_org, a["title_or_org_terms"]):
        return True
    return rest.count("econom") >= a["body_min_hits"]


def _compiled_fields(cfg: Config):
    if getattr(cfg, "_fields", None):
        return cfg._fields
    out = []
    only = cfg.profiles.get("anchored_only", {})
    extra = cfg.profiles.get("extra_strong", {})
    for f in cfg.profiles["fields"]:
        gated = {norm(t) for t in only.get(f["id"], [])}
        strong = []
        for t in list(f["strong"]) + list(extra.get(f["id"], [])):
            strong.append((term_regex(t), t, norm(t) in gated))
        out.append({
            "id": f["id"], "label": f["label"], "who": f["who"], "weight": f.get("weight", 3.0),
            "strong": strong,
            "support": [(term_regex(t), t) for t in f.get("support", [])],
        })
    cfg._fields = out
    cfg._neg = [(term_regex(t), t) for t in cfg.profiles["negative_terms"]]
    return out


def score_fields(title: str, rest: str, anchored: bool, cfg: Config):
    """`title` should include declared field labels (EURAXESS 'Research Field', predoc.org 'Fields')."""
    out = []
    for f in _compiled_fields(cfg):
        raw, hits = 0, []
        for rx, term, gated in f["strong"]:
            if gated and not anchored:
                continue
            if rx.search(title):
                raw += 6
                hits.append(term)
            elif rx.search(rest):
                raw += 3
                hits.append(term)
        if anchored:
            for rx, term in f["support"]:
                if rx.search(title):
                    raw += 2
                    hits.append(term + "~")
                elif rx.search(rest):
                    raw += 1
                    hits.append(term + "~")
        out.append({"id": f["id"], "label": f["label"], "who": f["who"], "weight": f["weight"], "raw": min(raw, 18), "hits": hits})
    return out


def negative_score(title: str, rest: str, cfg: Config) -> tuple[int, list[str]]:
    _compiled_fields(cfg)
    sc, hits = 0, []
    for rx, term in cfg._neg:
        if rx.search(title):
            sc += 6
            hits.append(term)
        elif rx.search(rest):
            sc += 3
            hits.append(term)
    return sc, hits


# --------------------------------------------------------------------------- closed / stale
def is_closed(item: dict, cfg: Config, today: dt.date) -> str | None:
    """Reason string when the posting is evidently closed or stale, else None."""
    s = cfg.settings
    if getattr(cfg, "_closed_rx", None) is None:
        cfg._closed_rx = [re.compile(p, re.I) for p in s.get("closed_markers", [])]
    text = " ".join(filter(None, [item.get("snippet"), item.get("body")]))
    for rx in cfg._closed_rx:
        m = rx.search(text)
        if m:
            return f"posting closed ('{m.group(0)[:40]}')"
    max_age = s.get("max_age_without_deadline_days")
    posted = item.get("posted")
    if max_age and posted and not item.get("deadline"):
        try:
            age = (today - dt.date.fromisoformat(posted[:10])).days
        except ValueError:
            age = 0
        if age > max_age:
            return f"stale: posted {posted[:10]}, no deadline given"
    return None


# --------------------------------------------------------------------------- main entry
def evaluate(item: dict, cfg: Config, today: dt.date | None = None) -> dict:
    """item keys: title, org, location, snippet, fields, body, deadline(iso|None), rolling,
    site_tags, source_opts(dict: econ_specific, default_country, assume_type).
    Returns decision dict with tier in strong|adjacent|rejected."""
    today = today or dt.date.today()
    s = cfg.settings
    opts = item.get("source_opts") or {}
    title = item.get("title") or ""
    body = item.get("body") or ""
    meta_text = " ".join(filter(None, [item.get("snippet"), item.get("fields"), item.get("site_tags")]))
    full_for_type = body if body else meta_text

    d = {"tier": "rejected", "reason": "", "ptype": None, "country": None, "region": None,
         "who": [], "fields": [], "score": 0.0, "hits": [], "anchored": False}

    if any(o in norm(item.get("org") or "") for o in cfg.blocked_orgs):
        d["reason"] = "blocked organisation (config/easy.yaml)"
        return d

    closed = is_closed(item, cfg, today)
    if closed:
        d["reason"] = closed
        return d

    # 1) position type
    ptype, why = detect_type(title, full_for_type + " " + (item.get("site_tags") or ""), cfg, opts.get("assume_type"))
    tags_n = norm(item.get("site_tags") or "")
    if (ptype is None and re.search(r"phd|doctoral", tags_n) and not re.search(r"postdoc|professor|post doc", tags_n)
            and not any_term(norm(title), s["exclude_in_title"] + s.get("hard_exclude_in_title", []))):
        # board tagged it PhD (and nothing senior) but the title is generic: require a PhD word in the
        # posting text itself - the tags alone are not evidence
        text_only = " ".join(filter(None, [item.get("snippet"), item.get("fields"), body]))
        if any_term(norm(text_only), ["phd", "doctoral", "doctorate", "doktorand*", "promotion*", "doctorant*", "promovend*"]):
            ptype, why = "PhD", "ok (board tag + text)"
    if ptype is None:
        d["reason"] = why
        return d
    d["ptype"] = ptype

    # 2) geography
    loc_blob = " ".join(filter(None, [item.get("location"), item.get("org")]))
    country, tier = detect_country(item.get("location") or "", " ".join([title, item.get("org") or "", meta_text, body[:3000]]), cfg,
                                   default=opts.get("default_country") or item.get("country_default"))
    d["country"], d["region"] = country, tier
    if tier == "non_europe":
        d["reason"] = f"outside Europe ({country})"
        return d

    # 3) relevance
    t_n = norm(title)
    org_n = norm(item.get("org") or "")
    rest_n = norm(" ".join([meta_text, body]))
    fields_n = norm(item.get("fields") or "")
    anchored = _anchor(t_n + " " + org_n + " " + fields_n, rest_n, cfg)
    if opts.get("econ_specific") and not anchored:
        # an economics-only board: the board itself is a weak anchor, but only if the
        # posting itself touches economics-style vocabulary
        anchored = bool(any_term(rest_n, ["policy", "market*", "tax*", "labour", "labor", "welfare", "inequality"]))
    d["anchored"] = anchored
    # declared field labels count like title words (they name the topic of the post)
    fields = score_fields((t_n + " " + fields_n).strip(), rest_n, anchored, cfg)
    neg, neg_hits = negative_score(t_n, rest_n, cfg)
    best = max(fields, key=lambda f: f["raw"] * f["weight"])
    d["fields"] = [f for f in sorted(fields, key=lambda f: -f["raw"]) if f["raw"] >= 3][:3]
    d["hits"] = best["hits"][:8]

    if neg >= s["negative_reject_at"] and best["raw"] < s["strong_min"]:
        d["reason"] = "finance / management topic (" + ", ".join(neg_hits[:3]) + ")"
        return d

    strong_min = s["strong_min"]
    if best["raw"] >= strong_min:
        tier_out = "strong"
        if neg >= s["negative_demote_at"]:
            tier_out = "adjacent"
    elif anchored:
        if best["raw"] >= 3 or cfg.profiles.get("include_generic_economics", True):
            tier_out = "adjacent"
        else:
            d["reason"] = "economics posting without a matching topic"
            return d
    elif best["raw"] >= s["adjacent_min_without_anchor"]:
        tier_out = "adjacent"
    else:
        d["reason"] = "not about economics / no topic match"
        return d

    # who
    who = set()
    for f in fields:
        if f["raw"] >= 3:
            who.update(f["who"])
    if not who:
        who = set(cfg.profiles.get("generic_who", ["shayan", "zahra"]))
    d["who"] = sorted(who)
    d["tier"] = tier_out
    d["reason"] = "ok"
    top = best["raw"] * best["weight"]
    d["score"] = round(top + (4 if tier == "west" else 0) + (2 if tier == "other" else 0) + (1.5 if anchored else 0), 1)
    d["primary_field"] = best["label"] if best["raw"] >= 3 else "General economics"
    return d

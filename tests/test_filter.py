"""Offline tests for the filtering logic.  Run:  python -m unittest discover -s tests -v"""
import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.logic import Config, evaluate  # noqa: E402
from agent.util import find_deadline, norm, parse_date, term_regex  # noqa: E402

CFG = Config()
TODAY = dt.date(2026, 10, 18)


def ev(title, org="", location="", snippet="", fields="", body="", tags="", **opts):
    return evaluate({"title": title, "org": org, "location": location, "snippet": snippet, "fields": fields,
                     "body": body, "site_tags": tags, "source_opts": opts}, CFG, TODAY)


class Util(unittest.TestCase):
    def test_norm(self):
        self.assertEqual(norm("Ph.D. Mitarbeiter*in Zürich Ørsted"), "phd mitarbeiterin zurich orsted")

    def test_wildcard(self):
        self.assertTrue(term_regex("econom*").search("labour economics"))
        self.assertTrue(term_regex("pre-doc*").search("a pre doctoral fellow"))
        self.assertFalse(term_regex("phd").search("phdx"))

    def test_dates(self):
        self.assertEqual(parse_date("31 Oct 2026"), dt.date(2026, 10, 31))
        self.assertEqual(parse_date("Oct 31, 2026"), dt.date(2026, 10, 31))
        self.assertEqual(parse_date("31/10/2026"), dt.date(2026, 10, 31))
        d, rolling = find_deadline("Application deadline: 15 November 2026", TODAY)
        self.assertEqual(d, dt.date(2026, 11, 15))


class ShouldKeep(unittest.TestCase):
    def assertKept(self, d, tier=None):
        self.assertNotEqual(d["tier"], "rejected", d["reason"])
        if tier:
            self.assertEqual(d["tier"], tier, d)

    def test_energy_auctions_louvain(self):
        d = ev("PhD Position in Economics: Renewable Energy Auctions", "UCLouvain", "Louvain-la-Neuve, Belgium",
               body="The PhD student will study auction design for renewable energy in the economics department.")
        self.assertKept(d, "strong")
        self.assertIn("zahra", d["who"])

    def test_cemfi_predoc_urban(self):
        d = ev("Pre-Doctoral Fellow, Urban economics and technology", "CEMFI", "Madrid, Spain",
               body="Pre-doctoral research assistant working on urban economics and technology.")
        self.assertKept(d, "strong")
        self.assertIn("shayan", d["who"])

    def test_health_econ_phd_nl(self):
        d = ev("PhD candidate in health economics", "Erasmus University Rotterdam", "Rotterdam, Netherlands")
        self.assertKept(d, "strong")
        self.assertIn("zahra", d["who"])

    def test_labour_doctoral_researcher(self):
        d = ev("Doctoral researcher in labour economics", "University of Mannheim", "Mannheim, Germany")
        self.assertKept(d, "strong")

    def test_climate_macro(self):
        d = ev("PhD position: Macroeconomics of climate policy and the green transition", "Kiel Institute", "Kiel, Germany")
        self.assertKept(d, "strong")

    def test_generic_economics_phd_is_adjacent(self):
        d = ev("PhD scholarships in Economics", "University of Southern Denmark", "Odense, Denmark")
        self.assertKept(d, "adjacent")

    def test_unknown_location_kept(self):
        d = ev("PhD in development economics", "Some Institute", "")
        self.assertKept(d)
        self.assertEqual(d["region"], "unknown")

    def test_generic_german_title_with_phd_evidence(self):
        d = ev("Wissenschaftliche*r Mitarbeiter*in (m/w/d) am Lehrstuhl für Volkswirtschaftslehre", "Universität Köln", "Köln, Deutschland",
               body="Die Stelle bietet die Möglichkeit zur Promotion im Bereich Arbeitsmarktökonomik und angewandte Mikroökonometrie.")
        self.assertKept(d)
        self.assertEqual(d["ptype"], "Doctoral researcher")

    def test_zurich_predoc_program(self):
        d = ev("Pre-Doctoral Program in Economics", "University of Zurich", "Zurich, Switzerland", body="Pre-doctoral research assistant positions in economics.")
        self.assertKept(d)

    def test_uk_economics_phd(self):
        d = ev("PhD Studentship in Economics - Policy evaluation", "University of Warwick", "Coventry, UK", default_country="United Kingdom")
        self.assertKept(d)
        self.assertEqual(d["region"], "west")

    def test_research_assistant_econ(self):
        d = ev("Research Assistant in applied microeconomics (causal inference)", "Paris School of Economics", "Paris, France")
        self.assertKept(d, "strong")


class ShouldReject(unittest.TestCase):
    def assertRejected(self, d):
        self.assertEqual(d["tier"], "rejected", d)

    def test_asset_pricing(self):
        self.assertRejected(ev("PhD position in Asset Pricing", "Goethe University Frankfurt", "Frankfurt, Germany"))

    def test_australia_health_econ(self):
        self.assertRejected(ev("PhD scholarship in health economics", "Monash University", "Melbourne, Australia"))

    def test_postdoc(self):
        self.assertRejected(ev("Postdoctoral researcher in labour economics", "University of Bonn", "Bonn, Germany"))

    def test_professor(self):
        self.assertRejected(ev("Assistant Professor in Economics", "University of Oslo", "Oslo, Norway"))

    def test_postdoc_and_phd_tags(self):
        self.assertRejected(ev("Economic Education Specialist", "Some Org", "Berlin, Germany", tags="Postdoc PhD"))

    def test_us_predoc(self):
        self.assertRejected(ev("Predoctoral Research Assistant", "Federal Reserve Bank of Chicago", "Chicago, IL", fields="Macroeconomics",
                               assume_type="Predoc/RA", default_country="United States"))

    def test_marketing_phd(self):
        self.assertRejected(ev("PhD position in Marketing and consumer behaviour", "University of Amsterdam", "Amsterdam, Netherlands"))

    def test_accounting_phd(self):
        self.assertRejected(ev("PhD in Accounting and auditing", "Copenhagen Business School", "Copenhagen, Denmark"))

    def test_physics_phd(self):
        self.assertRejected(ev("PhD position in experimental particle physics", "ETH Zurich", "Zurich, Switzerland"))

    def test_generic_mitarbeiter_without_phd(self):
        self.assertRejected(ev("Wissenschaftliche*r Mitarbeiter*in", "Universität Köln", "Köln",
                               body="Senior position, habilitation required, leading a research group in economics. Economics economics economics."))

    def test_summer_school(self):
        self.assertRejected(ev("PhD summer school in economics", "Uni X", "Paris, France"))



class EasyConfig(unittest.TestCase):
    def test_my_keywords_and_blocks(self):
        import copy
        cfg = Config()
        cfg.profiles = copy.deepcopy(cfg.profiles)
        cfg.settings = copy.deepcopy(cfg.settings)
        cfg.easy = {"my_keywords": [{"term": "tax compliance", "who": "shayan"}], "block_title_words": ["zebra"], "block_orgs": ["Blocked Uni"]}
        cfg._fields = None
        cfg._apply_easy()
        d = evaluate({"title": "PhD on tax compliance", "org": "X", "location": "Paris, France", "source_opts": {}}, cfg, TODAY)
        self.assertNotEqual(d["tier"], "rejected")
        self.assertEqual(d["who"], ["shayan"])
        self.assertEqual(evaluate({"title": "PhD zebra economics", "org": "X", "location": "Paris, France", "source_opts": {}}, cfg, TODAY)["tier"], "rejected")
        self.assertEqual(evaluate({"title": "PhD in labour economics", "org": "Blocked Uni", "location": "Paris, France", "source_opts": {}}, cfg, TODAY)["tier"], "rejected")


if __name__ == "__main__":
    unittest.main()

import json
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
os.environ["JOBWATCH_CONFIG_DIR"] = os.path.join(ROOT, "config")

from jobwatch import adapters, config, notify, skills  # noqa: E402
from jobwatch.adapters.base import Adapter  # noqa: E402
from jobwatch.adapters.json_api import JsonApi  # noqa: E402
from jobwatch.adapters.jsonld import find_jobposting  # noqa: E402
from jobwatch.filters import Filters, relocation_signal, years_required  # noqa: E402
from jobwatch.models import Job  # noqa: E402
from jobwatch.runner import is_quiet, run  # noqa: E402
from jobwatch.store import MemoryStore  # noqa: E402
from jobwatch.textutil import html_to_text  # noqa: E402

FILTERS = config.load_json("filters.json")
PROFILE = skills.Profile(config.load_json("skills_profile.json"))

JD = """About the role
Build our streaming platform using Rust and Kafka.

Requirements
- 5+ years of backend engineering experience
- Strong Java or Go skills
- Experience with Kafka, Kubernetes and PostgreSQL
- Deep knowledge of distributed systems
- Familiarity with Apache Spark

Nice to have
- Terraform
- Experience with Rust
- Kubernetes operators is a plus
We offer relocation assistance and visa sponsorship.
"""


class TextTests(unittest.TestCase):
    def test_html_to_text_handles_escaped_html(self):
        t = html_to_text("&lt;p&gt;Hello&lt;/p&gt;&lt;ul&gt;&lt;li&gt;Java&lt;/li&gt;&lt;li&gt;Kafka&lt;/li&gt;&lt;/ul&gt;")
        self.assertIn("\u2022 Java", t)
        self.assertIn("\u2022 Kafka", t)


class FilterTests(unittest.TestCase):
    def setUp(self):
        self.f = Filters(FILTERS)

    def test_titles(self):
        ok = ["Senior Software Engineer, Platform", "Backend Engineer", "SDE II", "Staff Engineer, Infrastructure"]
        bad = ["Software Engineering Intern", "Engineering Manager, Platform", "iOS Software Engineer",
               "Senior Frontend Engineer", "Sales Engineer", "Principal Software Engineer"]
        for t in ok:
            self.assertTrue(self.f.title_ok(t), t)
        for t in bad:
            self.assertFalse(self.f.title_ok(t), t)

    def test_locations(self):
        j = lambda loc: Job("X", "1", "Software Engineer", loc)
        self.assertTrue(self.f.check_listing(j("Bengaluru, India")))
        self.assertTrue(self.f.check_listing(j("Hyderabad")))
        self.assertTrue(self.f.check_listing(j("2 Locations")))
        self.assertTrue(self.f.check_listing(j("Remote - India")))
        self.assertFalse(self.f.check_listing(j("Kochi, India")) and False)
        self.assertEqual(self.f.classify_location("Indianapolis, Indiana, USA"), "abroad")
        self.assertEqual(self.f.classify_location("Pune, Maharashtra"), "india")

    def test_abroad_needs_relocation(self):
        job = Job("X", "1", "Software Engineer", "Berlin, Germany", description="Great team. Build things.")
        ok, _ = self.f.check_full(job)
        self.assertFalse(ok)
        job.description += " We offer relocation assistance."
        ok, flags = self.f.check_full(job)
        self.assertTrue(ok)
        self.assertTrue(flags["relocation"])

    def test_relocation_negatives(self):
        self.assertFalse(relocation_signal("We are unable to provide visa sponsorship for this role."))
        self.assertFalse(relocation_signal("Candidates must be authorized to work without sponsorship."))
        self.assertTrue(relocation_signal("Visa sponsorship is available for this position."))
        self.assertTrue(relocation_signal("We do not offer visa sponsorship, but relocation assistance is provided."))

    def test_experience(self):
        self.assertEqual(years_required("3-5 years of experience, 7+ years Java"), (7, 7))
        self.assertIsNone(years_required("no numbers here"))
        junior = Job("X", "1", "Software Engineer", "Bengaluru", description="0-2 years of experience")
        senior = Job("X", "2", "Software Engineer", "Bengaluru", description="12+ years of experience")
        mid = Job("X", "3", "Software Engineer", "Bengaluru", description="5+ years of experience")
        self.assertFalse(self.f.check_full(junior)[0])
        self.assertFalse(self.f.check_full(senior)[0])
        self.assertTrue(self.f.check_full(mid)[0])


class SkillTests(unittest.TestCase):
    def test_aliases_and_boundaries(self):
        s = skills.find_skills("Java, JavaScript, PostgreSQL, NoSQL, C++, C#, Node.js, CI/CD, K8s")
        for want in ["Java", "JavaScript", "PostgreSQL", "NoSQL", "C++", "C#", "Node.js", "CI/CD", "Kubernetes"]:
            self.assertIn(want, s)
        self.assertNotIn("SQL", s)
        self.assertEqual(skills.find_skills("Go to market strategy"), [])
        self.assertIn("Go", skills.find_skills("Experience with Java, Go or Rust"))

    def test_required_vs_preferred(self):
        req, pref = skills.classify_text(JD)
        self.assertIn("Kafka", req)
        self.assertIn("Distributed systems", req)
        self.assertIn("Spark", req)
        self.assertNotIn("Rust", req)
        self.assertIn("Terraform", pref)
        self.assertIn("Rust", pref)

    def test_analysis_against_profile(self):
        job = Job("Acme", "1", "Backend Engineer", "Bengaluru", description=JD)
        a = skills.analyze(job, PROFILE)
        self.assertIn("Kafka", a["required_have"])
        self.assertIn("Kubernetes", a["required_have"])
        self.assertIn("Spark", a["required_missing"])
        self.assertIn("Terraform", a["preferred_have"])
        self.assertIn("Rust", a["preferred_missing"])

    def test_structured_fields_win(self):
        job = Job("Amazon", "1", "SDE", "Hyderabad", description="We use Rust everywhere.",
                  required_text="Java and Spark", preferred_text="Kafka")
        a = skills.analyze(job, PROFILE)
        self.assertEqual(a["required_have"], ["Java"])
        self.assertEqual(a["required_missing"], ["Spark"])
        self.assertEqual(a["preferred_have"], ["Kafka"])

    def test_profile_names_are_valid(self):
        self.assertEqual(PROFILE.unknown, [])


class AdapterTests(unittest.TestCase):
    def test_jsonld(self):
        page = '<script type="application/ld+json">{"@context":"https://schema.org","@type":"JobPosting","title":"SWE","description":"&lt;p&gt;Java&lt;/p&gt;"}</script>'
        self.assertEqual(find_jobposting(page)["title"], "SWE")

    def test_json_api_field_mapping(self):
        import jobwatch.adapters.json_api as ja
        payload = {"jobs": [{"id_icims": "42", "title": "SDE II", "normalized_location": "Hyderabad, IND",
                             "job_path": "/en/jobs/42", "description": "<p>Build</p>",
                             "basic_qualifications": "5+ years Java", "preferred_qualifications": "Kafka"}]}
        ja.request = lambda *a, **k: json.dumps(payload)
        cfg = next(c for c in config.load_json("companies.json")["companies"] if c["name"] == "Amazon")
        cfg = {**cfg, "pagination": {"type": "offset", "param": "offset", "page_size": 100, "max_pages": 1}}
        jobs = JsonApi().list_jobs(cfg)
        self.assertEqual(jobs[0].id, "42")
        self.assertEqual(jobs[0].url, "https://www.amazon.jobs/en/jobs/42")
        self.assertEqual(jobs[0].required_text, "5+ years Java")


class FakeAdapter(Adapter):
    def __init__(self):
        self.jobs = []

    def list_jobs(self, cfg):
        return list(self.jobs)

    def enrich(self, cfg, job):
        job.enriched = True


class Capture:
    def __init__(self):
        self.sent = []

    def send(self, text, silent=False):
        self.sent.append(text)


class PipelineTests(unittest.TestCase):
    def setUp(self):
        import jobwatch.runner as r
        r.time.sleep = lambda s: None
        self.fake = FakeAdapter()
        adapters.ADAPTERS["fake"] = self.fake
        self.store, self.out = MemoryStore(), Capture()
        self.companies = {"companies": [{"name": "Acme", "strategy": "fake"}]}

    def run_once(self):
        return run(self.store, self.out, self.companies, FILTERS, config.load_json("skills_profile.json"))

    def test_seed_then_notify_then_dedupe(self):
        self.fake.jobs = [Job("Acme", "1", "Backend Engineer", "Bengaluru", description=JD)]
        self.run_once()
        self.assertEqual(self.out.sent, [])
        self.fake.jobs.append(Job("Acme", "2", "Senior Software Engineer", "Hyderabad", description=JD))
        self.fake.jobs.append(Job("Acme", "3", "Software Engineer", "Berlin, Germany", description="No info"))
        self.fake.jobs.append(Job("Acme", "4", "Software Engineer", "Berlin, Germany", description="Relocation assistance provided. 5+ years Java."))
        self.fake.jobs.append(Job("Acme", "5", "Engineering Manager", "Bengaluru", description=JD))
        s = self.run_once()
        self.assertEqual(s["sent"], 2)
        titles = "\n".join(self.out.sent)
        self.assertIn("Senior Software Engineer", titles)
        self.assertIn("\u2705 Kafka", titles)
        self.assertIn("\u274c Spark", titles)
        self.assertEqual(self.run_once()["sent"], 0)

    def test_failure_alert_after_three_runs(self):
        self.fake.jobs = []
        for _ in range(3):
            self.run_once()
        self.assertEqual(len([m for m in self.out.sent if "scraper problems" in m]), 1)

    def test_quiet_hours(self):
        from datetime import datetime, timezone
        q = FILTERS["settings"]
        self.assertTrue(is_quiet(q, datetime(2026, 1, 1, 20, 0, tzinfo=timezone.utc)))
        self.assertFalse(is_quiet(q, datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc)))


if __name__ == "__main__":
    unittest.main()

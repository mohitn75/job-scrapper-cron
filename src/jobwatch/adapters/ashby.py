from ..http import HttpError, get_json
from ..models import Job
from ..textutil import html_to_text
from .base import Adapter

API = "https://api.ashbyhq.com/posting-api/job-board/{board}"


class Ashby(Adapter):
    @staticmethod
    def probe(slug):
        try:
            d = get_json(API.format(board=slug), retries=0, timeout=15)
        except HttpError:
            return False
        return isinstance(d, dict) and "jobs" in d

    def list_jobs(self, cfg):
        d = get_json(API.format(board=cfg["board"]))
        jobs = []
        for j in d.get("jobs", []):
            if j.get("isListed") is False:
                continue
            locs = [j.get("location") or ""]
            locs += [s.get("location", "") for s in j.get("secondaryLocations") or [] if isinstance(s, dict)]
            jobs.append(Job(company=cfg["name"], id=str(j["id"]), title=j.get("title", ""),
                            location=", ".join(l for l in locs if l),
                            url=j.get("jobUrl", ""), posted=j.get("publishedAt", ""), raw=j))
        return jobs

    def enrich(self, cfg, job):
        j = job.raw
        job.description = j.get("descriptionPlain") or html_to_text(j.get("descriptionHtml", ""))
        job.enriched = True

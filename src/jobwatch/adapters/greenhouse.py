from ..http import HttpError, get_json
from ..models import Job
from ..textutil import html_to_text
from .base import Adapter

API = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs"


class Greenhouse(Adapter):
    @staticmethod
    def probe(slug):
        try:
            d = get_json(API.format(board=slug), retries=0, timeout=15)
        except HttpError:
            return False
        return isinstance(d, dict) and "jobs" in d

    def list_jobs(self, cfg):
        d = get_json(API.format(board=cfg["board"]) + "?content=true")
        jobs = []
        for j in d.get("jobs", []):
            jobs.append(Job(
                company=cfg["name"], id=str(j["id"]), title=j.get("title", ""),
                location=(j.get("location") or {}).get("name", ""),
                url=j.get("absolute_url", ""), posted=j.get("updated_at", ""),
                raw={"content": j.get("content", "")}))
        return jobs

    def enrich(self, cfg, job):
        job.description = html_to_text(job.raw.get("content", ""))
        job.enriched = True

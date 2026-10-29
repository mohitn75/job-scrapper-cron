from ..http import HttpError, get_json
from ..models import Job
from ..textutil import html_to_text
from .base import Adapter

HOSTS = {"us": "api.lever.co", "eu": "api.eu.lever.co"}


def _url(site, region="us"):
    return f"https://{HOSTS.get(region, HOSTS['us'])}/v0/postings/{site}?mode=json"


class Lever(Adapter):
    @staticmethod
    def probe(slug):
        """Returns the region ('us' or 'eu') if the Lever site exists, else None."""
        for region in ("us", "eu"):
            try:
                d = get_json(_url(slug, region), retries=0, timeout=15)
            except HttpError:
                continue
            if isinstance(d, list):
                return region
        return None

    def list_jobs(self, cfg):
        data = get_json(_url(cfg["site"], cfg.get("region", "us")))
        jobs = []
        for j in data:
            cats = j.get("categories") or {}
            loc = ", ".join(cats.get("allLocations") or [cats.get("location") or ""])
            jobs.append(Job(company=cfg["name"], id=str(j["id"]), title=j.get("text", ""),
                            location=loc, url=j.get("hostedUrl", ""), raw=j))
        return jobs

    def enrich(self, cfg, job):
        j = job.raw
        parts = [j.get("descriptionPlain") or html_to_text(j.get("description", ""))]
        for lst in j.get("lists") or []:
            parts.append(lst.get("text", "") + ":")
            parts.append(html_to_text(lst.get("content", "")))
        parts.append(j.get("additionalPlain") or html_to_text(j.get("additional", "")))
        job.description = "\n".join(p for p in parts if p)
        job.enriched = True

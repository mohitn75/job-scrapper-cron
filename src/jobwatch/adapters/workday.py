import json

from ..http import get_json, polite_sleep, request
from ..models import Job
from ..textutil import html_to_text
from .base import Adapter


def _base(cfg):
    return f"https://{cfg['host']}/wday/cxs/{cfg['tenant']}/{cfg['site']}"


class Workday(Adapter):
    """Workday career sites. cfg: host, tenant, site, optional search_terms, max_pages."""

    def list_jobs(self, cfg):
        terms = cfg.get("search_terms") or ["software engineer", "backend", "platform"]
        found = {}
        for term in terms:
            for page in range(cfg.get("max_pages", 3)):
                body = {"appliedFacets": cfg.get("facets", {}), "limit": 20,
                        "offset": page * 20, "searchText": term}
                d = json.loads(request(_base(cfg) + "/jobs", method="POST", body=body))
                posts = d.get("jobPostings", [])
                for p in posts:
                    path = p.get("externalPath")
                    if path and path not in found:
                        found[path] = p
                polite_sleep(cfg)
                if len(posts) < 20:
                    break
        return [Job(company=cfg["name"], id=path, title=p.get("title", ""),
                    location=p.get("locationsText", ""), posted=p.get("postedOn", ""),
                    url=f"https://{cfg['host']}/en-US/{cfg['site']}{path}")
                for path, p in found.items()]

    def enrich(self, cfg, job):
        d = get_json(_base(cfg) + job.id)
        info = d.get("jobPostingInfo", {})
        job.description = html_to_text(info.get("jobDescription", ""))
        locs = [info.get("location", "")] + list(info.get("additionalLocations") or [])
        country = (info.get("country") or {}).get("descriptor", "")
        text = ", ".join(l for l in locs if l)
        job.location = f"{text}, {country}" if country and country not in text else (text or job.location)
        job.url = info.get("externalUrl") or job.url
        job.enriched = True
        polite_sleep(cfg)

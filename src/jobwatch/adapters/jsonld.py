import html
import json
import re

from .. import http
from ..models import Job
from ..textutil import html_to_text
from .base import Adapter

_LD = re.compile(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.I | re.S)
_LOC = re.compile(r"<loc>\s*([^<]+?)\s*</loc>", re.I)


def _walk(node):
    if isinstance(node, list):
        for n in node:
            yield from _walk(n)
    elif isinstance(node, dict):
        yield node
        if "@graph" in node:
            yield from _walk(node["@graph"])


def find_jobposting(page):
    for m in _LD.finditer(page):
        try:
            data = json.loads(html.unescape(m.group(1)).strip())
        except ValueError:
            continue
        for node in _walk(data):
            t = node.get("@type")
            if t == "JobPosting" or (isinstance(t, list) and "JobPosting" in t):
                return node
    return None


def _loc_text(posting):
    locs = posting.get("jobLocation") or []
    locs = [locs] if isinstance(locs, dict) else locs
    out = []
    for l in locs:
        a = (l or {}).get("address") or {}
        if isinstance(a, str):
            out.append(a)
            continue
        country = a.get("addressCountry")
        country = country.get("name") if isinstance(country, dict) else country
        out.append(", ".join(x for x in [a.get("addressLocality"), a.get("addressRegion"), country] if x))
    return "; ".join(o for o in out if o)


class JsonLd(Adapter):
    """Sitemap + schema.org JobPosting pages. cfg: sitemap_url, url_regex, optional max_urls."""

    def _collect(self, url, pat, depth, cap, cfg):
        if not http.allowed(url):
            raise PermissionError(f"robots.txt disallows {url}")
        xml = http.request(url)
        urls = [html.unescape(u) for u in _LOC.findall(xml)]
        out = []
        for u in urls:
            if u.lower().endswith(".xml") and depth < 1:
                flt = cfg.get("sitemap_filter")
                if not flt or re.search(flt, u):
                    out += self._collect(u, pat, depth + 1, cap, cfg)
            elif pat.search(u):
                out.append(u)
            if len(out) >= cap:
                break
        return out[:cap]

    def list_jobs(self, cfg):
        pat = re.compile(cfg["url_regex"])
        urls = self._collect(cfg["sitemap_url"], pat, 0, cfg.get("max_urls", 400), cfg)
        return [Job(company=cfg["name"], id=u, url=u) for u in urls]

    def enrich(self, cfg, job):
        if not http.allowed(job.url):
            raise PermissionError(f"robots.txt disallows {job.url}")
        posting = find_jobposting(http.request(job.url))
        if not posting:
            raise ValueError("no JobPosting data on page")
        job.title = posting.get("title", job.title)
        job.location = _loc_text(posting) or job.location
        job.description = html_to_text(posting.get("description", ""))
        job.posted = posting.get("datePosted", "")
        job.enriched = True
        http.polite_sleep(cfg)

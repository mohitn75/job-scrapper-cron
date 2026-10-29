import json

from ..http import polite_sleep, request, with_params
from ..models import Job
from .base import Adapter
from ..textutil import html_to_text


def get_path(obj, path):
    cur = obj
    for part in str(path).split("."):
        if cur is None:
            return None
        if isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return None
        elif isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def as_text(v):
    if v is None:
        return ""
    if isinstance(v, list):
        return "\n".join(as_text(x) for x in v)
    if isinstance(v, dict):
        return json.dumps(v)
    s = str(v)
    return html_to_text(s) if "<" in s else s


class JsonApi(Adapter):
    """Generic config-driven JSON endpoint. See config/companies.json (Amazon) for an example."""

    def list_jobs(self, cfg):
        pg = cfg.get("pagination") or {}
        pages = pg.get("max_pages", 1) if pg else 1
        size = pg.get("page_size", 0)
        method = cfg.get("method", "GET")
        fields = cfg["fields"]
        jobs = []
        for i in range(pages):
            url, body = cfg["url"], cfg.get("body")
            if pg:
                value = i * size if pg.get("type", "offset") == "offset" else i + pg.get("start", 1)
                if pg.get("in") == "body" and isinstance(body, dict):
                    body = {**body, pg["param"]: value}
                else:
                    url = with_params(url, **{pg["param"]: value})
            raw = request(url, method=method, headers=cfg.get("headers"), body=body)
            items = get_path(json.loads(raw), cfg.get("jobs_path", "")) if cfg.get("jobs_path") else json.loads(raw)
            if not items:
                break
            for it in items:
                link = as_text(get_path(it, fields["url"])) if fields.get("url") else ""
                if link and not link.startswith("http"):
                    link = cfg.get("url_prefix", "") + link
                desc_paths = fields.get("description", [])
                desc_paths = [desc_paths] if isinstance(desc_paths, str) else desc_paths
                jobs.append(Job(
                    company=cfg["name"], id=as_text(get_path(it, fields["id"])),
                    title=as_text(get_path(it, fields["title"])),
                    location=as_text(get_path(it, fields["location"])), url=link,
                    description="\n".join(as_text(get_path(it, p)) for p in desc_paths),
                    required_text=as_text(get_path(it, fields["required"])) if fields.get("required") else "",
                    preferred_text=as_text(get_path(it, fields["preferred"])) if fields.get("preferred") else "",
                    enriched=True))
            polite_sleep(cfg)
            if size and len(items) < size:
                break
        return jobs

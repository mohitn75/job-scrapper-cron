import re

from . import http

_PATTERNS = [
    ("greenhouse", "board", re.compile(r"greenhouse\.io/embed/job_board(?:/js)?\?for=([\w-]+)", re.I), {}),
    ("greenhouse", "board", re.compile(r"(?:boards|job-boards)(?:\.eu)?\.greenhouse\.io/(?!embed)([\w-]+)", re.I), {}),
    ("lever", "site", re.compile(r"jobs\.eu\.lever\.co/([\w-]+)", re.I), {"region": "eu"}),
    ("lever", "site", re.compile(r"jobs\.lever\.co/([\w-]+)", re.I), {}),
    ("ashby", "board", re.compile(r"jobs\.ashbyhq\.com/([\w%.\-]+)", re.I), {}),
]
_WORKDAY = re.compile(r"https?://([\w-]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}(?:-[A-Za-z]{2})?/)?([\w\-]+)", re.I)


def from_text(text):
    """Find a known job-platform reference inside a URL or page HTML."""
    m = _WORKDAY.search(text or "")
    if m and m.group(3).lower() not in ("wday", "login"):
        tenant, wd, site = m.groups()
        return {"strategy": "workday", "host": f"{tenant}.{wd}.myworkdayjobs.com", "tenant": tenant, "site": site}
    for strategy, key, pat, extra in _PATTERNS:
        m = pat.search(text or "")
        if m:
            return {"strategy": strategy, key: m.group(1), **extra}
    return None


def slug_candidates(entry):
    if entry.get("slugs"):
        return list(entry["slugs"])
    base = re.sub(r"\(.*?\)", "", entry["name"]).lower()
    words = re.findall(r"[a-z0-9]+", base)
    if not words:
        return []
    cands = ["".join(words), "-".join(words)]
    if len(words) > 1:
        cands.append(words[0])
    cands += [cands[0] + "inc", cands[0] + "hq"]
    return list(dict.fromkeys(cands))


def discover(entry):
    """Work out how to read a company's jobs from its name and optional careers_url."""
    from .adapters.ashby import Ashby
    from .adapters.greenhouse import Greenhouse
    from .adapters.lever import Lever

    url = entry.get("careers_url")
    if url:
        found = from_text(url)
        if found:
            return found
        try:
            if http.allowed(url):
                found = from_text(http.request(url, retries=1))
                if found:
                    return found
        except Exception:
            pass
    for slug in slug_candidates(entry):
        if Greenhouse.probe(slug):
            return {"strategy": "greenhouse", "board": slug}
        region = Lever.probe(slug)
        if region:
            return {"strategy": "lever", "site": slug, "region": region}
        if Ashby.probe(slug):
            return {"strategy": "ashby", "board": slug}
    return None

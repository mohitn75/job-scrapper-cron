import gzip
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from urllib.robotparser import RobotFileParser

UA = os.environ.get("JOBWATCH_USER_AGENT", "JobWatch/1.0 (personal job alerts; low volume)")
DEFAULT_TIMEOUT = 25


class HttpError(Exception):
    def __init__(self, status, url):
        super().__init__(f"HTTP {status} for {url}")
        self.status = status
        self.url = url


def request(url, method="GET", headers=None, body=None, timeout=DEFAULT_TIMEOUT, retries=2):
    hdrs = {
        "User-Agent": UA,
        "Accept-Encoding": "gzip",
        "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
    }
    if headers:
        hdrs.update(headers)
    data = None
    if body is not None:
        if isinstance(body, (dict, list)):
            body = json.dumps(body)
            hdrs.setdefault("Content-Type", "application/json")
        data = body.encode("utf-8") if isinstance(body, str) else body
    attempt = 0
    while True:
        try:
            req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                if resp.headers.get("Content-Encoding", "").lower() == "gzip":
                    raw = gzip.decompress(raw)
                return raw.decode(resp.headers.get_content_charset() or "utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                attempt += 1
                time.sleep(2 * attempt)
                continue
            raise HttpError(e.code, url) from None
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt < retries:
                attempt += 1
                time.sleep(2 * attempt)
                continue
            raise


def get_json(url, **kw):
    return json.loads(request(url, **kw))


def with_params(url, **params):
    parts = urllib.parse.urlparse(url)
    q = dict(urllib.parse.parse_qsl(parts.query))
    q.update({k: str(v) for k, v in params.items()})
    return urllib.parse.urlunparse(parts._replace(query=urllib.parse.urlencode(q)))


_robots = {}


def allowed(url):
    """robots.txt check for HTML pages (public JSON APIs are not checked)."""
    p = urllib.parse.urlparse(url)
    base = f"{p.scheme}://{p.netloc}"
    rp = _robots.get(base)
    if rp is None:
        rp = RobotFileParser()
        try:
            rp.parse(request(base + "/robots.txt", retries=0, timeout=10).splitlines())
        except HttpError as e:
            if 400 <= e.status < 500:
                rp.parse([])
            else:
                rp.disallow_all = True
        except Exception:
            rp.disallow_all = True
        _robots[base] = rp
    return rp.can_fetch(UA, url)


def polite_sleep(cfg):
    time.sleep(cfg.get("delay", 0.3))

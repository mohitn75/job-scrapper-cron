import re

DEFAULT_MARKERS = ["india", "bengaluru", "bangalore", "hyderabad", "pune", "mumbai", "gurgaon",
                   "gurugram", "noida", "delhi", "chennai", "kolkata", "ahmedabad", "kochi"]


def _wb(words):
    words = [w.lower() for w in words if w]
    if not words:
        return None
    alt = "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))
    return re.compile(r"(?<![a-z])(?:%s)(?![a-z])" % alt, re.I)


_NEG = [re.compile(p, re.I) for p in [
    r"(?:not|n't|never)\s+(?:\w+\s+){0,3}(?:sponsor|sponsorship)",
    r"(?:unable|cannot|can't|won't)\s+(?:\w+\s+){0,4}(?:sponsor|sponsorship|visa)",
    r"without\s+(?:\w+\s+){0,3}sponsorship",
    r"\bno\s+(?:visa\s+)?sponsorship",
    r"sponsorship\s+(?:is\s+)?not\s+(?:available|offered|provided)",
    r"(?:not|n't)\s+(?:able\s+to\s+)?(?:offer|provide)\s+(?:\w+\s+){0,2}(?:visa|immigration)",
]]
_POS_RELOC = [re.compile(p, re.I) for p in [
    r"relocation\s+(?:assistance|support|package|bonus|benefits?|allowance|available|offered|provided|help)",
    r"relocation\s+is\s+(?:available|offered|provided|supported)",
    r"(?:offer|offers|provide|provides|include|includes|including)\s+(?:a\s+)?(?:generous\s+)?relocation",
    r"(?:will|can|may|able\s+to)\s+(?:offer|provide|support|assist\s+with)\s+(?:with\s+)?relocation",
    r"relocation\s+sponsorship",
    r"assist\s+with\s+relocation",
    r"relocate\s+you",
]]
_POS_VISA = [re.compile(p, re.I) for p in [
    r"visa\s+(?:sponsorship|support|assistance)",
    r"sponsor(?:ship)?\s+(?:is\s+)?(?:available|provided|offered)",
    r"(?:we|will|can)\s+(?:also\s+)?sponsor\s+(?:\w+\s+){0,2}(?:visa|work|immigration|employment|candidates|applicants|permit)",
    r"immigration\s+(?:support|assistance|sponsorship)",
]]


def relocation_signal(text):
    t = (text or "").lower()
    reloc = any(p.search(t) for p in _POS_RELOC)
    visa_pos = any(p.search(t) for p in _POS_VISA)
    visa_neg = any(p.search(t) for p in _NEG)
    return reloc or (visa_pos and not visa_neg)


_RANGE = re.compile(r"(\d{1,2})\s*\+?\s*(?:-|\u2013|\u2014|to)\s*(\d{1,2})\s*\+?\s*(?:years|yrs)", re.I)
_SINGLE = re.compile(r"(\d{1,2})\s*(?:\+|plus)?\s*(?:years|yrs)", re.I)


def years_required(text):
    """Return (lowest_headline, highest_headline) years mentioned, or None."""
    text = text or ""
    los, his, spans = [], [], []
    for m in _RANGE.finditer(text):
        a, b = int(m.group(1)), int(m.group(2))
        if a <= b <= 30:
            los.append(a)
            his.append(b)
            spans.append(m.span())
    for m in _SINGLE.finditer(text):
        if any(s < m.end() and m.start() < e for s, e in spans):
            continue
        n = int(m.group(1))
        if 0 < n <= 30:
            los.append(n)
            his.append(n)
    return (max(los), max(his)) if los else None


class Filters:
    def __init__(self, cfg):
        t = cfg.get("title", {})
        self.inc = _wb(t.get("include", []))
        self.exc = _wb(t.get("exclude", []))
        loc = cfg.get("locations", {})
        india = loc.get("india", {})
        self.markers = _wb(india.get("markers", DEFAULT_MARKERS))
        self.accept = _wb(india.get("accept_cities", ["bengaluru", "bangalore", "hyderabad"]))
        self.accept_remote = india.get("accept_remote_india", True)
        ab = loc.get("abroad", {})
        self.abroad_on = ab.get("enabled", True)
        self.countries = [c.lower() for c in ab.get("countries_allow", [])]
        self.need_reloc = ab.get("require_relocation_signal", True)
        ex = cfg.get("experience", {})
        self.min_ok = ex.get("min_years_acceptable", 3)
        self.max_req = ex.get("max_years_required", 9)

    def title_ok(self, title):
        if not title:
            return True
        if self.exc and self.exc.search(title):
            return False
        return bool(self.inc.search(title)) if self.inc else True

    def classify_location(self, loc):
        l = (loc or "").lower().strip()
        if not l or re.fullmatch(r"\d+\s+locations?", l):
            return "unknown"
        if self.markers and self.markers.search(l):
            return "india"
        return "abroad"

    def _india_accepted(self, loc):
        l = loc.lower()
        if self.accept and self.accept.search(l):
            return True
        if self.accept_remote and "remote" in l:
            return True
        return l.strip() == "india"

    def _abroad_accepted(self, loc):
        if not self.abroad_on:
            return False
        l = loc.lower()
        return not self.countries or any(c in l for c in self.countries)

    def _location_ok(self, loc):
        c = self.classify_location(loc)
        if c == "unknown":
            return True
        return self._india_accepted(loc) if c == "india" else self._abroad_accepted(loc)

    def check_listing(self, job):
        """Cheap check on listing-level data (title and location)."""
        return self.title_ok(job.title) and self._location_ok(job.location)

    def check_full(self, job):
        """Full check once the description is available. Returns (ok, flags)."""
        flags = {"relocation": None, "years": None}
        if not self.title_ok(job.title) or not self._location_ok(job.location):
            return False, flags
        full = " ".join([job.description, job.required_text, job.preferred_text])
        cls = self.classify_location(job.location)
        if cls in ("abroad", "unknown"):
            flags["relocation"] = relocation_signal(full)
            if cls == "abroad" and self.need_reloc and not flags["relocation"]:
                return False, flags
        yrs = years_required(job.required_text or job.description)
        flags["years"] = yrs
        if yrs and (yrs[0] > self.max_req or yrs[1] < self.min_ok):
            return False, flags
        return True, flags

import time

from .ashby import Ashby
from .greenhouse import Greenhouse
from .json_api import JsonApi
from .jsonld import JsonLd
from .lever import Lever
from .workday import Workday

ADAPTERS = {
    "greenhouse": Greenhouse(),
    "lever": Lever(),
    "ashby": Ashby(),
    "workday": Workday(),
    "json_api": JsonApi(),
    "jsonld": JsonLd(),
}

RESOLVE_OK_TTL = 7 * 86400
RESOLVE_FAIL_TTL = 86400


def get_adapter(strategy):
    try:
        return ADAPTERS[strategy]
    except KeyError:
        raise ValueError(f"unknown strategy '{strategy}'") from None


def resolve(entry, state):
    """Return the effective config for a company, auto-detecting the source if needed.
    Mutates `state` (cached detection result); the caller persists it."""
    if entry.get("strategy", "auto") != "auto":
        return dict(entry)
    now = time.time()
    cached = state.get("resolved")
    if cached and now - state.get("resolved_at", 0) < RESOLVE_OK_TTL:
        return {**entry, **cached}
    if not cached and now - state.get("resolve_failed_at", 0) < RESOLVE_FAIL_TTL:
        return None
    from .. import detect
    found = detect.discover(entry)
    if found:
        state["resolved"], state["resolved_at"] = found, now
        state.pop("resolve_failed_at", None)
        return {**entry, **found}
    state["resolve_failed_at"] = now
    return None

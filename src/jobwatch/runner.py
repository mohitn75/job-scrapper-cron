import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from . import adapters, notify, skills
from .filters import Filters

log = logging.getLogger("jobwatch")

DEFAULT_SETTINGS = {
    "max_enrich_per_company": 25,
    "max_messages_per_run": 40,
    "alert_after_failures": 3,
    "min_required_match": 0.0,
    "workers": 12,
}


def is_quiet(settings, now=None):
    q = settings.get("quiet_hours") or {}
    if not q.get("enabled"):
        return False
    now = now or datetime.now(timezone.utc)
    h = (now + timedelta(minutes=q.get("utc_offset_minutes", 330))).hour
    s, e = q.get("start", 23), q.get("end", 7)
    return (h >= s or h < e) if s > e else (s <= h < e)


def _failure(state, name, reason, settings):
    state["fail"] = state.get("fail", 0) + 1
    n, after = state["fail"], settings["alert_after_failures"]
    state["last_error"] = reason[:200]
    if n == after or (n > after and (n - after) % 24 == 0):
        return f"{name}: {reason[:120]} ({n} runs in a row)"
    return None


def process_company(entry, store, flt, profile, settings, deadline):
    name = entry["name"]
    res = {"name": name, "notify": [], "alert": None, "stats": {}}
    state = store.get_state(name)
    try:
        cfg = adapters.resolve(entry, state)
        if cfg is None:
            res["alert"] = _failure(state, name, "could not detect careers source; set strategy in companies.json", settings)
            return res
        adapter = adapters.get_adapter(cfg["strategy"])
        jobs = adapter.list_jobs(cfg)
        if not jobs:
            res["alert"] = _failure(state, name, "returned 0 jobs", settings)
            return res
        state["fail"] = 0

        unique = {j.key: j for j in jobs}
        candidates = [j for j in unique.values() if flt.check_listing(j)]
        seen = store.seen([j.key for j in candidates])
        fresh = [j for j in candidates if j.key not in seen]
        res["stats"] = {"listed": len(jobs), "candidates": len(candidates), "new": len(fresh)}

        if not state.get("seeded") and not entry.get("notify_existing"):
            store.mark_seen([j.key for j in fresh])
            state["seeded"] = True
            res["stats"]["seeded"] = len(fresh)
            return res

        silent = []
        for job in fresh[:settings["max_enrich_per_company"]]:
            if deadline and time.time() > deadline:
                break
            try:
                adapter.enrich(cfg, job)
            except Exception as e:
                log.warning("%s: enrich failed for %s: %s", name, job.id, e)
                continue
            ok, flags = flt.check_full(job)
            analysis = skills.analyze(job, profile) if ok else None
            if ok and notify.match_ratio(analysis) >= settings["min_required_match"]:
                res["notify"].append((job, analysis, flags))
            else:
                silent.append(job.key)
        if silent:
            store.mark_seen(silent)
        state["seeded"] = True
        return res
    except Exception as e:
        log.warning("%s failed: %s", name, e)
        res["alert"] = _failure(state, name, f"{type(e).__name__}: {e}", settings)
        return res
    finally:
        store.put_state(name, state)


def run(store, notifier, companies, filters_cfg, profile_cfg, deadline=None):
    settings = {**DEFAULT_SETTINGS, **filters_cfg.get("settings", {})}
    flt, profile = Filters(filters_cfg), skills.Profile(profile_cfg)
    entries = [c for c in companies.get("companies", []) if c.get("enabled", True)]

    with ThreadPoolExecutor(max_workers=settings["workers"]) as ex:
        results = list(ex.map(lambda e: process_company(e, store, flt, profile, settings, deadline), entries))

    quiet = is_quiet(settings)
    summary = {"companies": len(entries), "sent": 0, "alerts": 0, "errors": []}

    alerts = [r["alert"] for r in results if r["alert"]]
    if alerts:
        shown = alerts[:15]
        extra = f"\n...and {len(alerts) - 15} more" if len(alerts) > 15 else ""
        try:
            notifier.send("\u26a0\ufe0f JobWatch: scraper problems\n" + "\n".join(notify.esc(a) for a in shown) + extra, silent=True)
            summary["alerts"] = len(alerts)
        except Exception as e:
            summary["errors"].append(str(e))

    pending = [t for r in results for t in r["notify"]]
    pending.sort(key=lambda t: notify.match_ratio(t[1]), reverse=True)
    for job, analysis, flags in pending[:settings["max_messages_per_run"]]:
        if deadline and time.time() > deadline:
            break
        try:
            notifier.send(notify.format_job(job, analysis, flags), silent=quiet)
            store.mark_seen([job.key])
            summary["sent"] += 1
            time.sleep(1.1)
        except Exception as e:
            summary["errors"].append(str(e))
            break
    summary["pending_after_cap"] = max(0, len(pending) - summary["sent"])
    return summary

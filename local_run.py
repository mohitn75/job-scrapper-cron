#!/usr/bin/env python3
"""Local helper. Usage:
  python3 local_run.py probe-all            # which companies resolve, and how many jobs each returns
  python3 local_run.py probe "Name" [URL]   # test a single company
  python3 local_run.py run --dry-run        # full pipeline, prints messages instead of sending
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from jobwatch import adapters, config, skills  # noqa: E402
from jobwatch.filters import Filters  # noqa: E402
from jobwatch.notify import PrintNotifier, Telegram  # noqa: E402
from jobwatch.runner import run  # noqa: E402
from jobwatch.store import MemoryStore  # noqa: E402


def probe_entry(entry, flt):
    state = {}
    cfg = adapters.resolve(entry, state)
    if not cfg:
        return "UNRESOLVED", 0, 0, None
    try:
        jobs = adapters.get_adapter(cfg["strategy"]).list_jobs(cfg)
    except Exception as e:
        return f"{cfg['strategy']} ERROR {type(e).__name__}: {e}"[:90], 0, 0, cfg
    cands = sum(1 for j in jobs if flt.check_listing(j))
    return cfg["strategy"], len(jobs), cands, cfg


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("probe-all")
    p = sub.add_parser("probe")
    p.add_argument("name")
    p.add_argument("url", nargs="?")
    r = sub.add_parser("run")
    r.add_argument("--dry-run", action="store_true")
    r.add_argument("--state-file", default=".jobwatch_state.json")
    a = ap.parse_args()

    filters_cfg = config.load_json("filters.json")
    profile = skills.Profile(config.load_json("skills_profile.json"))
    if profile.unknown:
        print("Unknown skill names in skills_profile.json (ignored):", profile.unknown)
    flt = Filters(filters_cfg)

    if a.cmd == "probe":
        entry = {"name": a.name, **({"careers_url": a.url} if a.url else {})}
        strat, total, cands, cfg = probe_entry(entry, flt)
        print(strat, f"jobs={total} matching_title_and_location={cands}")
        print(json.dumps(cfg, indent=2) if cfg else "Add an explicit strategy in companies.json")
    elif a.cmd == "probe-all":
        entries = [c for c in config.load_json("companies.json")["companies"] if c.get("enabled", True)]
        print(f"{'company':28} {'source':34} {'jobs':>5} {'relevant':>8}")
        for e in entries:
            strat, total, cands, cfg = probe_entry(e, flt)
            detail = ""
            if cfg and e.get("strategy", "auto") == "auto":
                detail = " <- " + json.dumps({k: v for k, v in cfg.items() if k in ("board", "site", "host", "region")})
            print(f"{e['name'][:27]:28} {strat[:33]:34} {total:>5} {cands:>8}{detail}")
            time.sleep(0.2)
    else:
        notifier = PrintNotifier() if a.dry_run else Telegram(config.get_secret("telegram_bot_token"), config.get_secret("telegram_chat_id"))
        store = MemoryStore(a.state_file)
        summary = run(store, notifier, config.load_json("companies.json"), filters_cfg, config.load_json("skills_profile.json"))
        print("\nsummary:", summary)


if __name__ == "__main__":
    main()

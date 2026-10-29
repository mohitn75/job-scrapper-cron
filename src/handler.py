import logging
import os
import time

from jobwatch import config
from jobwatch.notify import Telegram
from jobwatch.runner import run
from jobwatch.store import DynamoStore

logging.getLogger().setLevel(logging.INFO)
log = logging.getLogger("jobwatch")


def lambda_handler(event, context):
    event = event or {}
    tg = Telegram(config.get_secret("telegram_bot_token"), config.get_secret("telegram_chat_id"))
    if event.get("action") == "test":
        tg.send("JobWatch connected \u2705")
        return {"ok": True}

    store = DynamoStore(os.environ["TABLE_NAME"])
    deadline = time.time() + context.get_remaining_time_in_millis() / 1000 - 30
    try:
        summary = run(store, tg,
                      config.load_json("companies.json"),
                      config.load_json("filters.json"),
                      config.load_json("skills_profile.json"),
                      deadline=deadline)
    except Exception as e:
        try:
            tg.send(f"JobWatch crashed: {type(e).__name__}: {str(e)[:200]}", silent=True)
        except Exception:
            pass
        raise
    log.info("summary: %s", summary)
    if summary["errors"]:
        raise RuntimeError("; ".join(summary["errors"])[:500])
    return summary

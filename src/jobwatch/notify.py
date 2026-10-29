import html
import json
import time
import urllib.error
import urllib.request


def esc(s):
    return html.escape(s or "", quote=False)


def _years(yrs):
    if not yrs:
        return None
    lo, hi = yrs
    return f"{lo}+ years" if lo == hi else f"{lo}-{hi} years"


def match_ratio(analysis):
    have = len(analysis["required_have"])
    total = have + len(analysis["required_missing"])
    return have / total if total else 1.0


def format_job(job, analysis, flags, max_items=14):
    lines = [f"<b>{esc(job.title) or 'New opening'}</b>",
             f"{esc(job.company)} \u00b7 {esc(job.location) or 'Location not listed'}"]
    if flags.get("relocation") is True:
        lines.append("Relocation or visa support: mentioned \u2705")
    y = _years(flags.get("years"))
    if y:
        lines.append(f"Experience asked: {y}")

    rh, rm = analysis["required_have"], analysis["required_missing"]
    ph, pm = analysis["preferred_have"], analysis["preferred_missing"]
    if rh or rm:
        lines += ["", f"<b>Required skills: you match {len(rh)} of {len(rh) + len(rm)}</b>"]
        lines += [f"\u2705 {esc(s)}" for s in rh[:max_items]]
        lines += [f"\u274c {esc(s)}" for s in rm[:max_items]]
    if ph or pm:
        lines += ["", "<b>Nice to have</b>"]
        lines += [f"\u2705 {esc(s)}" for s in ph[:max_items]]
        lines += [f"\u274c {esc(s)}" for s in pm[:max_items]]
    if not (rh or rm or ph or pm):
        lines += ["", "No recognizable skills found in the description."]
    if job.url:
        lines += ["", f'<a href="{html.escape(job.url, quote=True)}">Open posting</a>']
    return "\n".join(lines)[:4000]


class Telegram:
    def __init__(self, token, chat_id):
        self.token = token
        self.chat_id = chat_id

    def send(self, text, silent=False):
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        body = json.dumps({
            "chat_id": self.chat_id, "text": text, "parse_mode": "HTML",
            "disable_web_page_preview": True, "disable_notification": silent,
        }).encode("utf-8")
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=20) as r:
                    return json.load(r)
            except urllib.error.HTTPError as e:
                payload = e.read().decode("utf-8", errors="replace")
                if e.code == 429 and attempt < 2:
                    try:
                        wait = json.loads(payload).get("parameters", {}).get("retry_after", 5)
                    except ValueError:
                        wait = 5
                    time.sleep(min(wait, 30))
                    continue
                raise RuntimeError(f"Telegram error {e.code}: {payload[:200]}") from None
            except (urllib.error.URLError, TimeoutError):
                if attempt < 2:
                    time.sleep(2)
                    continue
                raise RuntimeError("Telegram unreachable") from None


class PrintNotifier:
    """Dry-run notifier: prints instead of sending."""
    def __init__(self):
        self.sent = []

    def send(self, text, silent=False):
        self.sent.append(text)
        print("-" * 60)
        print(html.unescape(text).replace("<b>", "").replace("</b>", ""))

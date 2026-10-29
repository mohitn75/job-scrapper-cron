# JobWatch: personal job alerts on AWS free tier

Every hour a Lambda scans the careers sources of ~100 product companies, filters for backend/platform roles
(about 6 years of experience, Indian cities, or abroad only when relocation/visa support is mentioned),
checks each job's skills against your resume profile, and sends new jobs to Telegram with a checklist:

    Senior Software Engineer, Platform
    Databricks · Bengaluru, India
    Required skills: you match 4 of 6
    ✅ Java   ✅ Kafka   ✅ Kubernetes   ✅ Terraform   ❌ Spark   ❌ Scala
    Nice to have:  ✅ GCP   ❌ Rust

Pure standard-library Python (boto3 is built into Lambda), so there is nothing to package or install.

```
config/                 companies.json, filters.json, skills_profile.json  (you edit these)
src/handler.py          Lambda entry point
src/jobwatch/           scraper adapters, filters, skill matcher, Telegram, DynamoDB store
terraform/              S3, DynamoDB, Lambda, IAM, hourly schedule
local_run.py            local probe / dry-run tool
tests/                  offline unit tests
```

## 0. Prerequisites

- AWS account, AWS CLI configured (`aws configure`), Terraform >= 1.5, Python 3.12 locally.
- A Telegram account.

## 1. Billing safety (5 minutes, do this first)

AWS changed its free tier for newly created accounts, so check in the Billing console which plan yours is on.
Expected usage here is tiny (about 720 Lambda runs a month, a few thousand DynamoDB operations), but add a
guard anyway: Billing > Budgets > create a monthly cost budget of $1 with an email alert.

## 2. Create the Telegram bot

1. In Telegram, message **@BotFather**, send `/newbot`, follow the prompts, and copy the **bot token**.
2. Open a chat with your new bot and send it any message (for example "hi").
3. In a browser open `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` and find `"chat":{"id":123456789,...}`.
   That number is your **chat id**.

Never paste the token into chat, a repo, or a Terraform file.

## 3. Verify locally before deploying (strongly recommended)

I could not test against live career sites while writing this, so run these on your machine first.

```bash
python3 -m unittest discover -s tests -v          # offline tests, should all pass
python3 local_run.py probe-all                     # which companies resolve, how many jobs, how many look relevant
python3 local_run.py probe "Stripe"                # test one company by name
python3 local_run.py probe "Acme" https://acme.com/careers
python3 local_run.py run --dry-run                 # full pipeline, prints messages instead of sending
python3 local_run.py run --dry-run                 # run again: nothing new should appear
```

What `probe-all` tells you:

- A source name (greenhouse, lever, ashby, workday, json_api): resolved and returning jobs.
- `UNRESOLVED`: the name alone could not be matched to a job board. Add a `careers_url` (works for Workday
  URLs and pages that embed a Greenhouse/Lever/Ashby board) or configure `json_api` / `jsonld` (see Amazon).
- `<- {"board": "..."}` next to an auto-detected company shows the slug it picked. Name-based detection can
  occasionally pick a different company with a similar slug, so skim these.
- Companies marked `"enabled": false` have custom career sites. Enable them once you add a config.
- The Workday URLs and the Amazon config are from memory: if one errors, check the host and site name in the
  browser address bar of that company's careers page.

The first real run only records existing jobs silently (so you are not flooded). To see a real alert sooner,
add `"notify_existing": true` to one company in `companies.json` for the first run, then remove it.

## 4. Deploy

```bash
# one-time: store the Telegram secrets (SecureString, free tier)
read -rs TOKEN;   aws ssm put-parameter --region ap-south-1 --name /jobwatch/telegram_bot_token --type SecureString --value "$TOKEN"
read -r  CHAT_ID; aws ssm put-parameter --region ap-south-1 --name /jobwatch/telegram_chat_id   --type SecureString --value "$CHAT_ID"

cd terraform
terraform init
terraform apply          # review the plan, type yes

# smoke test: should send "JobWatch connected" to your Telegram
aws lambda invoke --region ap-south-1 --function-name jobwatch \
  --payload '{"action":"test"}' --cli-binary-format raw-in-base64-out out.json

# first scan (silently records current jobs), then watch the logs
aws lambda invoke --region ap-south-1 --function-name jobwatch --payload '{}' \
  --cli-binary-format raw-in-base64-out out.json
aws logs tail /aws/lambda/jobwatch --region ap-south-1 --follow
```

From then on EventBridge Scheduler runs it every hour. Change region, project name or schedule in
`terraform/variables.tf` (for example `rate(30 minutes)`).

## 5. Day-to-day

- **Add a company:** append `{"name": "Company"}` to `config/companies.json`, then `terraform apply`
  (or `aws s3 cp config/companies.json s3://<config_bucket>/config/companies.json`; the bucket name is a
  Terraform output). No redeploy needed for config-only changes. New companies are seeded silently first.
- **Remove or pause one:** delete it or set `"enabled": false`.
- **Tune filters:** edit `config/filters.json` (title keywords, cities, experience range, abroad rules,
  quiet hours, `min_required_match` to hide weak matches).
- **Update your skills:** edit `config/skills_profile.json`. It was built from your CV including the experience
  bullets (Kafka, GraphQL, Debezium, Paimon, vector/full-text search), so review it and add anything you
  genuinely have, for example Docker or Microservices. Skill names come from `TAXONOMY` in `src/jobwatch/skills.py`;
  add aliases or new skills there.
- **Scraper failures:** if a company errors or returns zero jobs 3 runs in a row you get one Telegram warning.

## 6. How it decides (and where it can be wrong)

- **Sources:** Greenhouse, Lever, Ashby and Workday public job APIs, plus a generic `json_api` config and a
  `jsonld` (sitemap + schema.org JobPosting) fallback. Plain HTML selectors and headless-browser scraping
  are not in the MVP.
- **Relocation:** for non-India jobs it looks for phrases like "relocation assistance" or "visa sponsorship
  available" and rejects explicit negatives ("unable to sponsor"). It is keyword-based and will sometimes
  miss or misjudge.
- **Skills:** keyword matching against a built-in skill list. Required vs nice-to-have comes from section
  headings and phrases such as "is a plus". Skills not on the list are not shown. An LLM matcher is the planned upgrade.
- **Politeness:** public JSON APIs are called directly; HTML pages respect robots.txt; requests are rate-limited
  and the User-Agent identifies the tool.
- **Dedupe:** jobs are remembered in DynamoDB for a year. A job is marked seen only after Telegram accepts it.
- **Caps:** up to 25 new jobs per company and 40 messages per run; the rest carry over to the next hour.

## 7. Next features

LLM-based skill matching, daily digest mode, headless-browser strategy for JavaScript-only sites, per-company
polling intervals, closed-job notices, resume-tailoring suggestions.

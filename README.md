# jobsift

> AI-powered job-matching agent: aggregates listings from several **public job-board APIs**, scores them against **your own profile/CV** with an LLM, and emails you a daily, relevance-ranked digest.

![CI](https://github.com/florianjoubert/jobsift/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.13-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## How it works

1. **Connectors** - each source (France Travail, Welcome to the Jungle, Adzuna, Arbeitnow) implements a common interface and returns a normalized `Job`.
2. **Filters** - geographic scope (e.g. France + EU remote), then language (FR/EN).
3. **AI scoring** - every listing is scored 0–100 against *your* profile with OpenAI (structured output), with full-remote prioritized.
4. **Digest** - a clean, ranked HTML email (or an HTML file if email isn't configured).

> **On data sources:** France Travail, Adzuna and Arbeitnow are official, documented APIs.
> Welcome to the Jungle is accessed via its public Algolia search endpoint - public,
> unauthenticated data, the same the website itself queries (no login, no authenticated
> scraping). It is not an official API and can be turned off with `sources.wttj: false`.

## Architecture

```
app/
  connectors/   # job sources (one class per source) + registry
  services/     # pipeline, geo/language filters, scoring, notifier
  db/           # SQLite persistence
  api/          # FastAPI (GET /jobs, POST /runs, GET /health)
  schemas/      # shared Pydantic models
```

Connectors are **pluggable**: adding a source = one file implementing the `JobConnector` interface.

---

## Quick start

### 1. Prerequisites
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Python 3.13 (uv can install it for you)
- An OpenAI API key (required - used for scoring)

### 2. Install
```bash
git clone https://github.com/florianjoubert/jobsift.git
cd jobsift
uv sync
```

### 3. Configure secrets - `.env`
```bash
cp .env.example .env
```
Then edit `.env`. **Only `OPENAI_API_KEY` is required**; everything else is optional (a connector without its key is skipped, and without email the digest is written to an HTML file).

| Variable | Where to get it | Required |
|---|---|---|
| `OPENAI_API_KEY` | [platform.openai.com](https://platform.openai.com) | **Yes** |
| `OPENAI_MODEL` | e.g. a small/cheap model | defaults provided |
| `FRANCE_TRAVAIL_CLIENT_ID` / `_SECRET` | [francetravail.io](https://francetravail.io) (free) | No |
| `ADZUNA_APP_ID` / `_KEY` | [developer.adzuna.com](https://developer.adzuna.com) (free) | No |
| `EMAIL_ADDRESS` / `EMAIL_PASSWORD` / `EMAIL_TO` | Gmail + [App Password](https://myaccount.google.com/apppasswords) | No |

### 4. Set up your profile - `profile.md` ⭐
This is the heart of the matching: **every job is scored against this file.** The richer and more specific it is, the better the scores.
```bash
cp profile.example.md profile.md
```
Edit `profile.md` with **your CV and your targeting**. A good profile contains:
- **Your background / CV** - experience, skills, stack, seniority.
- **TARGET** - the roles/companies you actually want (be specific).
- **EXCLUSIONS** - what to reject (e.g. on-site roles, consulting/staffing, non-tech verticals). The scorer enforces these and caps off-target listings low.
- **CONSTRAINTS** - e.g. full remote only, languages, rate/salary.

The clearer your TARGET and EXCLUSIONS, the sharper the ranking. `profile.md` is **gitignored** - your CV never leaves your machine except in the scoring request to OpenAI.

### 5. Configure the search - `config.yaml`
```bash
cp config.example.yaml config.yaml
```
| Section | Field | Purpose |
|---|---|---|
| `search` | `keywords` | search terms sent to the sources |
| `search` | `lookback_days` | recency window |
| `geo` | `allowed_countries` | countries kept (full names, e.g. `France`, `Germany`) |
| `geo` | `allow_remote_unknown` | keep remote jobs with unknown country |
| `sources` | `arbeitnow` / `wttj` / `france_travail` / `adzuna` | enable/disable each source |
| `scoring` | `min_relevance_score` | minimum score (0–100) to appear in the digest |
| `notification` | `smtp_server` / `smtp_port` | mail server (recipient comes from `.env`) |

### 6. Run it
```bash
uv run python -m app.cli          # one full run (fetch → filter → score → email)
```
On the first run the database is empty, so every listing is scored (can take a while). Later runs are fast - already-seen jobs are skipped, only new ones are scored.

### 7. (Optional) Run the API
```bash
uv run uvicorn app.main:app       # http://localhost:8000
```
- `GET /health` - liveness
- `POST /runs` - trigger a run in the background → returns a `run_id`
- `GET /runs/{id}` - run status/summary
- `GET /jobs?min_score=&source=` - list scored jobs

> The API has **no authentication** and is meant for **localhost only** (uvicorn binds
> `127.0.0.1` by default). Don't expose it publicly without adding an auth layer and rate
> limiting on `POST /runs` (which triggers OpenAI usage).

### 8. (Optional) Schedule a daily run

Any scheduler works: just run `uv run python -m app.cli` once a day from the project
directory. Schedulers need **absolute paths** (find uv with `which uv`).

**Linux (cron)** - `crontab -e`, then add:
```
0 8 * * * cd /path/to/jobsift && /path/to/uv run python -m app.cli >> data/cron.log 2>&1
```

**macOS (launchd)** - copy the provided template, edit the paths, then load it:
```bash
cp deploy/com.jobsift.daily.plist.example ~/Library/LaunchAgents/com.jobsift.daily.plist
# replace the /PATH/TO placeholders in the file, then:
launchctl load ~/Library/LaunchAgents/com.jobsift.daily.plist
```
> macOS privacy (TCC) note: launchd cannot access `~/Documents`, `~/Desktop` or
> `~/Downloads`. Keep the project **and** the log paths outside those folders (or grant
> uv Full Disk Access), otherwise the scheduled run fails to start.

**Windows (Task Scheduler)** - create a Basic Task with a daily trigger; action "Start a
program": program `uv`, arguments `run python -m app.cli`, "Start in" = the project dir.

---

## Adding a source

Create `app/connectors/<name>.py` with a class exposing `name` and `fetch(criteria) -> list[Job]`, returning normalized `Job` objects, then register it in `app/connectors/registry.py`.

For a source you'd rather not commit, drop a `*.py` exposing a `Connector` class into a local `connectors_private/` folder: it's auto-discovered at startup and gitignored.

## Development

```bash
uv run pytest          # tests
uv run ruff check .    # lint
```

## License

[MIT](LICENSE)

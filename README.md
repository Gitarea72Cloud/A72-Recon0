# A72-Recon0

Adaptive placement test for the Evolve Master in Cybersecurity (A72 Labs). Sorts
incoming students into a **Basic** or **Advanced** starting track before
Module 1, through hands-on tasks in a simulated Linux shell rather than
multiple choice.

Full design rationale, the branching diagram, and an interactive terminal
demo live in the project proposal — this repo is the implementation of that
document, not a separate source of truth. Ask the A72-Recon0 project owner
for the current link if you don't have it.

## Architecture

Fully serverless, no VPC:

- **S3** — static frontend hosting (`frontend/`)
- **Cognito** — auth; students are bulk-imported, not self-signup
- **API Gateway (HTTP API)** — Cognito JWT authorizer
- **Lambda** (Python 3.12) — `start-session`, `terminal-exec`, `submit-answer`,
  `get-result`, `admin`
- **DynamoDB** — single table, on-demand, keyed by cohort/checkpoint from day
  one so the same engine can run again for Cohort 2 (Jan 2027), Cohort 3
  (Apr 2027), or an end-of-module checkpoint later

See `template.yaml` for the full resource definitions.

## Repo layout

```
template.yaml              SAM template — all AWS resources
samconfig.toml              sam deploy defaults (dev / prod)
src/functions/*/app.py      one Lambda per action
layer/python/common/        shared code (db, scoring, auth) as a Lambda layer
frontend/                   static site (placeholder — real SPA is Phase 1 UI work)
scripts/seed_questions.py   loads 2 sample Stage 0 items for smoke-testing
bootstrap/                  one-time AWS-side setup (see DEPLOY.md)
.github/workflows/          CI (validate on every PR) + CD (deploy on push to main)
```

## v1 scope

Linux-only interpreter and domains (Linux & CLI, networking, scripting, core
security, tooling-recognition). Windows/AD stays short-answer/conceptual
until a second, GUI-flavored engine (`windows-exec`) is built — see the
proposal's decisions log for why.

## Local development

```bash
pip install aws-sam-cli
sam build
sam local start-api   # runs the API against a local Docker Lambda + your real AWS DynamoDB table
```

You'll still need a deployed `DataTable` to point at (DynamoDB doesn't have
a meaningful local emulator worth the setup cost here) — deploy the dev
stack first (see `DEPLOY.md`), then export `TABLE_NAME` from its output
before running `sam local`.

## Deploying

See **[DEPLOY.md](./DEPLOY.md)** — one manual one-time step in your AWS
account, then every push to `main` deploys itself via GitHub Actions.

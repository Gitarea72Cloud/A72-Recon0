# Deploying A72-Recon0

Target account: **738388288350**, region **eu-south-2** (AWS "Spain").

The pipeline uses GitHub OIDC to assume an AWS role — no long-lived AWS
access keys are ever stored in GitHub. That role has to exist before the
first deploy can work; creating it just needs credentials for account
`738388288350` configured in the AWS CLI (a profile in your own terminal,
AWS CloudShell, or an agent session with such a profile all work).

## 1. One-time: create the OIDC provider + deploy role

With credentials for account `738388288350` configured (`--profile <name>`
if it's not your default):

```bash
# Check whether this account already has a GitHub OIDC provider
# (common if you've connected GitHub Actions to this account before):
aws iam list-open-id-connect-providers

# If token.actions.githubusercontent.com is already listed, deploy with
# CreateOidcProvider=false. Otherwise leave it at the default (true).
aws cloudformation deploy \
  --template-file bootstrap/github-oidc-role.yaml \
  --stack-name a72-recon0-github-oidc \
  --region eu-south-2 \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides CreateOidcProvider=true
```

This creates a role, `A72Recon0-GitHubActionsDeployRole`, trusted only for
`push` events on `Gitarea72Cloud/A72-Recon0`'s `main` branch — not other
branches, not pull requests, not forks. `.github/workflows/deploy.yml`
already points at it by ARN
(`arn:aws:iam::738388288350:role/A72Recon0-GitHubActionsDeployRole`), so
there's nothing further to configure in GitHub itself.

**Gotcha hit on first deploy:** if this GitHub org or repo has ever been
renamed or transferred, GitHub sends an ID-qualified `sub` claim
(`repo:ORG@ORGID/REPO@REPOID:ref:...`) instead of the plain
`repo:ORG/REPO:ref:...` form, and a trust policy written for the plain form
gets `Not authorized to perform sts:AssumeRoleWithWebIdentity` even though
everything else is correct. The template's `GitHubOrgId`/`GitHubRepoId`
parameters (defaulted to this repo's actual IDs) already account for this.
If you ever need to rediscover the IDs, decode a token from an Actions run:
add a step with
`curl -sS -H "Authorization: bearer $ACTIONS_ID_TOKEN_REQUEST_TOKEN" "$ACTIONS_ID_TOKEN_REQUEST_URL&audience=sts.amazonaws.com" | jq -r .value | cut -d. -f2 | base64 -d | jq`.

The attached policy (`bootstrap/github-oidc-role.yaml`) is a **first pass**,
scoped by the `a72-recon0-*` naming convention everywhere the service
supports resource-level restriction, but a few actions (Cognito, API
Gateway) had to stay broader since those ARNs aren't knowable before first
creation. Worth tightening once the stack has deployed once and the real
ARNs exist.

## 2. One-time: point a CloudFront distribution at the frontend bucket

The frontend bucket (`a72-recon0-web-${Stage}-738388288350`) is private —
S3 Block Public Access is on at the account level, so a public bucket
policy is rejected outright. It's served through CloudFront with Origin
Access Control (OAC) instead, which also means HTTPS/CDN for free.

**Known gotcha:** this account currently can't create *new* CloudFront
distributions via CloudFormation or the API — every attempt fails with
`Access denied for operation 'AWS::CloudFront::Distribution: Your account
must be verified before you can add new CloudFront resources'`. Confirmed
account-wide (identical error under an admin IAM user and a scoped role,
and in a test stack homed in us-east-1 instead of eu-south-2 — not a
permissions or region issue). It also blocks *creating a new* distribution
by hand in the console. **Editing an existing distribution is not gated**,
so if the account already has an idle/unused CloudFront distribution,
repurposing it works around this entirely; a new Origin Access Control
resource can still be created fine even while distribution creation is
blocked. Fixing this for real means an AWS Support case asking to verify
the account for new CloudFront resources — until then, reuse-and-edit is
the workflow.

Whichever distribution you use, point it at the frontend bucket:

| Setting | Value |
|---|---|
| Origin domain | `<bucket>.s3.eu-south-2.amazonaws.com` (the S3 **REST** endpoint, not the website-hosting endpoint — OAC/SigV4 needs the REST endpoint) |
| Origin path | (blank) |
| Origin access | Origin access control (OAC), signing behavior "Sign requests" |
| Viewer protocol policy | Redirect HTTP to HTTPS |
| Allowed methods | GET, HEAD |
| Cache policy | CachingOptimized (AWS managed) |
| Default root object | `index.html` |
| Custom error responses | 403 → `/index.html` (200), 404 → `/index.html` (200) — SPA fallback for client-side routes |

Then set the distribution's ID as a repo variable so the pipeline knows
about it:

```bash
gh variable set CLOUDFRONT_DISTRIBUTION_ID --body "<distribution-id>"
```

`template.yaml`'s `WebsiteBucketPolicy` only gets created once
`CloudFrontDistributionId` is passed to `sam deploy` (which
`deploy.yml` does automatically from that repo variable) — it grants
`s3:GetObject` scoped to that exact distribution's ARN via
`AWS:SourceArn`, nothing broader.

## 3. One-time: enable Bedrock for AI-assisted question drafting

The admin question bank's "Generate with AI" button (`POST
/admin/questions/generate`) calls Claude Haiku 4.5 via Bedrock. Two
one-time account-side steps, both console-only — no CLI/API path exists
for either:

1. **Accept Anthropic's model-access agreement.** Bedrock requires a
   "use case" form (an opaque, undocumented blob via the CLI's
   `put-use-case-for-model-access --form-data`) submitted before
   `create-foundation-model-agreement` will succeed — deliberately not
   scriptable here since it asks for a genuine business justification.
   Go to the [Bedrock console](https://console.aws.amazon.com/bedrock/)
   → **Model access** → find **Anthropic** → **Request model access** →
   fill in the short form → submit. Normally instant for Claude models.
2. **Deploy the cost-guardrail budget** (`bootstrap/bedrock-cost-budget.yaml`)
   to **us-east-1 specifically** — `AWS::Budgets::Budget` is one of the
   CloudFormation resource types only recognized in that region (a
   long-standing Billing/Cost Management quirk), even though the budget
   itself tracks spend account-wide:
   ```bash
   aws cloudformation deploy \
     --template-file bootstrap/bedrock-cost-budget.yaml \
     --stack-name a72-recon0-bedrock-cost-budget \
     --region us-east-1 \
     --parameter-overrides Stage=dev MonthlyBudgetUsd=20 AlertEmail=you@example.com
   ```
   This only emails at ~50%/100% of the cap (AWS Budgets/Cost Explorer
   data lags real spend by up to ~24h, so it can't be a hard stop). The
   actual instant hard stop lives in `AdminFunction` itself
   (`BEDROCK_MAX_SPEND_USD` env var, default 20): it tracks real spend
   from each call's actual token usage in DynamoDB
   (`PK=BEDROCK_USAGE`/`SK=QUESTION_GEN`) and refuses further Bedrock
   calls once the running total hits the cap — no billing-data lag
   involved, since it's computed directly from what Bedrock's own
   response says it billed.

## 4. One-time: verify the sender identity for module-unlock emails

When an instructor unlocks a module assessment, every student gets an
in-app notification plus a best-effort email. The in-app half needs no
setup (it's just DynamoDB), but the email half needs a one-time,
console/email-click step, same shape as the Bedrock step above:

1. **Deploy the sender identity** (`bootstrap/ses-notification-identity.yaml`)
   to **eu-west-1 specifically** — Amazon SES isn't available in
   eu-south-2 at all (same kind of region quirk as the Budgets template
   needing us-east-1):
   ```bash
   aws cloudformation deploy \
     --template-file bootstrap/ses-notification-identity.yaml \
     --stack-name a72-recon0-ses-notifications \
     --region eu-west-1 \
     --parameter-overrides SenderEmail=morillasfj@gmail.com
   ```
2. **Click the confirmation link** AWS emails to that address — nothing
   sends until it's clicked.
3. **Known limitation:** new SES accounts start in the "sandbox," which
   only delivers to *other* verified addresses until AWS grants
   production access (Account dashboard → "Request production access,"
   self-service — not the same as the account-verification gates hit
   elsewhere in this project). Until then, emails to real students will
   silently no-op (caught, logged nowhere, never raises) — **the in-app
   notification still lands regardless**, so the feature works end to
   end either way; requesting production access is a separate,
   non-blocking follow-up whenever it's convenient.

## 5. Push to main

Every push to `main` now runs `.github/workflows/deploy.yml`: `sam build`,
`sam deploy` to `eu-south-2`, syncs `frontend/` to the resulting S3
bucket, then invalidates the CloudFront cache (skipped automatically if
`CLOUDFRONT_DISTRIBUTION_ID` isn't set yet). Watch it under the repo's
**Actions** tab.

## 6. Smoke-test it

```bash
aws cloudformation describe-stacks --stack-name a72-recon0-dev \
  --region eu-south-2 --query "Stacks[0].Outputs" --output table

python3 scripts/seed_questions.py --table a72-recon0-dev --region eu-south-2
python3 scripts/seed_module_questions.py --table a72-recon0-dev --region eu-south-2
```

Then create yourself a Cognito user (`aws cognito-idp admin-create-user
--user-pool-id <UserPoolId> --username you@example.com`) and hit
`POST {ApiUrl}/session/start` with that user's ID token to confirm the
whole path works end to end.

## Later: production

`samconfig.toml` already has a `prod` config (`sam deploy --config-env prod`)
targeting a separate `a72-recon0-prod` stack in the same account/region —
not wired into the GitHub Actions workflow yet on purpose, since the roadmap
calls for real Cohort 1 (Oct 2026) validation on `dev` first.

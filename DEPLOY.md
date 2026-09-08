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

## 3. Push to main

Every push to `main` now runs `.github/workflows/deploy.yml`: `sam build`,
`sam deploy` to `eu-south-2`, syncs `frontend/` to the resulting S3
bucket, then invalidates the CloudFront cache (skipped automatically if
`CLOUDFRONT_DISTRIBUTION_ID` isn't set yet). Watch it under the repo's
**Actions** tab.

## 4. Smoke-test it

```bash
aws cloudformation describe-stacks --stack-name a72-recon0-dev \
  --region eu-south-2 --query "Stacks[0].Outputs" --output table

python3 scripts/seed_questions.py --table a72-recon0-dev --region eu-south-2
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

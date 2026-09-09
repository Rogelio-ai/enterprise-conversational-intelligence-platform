# Production Deployment and Rollback Runbook

## Artifact and credential policy

The release chain is: private source repository → controlled build → immutable `git-<full SHA>` images → private registry → authenticated pull → runtime hosts. `latest` is not a release identity. The build identity has push permission. The VPS and Connector host use distinct pull-only credentials and have no source-repository credentials.

The VPS needs only the certified deployment bundle (`compose.production.yaml` and `deploy/observability/*`), the protected env/secret/TLS files, and Docker Compose. It does not clone, pull, mount, or build application source.

## Build and publish

1. Require a clean certified commit and record `git rev-parse HEAD`.
2. Authenticate to the private registry using the build/publish credential.
3. Set `REGISTRY` and `REGISTRY_NAMESPACE` and run `scripts/release-images.sh build`.
4. Run focused tests and `scripts/verify-release-artifacts.sh`.
5. Run `scripts/release-images.sh publish`. Record each immutable tag and registry digest.
6. Copy `deploy/production.env.example` outside Git, replace operator values, and pin the recorded image identities. Prefer `name@sha256:digest`; `name:git-<full SHA>` is acceptable with the digest recorded in the release record.

## Deploy

1. Log in to the registry on the VPS using only its pull credential.
2. Validate: `docker compose --env-file "$PRODUCTION_ENV_FILE" -f compose.production.yaml config --quiet`.
3. Create and verify an encrypted/off-host backup.
4. Run `PRODUCTION_ENV_FILE=... CONFIRMED_BACKUP_ARTIFACT=... scripts/controlled-migration.sh`. A failure stops promotion.
5. Run `PRODUCTION_ENV_FILE=... scripts/deploy-release.sh`.
6. Verify HTTPS `/health` and `/ready`, `/diner/`, `/staff/`, same-origin `/api/health`, metrics scrape targets, logs, and image digests.
7. Observe error/readiness signals before announcing availability.

The API image startup never runs Alembic. `migrate` is the only production migration authority. Do not bootstrap an admin during normal startup.

## Start, stop, and traffic stop

```bash
docker compose --env-file "$PRODUCTION_ENV_FILE" -f compose.production.yaml start
docker compose --env-file "$PRODUCTION_ENV_FILE" -f compose.production.yaml stop
docker compose --env-file "$PRODUCTION_ENV_FILE" -f compose.production.yaml stop ingress
```

Stopping ingress stops new browser traffic while keeping API/DB evidence available on private networks. For integrity uncertainty, also stop API mutation processing with `stop api` after capturing status and logs.

## Application rollback

1. Stop ingress and declare manual mode.
2. Identify the prior certified API/web/ingress image digests and confirm their schema compatibility with the current DB.
3. Change only image references in the protected production env file.
4. Pull and redeploy with `scripts/deploy-release.sh`; verify release identity, `/health`, `/ready`, and representative reads.
5. Restore traffic only after reconciliation.

Never run an automatic Alembic downgrade. If the prior application is incompatible, keep traffic stopped and use controlled restore/recovery with the incident owner.

## Connector update and rollback

Keep `config.toml`, `credentials.json`, and the SQLite ledger outside the image. With `deploy/connector/compose.connector.yaml`, pull the new immutable image and run `docker compose up -d`. Check heartbeat and delivery state before retiring the old identity. Roll back by selecting a compatible prior digest and redeploying; the mounted configuration, credential, and named ledger volume remain unchanged. Docker is preferred for TCP/9100 and compatible USB access. Debian/systemd remains supported for host-native USB, CUPS queues/drivers, or permissions.

## Incident and manual restaurant fallback

1. Stop new diner traffic at ingress and announce manual mode to staff.
2. If integrity is uncertain, stop unsafe mutations; do not retry uncertain payments or fiscal operations.
3. Keep electronic payments, CFDI, external POS, and connector delivery disabled. Stop the Connector service if delivery safety is uncertain.
4. Preserve DB backup, container/image identities, structured logs, correlations, and timestamps. Restrict evidence access.
5. Operate cash/screen/manual restaurant procedures approved by the restaurant owner.
6. Reconcile open sessions, drafts, orders, preparation work, checks, payments, cash movements, fiscal attempts, and print dispatches before resuming.
7. Record cause, impact, decisions, owner, and recovery validation.

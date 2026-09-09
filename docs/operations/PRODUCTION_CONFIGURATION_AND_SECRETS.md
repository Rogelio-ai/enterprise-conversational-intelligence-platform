# Production Configuration and Secret Boundary

## Contract

`deploy/production.env.example` is the authoritative non-secret contract. Production Compose hard-codes `APP_ENV=production`, disables docs and every excluded capability, and accepts an external MySQL host. Values marked `OPERATOR INPUT REQUIRED` must be resolved outside Git before deployment.

| Boundary | Values |
| --- | --- |
| Non-secret deployment | immutable image references, public origin, trusted hosts, bind ports, log level, pool sizes, TTLs, rate limits, monitoring retention, FINKOK demo endpoint/timeouts |
| Backend secrets | runtime DB password, migration DB password, JWT signing secret, independent diner-access secret; later provider credentials only when separately enabled |
| Infrastructure secrets | registry push credential, runtime pull-only credential, connector pull-only credential, TLS private key, backup encryption/storage credential |
| Connector-local | cloud URL, tenant/location identity, printer targets/IPs/queues, connector credential file, persistent SQLite ledger |

Secret files must be owner-readable only (`0600`), stored outside the checkout, mounted read-only, and rotated by deploying a newly versioned file. `RUNTIME_UID`/`RUNTIME_GID` must identify their non-root owner on the VPS; the API/ingress processes run as that identity. The API entrypoint reads secret files without printing values. MySQL root credentials are neither accepted nor mounted by the API or migration job. Frontend builds receive only `/api` and public base paths.

## Capability safety

For WS-33-B the production Compose definition fixes these settings to `false` rather than accepting operator overrides:

- `ELECTRONIC_PAYMENTS_ENABLED`: Conekta is absent from the runtime registry.
- `CFDI_ISSUANCE_ENABLED`: FINKOK is absent from the runtime registry.
- `CONNECTOR_DELIVERY_ENABLED`: connector delivery endpoints fail closed with `503 capability_disabled`.
- `EXTERNAL_POS_ENABLED`: POS submission endpoints fail closed with `503 capability_disabled`.

Enabling any one is separate capability certification work and is not part of this workstream.

## Release check

Run `scripts/verify-release-artifacts.sh` before publishing. It rejects forbidden tracked artifact categories, bounded credential patterns, and `latest` image identities. Also scan the produced filesystem explicitly:

```bash
docker run --rm --entrypoint sh "$API_IMAGE" -c 'test ! -e /app/tests && test ! -e /app/.git && test ! -e /app/.env'
docker run --rm --entrypoint sh "$DINER_WEB_IMAGE" -c '! grep -RIE "AUTH_JWT_SECRET|MYSQL_PASSWORD|FINKOK_PASSWORD" /usr/share/nginx/html'
docker run --rm --entrypoint sh "$STAFF_WEB_IMAGE" -c '! grep -RIE "AUTH_JWT_SECRET|MYSQL_PASSWORD|FINKOK_PASSWORD" /usr/share/nginx/html'
```

Never paste secret values into tickets, command history, logs, health/readiness responses, or the deployment report.

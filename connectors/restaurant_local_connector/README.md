# Pryecip Restaurant Local Connector

Python 3.12 service that polls the connector-specific REST API, durably records frozen preparation
operations in SQLite, renders `preparation-ticket-v1`, and submits to a configured CUPS queue. It
never connects to the SaaS database and never changes order, routing, or preparation execution truth.

The certified evidence boundary is `DESTINATION_SUBMISSION_ACCEPTED`: CUPS accepted the job and
returned a job ID. This does **not** mean paper was physically printed. The delivery guarantee is
durable at-least-once discovery plus logical operation idempotency, fenced cloud claims, a durable
local ledger, duplicate-risk mitigation, and explicit uncertainty—not exactly-once printing.

## Configuration

Install config at `/etc/pryecip-local-connector/config.toml`:

```toml
[cloud]
base_url = "https://api.example.com"
tls_verify = true

[runtime]
ledger_path = "/var/lib/pryecip-local-connector/ledger.sqlite3"
credentials_path = "/etc/pryecip-local-connector/credentials.json"
poll_seconds = 5
poll_jitter = 0.2
connect_timeout_seconds = 5
read_timeout_seconds = 15
max_backoff_seconds = 60
auth_failure_retry_seconds = 300
log_level = "INFO"

[targets.kitchen_printer]
adapter = "cups"
queue = "EPSON_KITCHEN"
columns = 42

[targets.bar_printer]
adapter = "cups"
queue = "EPSON_BAR"
columns = 42
```

Store the one-time enrollment result separately as mode `0600`:

```json
{"client_id":"...","client_secret":"..."}
```

Production permits HTTPS by default. Plain HTTP requires `allow_insecure_http = true` and is only
appropriate for explicit local development. The access token is memory-only; neither it nor the
client secret is written to SQLite or logs.

## Recovery semantics

`SUBMISSION_STARTED` is reconciled against the deterministic CUPS job title. A matching job becomes
accepted; inconclusive evidence becomes `UNCERTAIN` and is never automatically submitted again.
Accepted local evidence is replayed to the cloud without printing again. Missing mappings are
`ACTION_REQUIRED`; there is no default-printer fallback.

DB-backed credential validation on each machine request is the v1 immediate-revocation policy, not
an eternal architectural requirement. WebSocket notification, Redis, raw ESC/POS, TCP/9100,
self-updating, and mutable payload enrichment are deferred.

Known frozen `preparation-delivery-v1` gaps intentionally deferred: human-readable folio, notes,
allergens, guest/seat, course timing, customer name, and new modifier semantics.

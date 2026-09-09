# Pryecip Restaurant Local Connector

Python 3.12 service that polls the connector-specific REST API, durably records frozen Preparation
and Paid Check operations in SQLite, renders backend-authoritative payloads, and submits them to a
configured CUPS queue or ESC/POS destination. It
never connects to the SaaS database and never changes order, routing, or preparation execution truth.

The certified evidence boundary is `DESTINATION_SUBMISSION_ACCEPTED`: CUPS accepted the job and
returned a job ID, or the OS accepted all bytes for an ESC/POS destination. This does **not** mean
paper was physically printed. The delivery guarantee is
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
adapter = "escpos_network"
host = "192.168.20.40"
port = 9100
columns = 42
encoding = "cp850"

[targets.bar_printer]
adapter = "cups"
queue = "EPSON_BAR"
columns = 42

[targets.cashier_printer]
adapter = "escpos_usb"
device_path = "/dev/usb/lp0"
columns = 42
encoding = "cp850"
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
accepted; inconclusive CUPS evidence and interrupted raw ESC/POS submissions become `UNCERTAIN`
and are never automatically submitted again.
Accepted local evidence is replayed to the cloud without printing again. Missing mappings are
`ACTION_REQUIRED`; there is no default-printer fallback.

DB-backed credential validation on each machine request is the v1 immediate-revocation policy, not
an eternal architectural requirement. WebSocket notification, Redis, self-updating, and mutable
payload enrichment are deferred.

The connector polls both authoritative job families (`PreparationDispatch` and
`PaidCheckDispatch`) with the same device credential and location binding. Local SQLite namespaces
their independent numeric IDs by job family. A restart recovers a persisted, never-submitted claim
only after its cloud lease expires and the server grants a recovery claim.

## Run and status

```bash
pryecip-local-connector --config /etc/pryecip-local-connector/config.toml run
pryecip-local-connector --config /etc/pryecip-local-connector/config.toml status
```

The `status` command reports ledger integrity/backlog, configured logical destinations, credential
presence, and visible CUPS queues without printing or disclosing credentials. The included systemd
unit uses automatic restart; `Dockerfile` provides the same executable container boundary.

Known frozen `preparation-delivery-v1` gaps intentionally deferred: human-readable folio, notes,
allergens, guest/seat, course timing, customer name, and new modifier semantics.

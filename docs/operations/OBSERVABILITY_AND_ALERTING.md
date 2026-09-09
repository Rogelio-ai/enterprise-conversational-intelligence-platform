# Pilot Operational View and Alerts

Prometheus scrapes the private API `/metrics`; public ingress returns 404 for metrics/docs/OpenAPI. Prometheus is bound to VPS loopback. Structured JSON logs stay on stdout for collection by the hosting platform and contain correlation IDs, route templates, durations, status, and bounded domain identifiers—not request bodies, credentials, payment sources, fiscal XML, or artifacts.

| Concern | Signal / view | Alert |
| --- | --- | --- |
| API availability | `up{job="ecip-api"}`, `/health` | `ApiUnavailable` |
| latency/errors | `ecip_http_request_duration_seconds`, `ecip_http_requests_total` | `ApiErrorRateHigh` |
| DB readiness | `/ready` status metric through request counter | `DatabaseNotReady` |
| Order → Preparation | `ecip_operational_events_total{domain="preparation"}` | `OrderPreparationFailure` |
| backup | Pushgateway `ecip_backup_success`, timestamp | `BackupFailed` |
| payment | `restaurant_payment_execution_total{outcome="uncertain"}` | `PaymentUncertain` (inactive while disabled) |
| fiscal | fiscal operational event counter/log | `FiscalFailureOrUncertainty` (inactive while disabled) |
| Connector | heartbeat operational state | `ConnectorOffline` (inactive while disabled) |
| print | printing operational event/log and manager exception view | `PrintActionRequiredBacklog` (inactive while disabled) |

Use Prometheus `/alerts`, `/targets`, and the expression browser as the compact pilot dashboard. Alertmanager recipient configuration is `OPERATOR INPUT REQUIRED`. Validate rule syntax and the safe synthetic API-unavailable path with:

```bash
docker run --rm -v "$PWD/deploy/observability:/rules:ro" prom/prometheus:v3.5.0 \
  promtool test rules /rules/alerts.test.yml
```

Before pilot GO, configure a real recipient, send one synthetic notification, acknowledge it, and record timestamps. Disabled-capability alert rules remain present but naturally inactive until separate certification enables their signals.

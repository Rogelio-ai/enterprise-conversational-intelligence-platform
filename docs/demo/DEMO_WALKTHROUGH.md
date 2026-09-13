# WS-DEMO-01 local walkthrough

## Purpose and safety boundary

This environment runs the real Staff Web against the real API and an isolated MySQL
database populated only with deterministic fictitious data. It is for local visual and
workflow review. It is not PREPILOT, staging, production, or a source of operational
Restaurant data.

The Compose project is fixed to `pryecip-demo`, the database is `pryecip_demo`, and the
only persistent volume is `pryecip_demo_mysql_data`. MySQL is not published to the host.
The bootstrap refuses any host/database/environment outside this exact boundary.

## Prerequisites

- Docker with Compose v2
- Ports `18082` and `18083` available on loopback
- Google Chrome at `/usr/bin/google-chrome` only when running the optional smoke test

## Start

```sh
./scripts/demo/start_demo.sh
```

Compose waits for MySQL, migrates to the single Alembic head, bootstraps the dataset,
then starts the API and Staff Web. Inspect it with:

```sh
docker compose -f compose.demo.yaml ps
docker compose -f compose.demo.yaml logs bootstrap-demo api staff-web
```

URLs:

- Staff Web: <http://127.0.0.1:18082/staff/>
- API health: <http://127.0.0.1:18083/ready>
- API documentation: <http://127.0.0.1:18083/docs>

Login:

- Account: `manager@restaurant.demo`
- Password: `DemoManager123!`
- Role: `TENANT_ADMIN` with demo-wide navigation permission

These credentials are intentionally obvious local-demo values and have no use outside
the isolated stack.

## Recommended walkthrough

Login, confirm the yellow DEMO indicator, then visit:

1. Gerencia for the location overview.
2. Host for available and occupied tables.
3. Mesero and Cocina for the certified service/preparation workspaces.
4. Caja for the open fictitious register and cash movement.
5. Inventario → Resumen and Existencias.
6. Recepción, Pérdidas, Conteos físicos, and Conciliación.
7. Órdenes de compra and Preparaciones.
8. Reabastecimiento and Lotes.
9. Transferencias and Valuación; inspect FIFO and STANDARD_COST snapshots.

The story includes a fictional supplier receipt, lot-controlled raw materials, prepared
carnitas with yield evidence, a posted loss, a posted physical count and closed
reconciliation, an approved replenishment order, policies, a received transfer with FIFO
layers, and immutable FIFO/STANDARD_COST valuations.

## Reset

Reset is intentionally guarded and deletes only the fixed demo volume:

```sh
DEMO_ENV=demo ./scripts/demo/reset_demo.sh
```

It refuses unknown, staging, or production intent. The result is the same logical dataset.

## Stop

```sh
./scripts/demo/stop_demo.sh
```

This preserves demo data. Use the guarded reset command when intentionally discarding the
isolated demo database.

## External integrations

Electronic payment, Conekta, CFDI issuance, external POS, connector delivery, printers,
email, SMS, and WhatsApp are disabled or shown as not connected. The dataset contains no
provider transaction and performs no real money movement.

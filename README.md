# README.md

# Enterprise Conversational Intelligence Platform (ECIP)

> **Building the conversational intelligence layer of the enterprise.**

---

# Overview

Enterprise Conversational Intelligence Platform (ECIP) is an enterprise-grade, AI-native and Agent-native software platform designed to understand, reason, decide and execute business actions through conversational interactions.

ECIP is the intelligence layer that connects:

* Customers
* Employees
* Enterprise Systems
* Enterprise Knowledge
* Artificial Intelligence
* Intelligent Agents

through a unified conversational runtime.

The platform is designed to operate across multiple communication channels while preserving a single enterprise context.

---

# First Commercial Product

The first commercial implementation of ECIP is:

**Restaurant Intelligence Platform**

Restaurant Intelligence Platform is implemented as the first Domain Pack of ECIP.

The enterprise platform remains domain-independent.

---

# Project Goals

The objectives of ECIP are to:

* Improve customer experience.
* Increase business value.
* Improve operational efficiency.
* Increase enterprise knowledge.
* Support intelligent business decisions.
* Execute authorized business actions.
* Enable intelligent human collaboration.
* Provide a reusable enterprise conversational platform.

---

# What ECIP Is

ECIP is:

* Enterprise-first
* AI-native
* Agent-native
* Multi-tenant
* Multi-channel
* Context-aware
* Knowledge-driven
* Action-oriented
* Secure
* Auditable
* Production-ready

---

# What ECIP Is Not

ECIP is not:

* A chatbot.
* An IVR.
* A CRM.
* A call center.
* A telephony platform.
* A messaging application.
* A replacement for ERP or POS systems.

Enterprise operational systems remain systems of record.

ECIP operates above them as the conversational intelligence layer.

---

# High-Level Architecture

```text
Communication Channels
        │
        ▼
Channel Adapters
        │
        ▼
Conversation Runtime
        │
        ▼
Enterprise Intelligence Core
        │
        ▼
Domain Packs
        │
        ▼
Enterprise Systems
```

---

# Initial Capabilities

The first implementation includes:

* Conversation Runtime
* Enterprise Context
* Enterprise Knowledge
* Enterprise Memory
* Decision Intelligence
* Action Runtime
* Human Escalation
* Multi-channel Architecture
* Restaurant Domain Pack

---

# Repository Structure

```text
pryecip/

apps/
services/
packages/
domain-packs/
connectors/
infrastructure/
docs/
projects/
tests/
scripts/
```

The repository is organized to separate reusable enterprise capabilities from domain-specific implementations.

---

# Repository Documentation

The most important project documents are:

| Document                                                                            | Purpose                                               |
| ----------------------------------------------------------------------------------- | ----------------------------------------------------- |
| `README.md`                                                                         | Repository overview                                   |
| `PRODUCT_CONSTITUTION.md`                                                           | Defines the permanent identity of ECIP                |
| `projects/Enterprise_Conversational_Intelligence_Platform/Project_Audit_Profile.md` | Project-specific governance                           |
| `docs/`                                                                             | Functional, technical and architectural documentation |

---

# Governance

This project is governed by:

## Enterprise Audit Framework

Defines:

* Architecture governance
* Runtime governance
* Ownership governance
* Risk classification
* Validation
* Certification
* Audit methodology

## Product Constitution

Defines:

* Product identity
* Product mission
* Product principles
* Product scope
* Long-term product direction

Project-specific adaptations are defined in:

```text
projects/Enterprise_Conversational_Intelligence_Platform/
Project_Audit_Profile.md
```

---

# Development Principles

Development follows the following priorities:

1. Customer Value
2. Production Readiness
3. Runtime Preservation
4. Ownership Preservation
5. Context Preservation
6. Certified Behavior Preservation
7. Security
8. Minimal Necessary Change

---

# Reuse Strategy

Reusable enterprise components from previously certified projects may be incorporated after evaluation.

Examples include:

* Infrastructure
* Authentication patterns
* Durable Job Runtime
* Observability
* Backend conventions
* Frontend shell
* Testing patterns

Business-specific implementations are not copied directly.

---

# Current Status

Project Status

**Active Development**

Repository

**pryecip**

Current Product

**Enterprise Conversational Intelligence Platform**

First Domain Pack

**Restaurant Intelligence Platform**

Commercial Status

**Pre-MVP**

---

# Development Runtime

The executable baseline contains the FastAPI service and an isolated local MySQL service. Copy the
example environment and replace `AUTH_JWT_SECRET` with a random value of at least 32 characters.

```bash
cp .env.example .env
docker compose up --build
```

Compose applies the Alembic migration before starting the API. To apply it explicitly or inspect the migration state:

```bash
docker compose exec api alembic upgrade head
docker compose exec api alembic current
```

The current application migration head is `0005_resource_foundation`.

Authentication uses an Argon2 password hash and a signed access token. The relevant settings are
`AUTH_JWT_SECRET`, `AUTH_JWT_ALGORITHM`, `AUTH_ACCESS_TOKEN_TTL_MINUTES`, and
`PASSWORD_MIN_LENGTH`.

Bootstrap the first development or staging Tenant administrator with explicit environment values:

```bash
docker compose exec \
  -e BOOTSTRAP_TENANT_NAME='Development Tenant' \
  -e BOOTSTRAP_TENANT_SLUG='development' \
  -e BOOTSTRAP_ADMIN_EMAIL='admin@example.invalid' \
  -e BOOTSTRAP_ADMIN_PASSWORD \
  -e BOOTSTRAP_ADMIN_DISPLAY_NAME='Development Admin' \
  api python -m app.bootstrap_admin
```

Set `BOOTSTRAP_ADMIN_PASSWORD` in the invoking shell; the command does not print it. Re-running the
same bootstrap is safe and reports `already_configured`.

Log in (include `tenant_id` when the User has more than one active Tenant membership):

```bash
curl -X POST http://localhost:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.invalid","password":"<password>"}'
```

Use the returned access token for the authenticated context and permission-protected Tenant:

```bash
curl http://localhost:8000/auth/me -H 'Authorization: Bearer <access-token>'
curl http://localhost:8000/tenants/current \
  -H 'Authorization: Bearer <access-token>' \
  -H 'X-Tenant-ID: <signed-tenant-id>'
```

The Organization, Location, and Resource foundations expose these tenant-scoped endpoints:

```text
GET|POST   /organizations
GET|PATCH  /organizations/{organization_id}
GET|POST   /locations
GET|PATCH  /locations/{location_id}
GET|POST   /resources
GET|PATCH  /resources/{resource_id}
```

They use the corresponding `organization.read|manage`, `location.read|manage`, and
`resource.read|manage` permissions. Resource is a bounded, Location-owned physical operational
identity; hierarchy, capacity, availability, and other real-time operational state are deferred.
Tenant ownership is always taken from the signed authentication context, never from request data.

The Restaurant Domain Pack includes an internal, vendor-neutral POS integration contract for
Location, Customer, Catalog, Pricing, Promotion, and Order capabilities. A deterministic,
in-memory Mock POS Adapter implements that contract for future development without persistence or
a public API. No real POS integration is implemented yet.

A single active membership is inferred during login. Multiple active memberships require an
explicit `tenant_id` at login. `X-Tenant-ID` may only confirm the Tenant bound into the signed token;
it cannot switch or grant Tenant access.

Run backend tests in an isolated container:

```bash
docker compose run --rm api pytest
```

Run the same migration and integration suite against an isolated MariaDB 10.6 service with:

```bash
docker compose -p pryecip-mariadb -f compose.yaml -f compose.mariadb.yaml \
  run --build --rm api pytest
docker compose -p pryecip-mariadb -f compose.yaml -f compose.mariadb.yaml down -v
```

Runtime endpoints are available at:

* `http://localhost:8000/health`
* `http://localhost:8000/ready`
* `http://localhost:8000/metrics`

Stop the runtime without deleting the MySQL volume:

```bash
docker compose down
```

---

# Long-Term Vision

Build a reusable enterprise platform capable of supporting multiple industries through Domain Packs while preserving a common conversational intelligence core.

Restaurant Intelligence Platform is the first commercial realization of that vision.

---

# License

License information will be defined before the first commercial release.

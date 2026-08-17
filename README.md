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

The first executable baseline contains only the FastAPI service and an isolated local MySQL service.

```bash
cp .env.example .env
docker compose up --build
```

Compose applies the Alembic migration before starting the API. To apply it explicitly or inspect the migration state:

```bash
docker compose exec api alembic upgrade head
docker compose exec api alembic current
```

Run backend tests in an isolated container:

```bash
docker compose run --rm api pytest
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

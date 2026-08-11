# Central ISO

> Technical pilot for Quality Management System (QMS) document automation, combining read-only document scanning, deterministic business rules, traceability and n8n orchestration.

## Why it exists

The project came from a real industrial-quality problem: controlled documents, certificates and nonconformity records were spread across network folders and required recurring manual checks. The pilot validates that part of this work can be converted into a deterministic, auditable pipeline without modifying official source files or relying on paid SaaS services.

**Real status:** functional proof of concept / technical pilot. It is not presented as an ISO-certified system, an automated auditor, or a production corporate deployment.

## Highlights

- requirements discovery from Quality stakeholders;
- read-only document repository scanning;
- SHA-256 based idempotency and duplicate detection;
- local extraction for PDF, DOCX, XLSX, ODT, TXT and CSV;
- certificate and nonconformity tracking;
- deterministic rules for deadlines, effectiveness checks and human review;
- FastAPI REST API and relational persistence;
- n8n workflows for scheduling, queries, alerts and recovery;
- Tauri v2 desktop wrapper;
- Docker Compose environment;
- automated validation: **32 tests passed** in the clean GitHub CI build.

## Architecture

```text
Document source (read-only)
        ↓
Python scanner + extraction
        ↓
SHA-256 + classification
        ↓
SQLite / PostgreSQL
        ↓
Deterministic rules engine
        ↓
FastAPI REST
   ↙           ↘
n8n         Web/Tauri UI
        ↓
Evidence + human review
```

## Tech stack

Python · FastAPI · SQLAlchemy · PostgreSQL · SQLite · n8n · Docker · Tauri v2 · Rust · PyMuPDF · python-docx · openpyxl · pytest · GitHub Actions

## Public-demo safety

The repository ships with synthetic data only. Demo suppliers, certificate identifiers, people and scenarios are fictional. Corporate paths, credentials, brands and private infrastructure are not included. External AI is disabled by default and the demo does not make regulatory decisions automatically.

For full documentation, see the [Portuguese README](README.md), [case study](docs/CASE_STUDY.md), [architecture](docs/ARCHITECTURE.md), [security](docs/SECURITY.md) and [testing](docs/TESTING.md).

## Author

**Maycon Ferreira** — automation, applied AI, integrations and internal systems.

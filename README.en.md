<div align="center">

# Central ISO

**Quality technical pilot for turning recurring document checks into traceable, deterministic and reviewable verification.**

[![CI](https://github.com/Mayconxzdev/Central-ISO/actions/workflows/ci.yml/badge.svg)](https://github.com/Mayconxzdev/Central-ISO/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white)
![n8n](https://img.shields.io/badge/Automation-n8n-EA4B71?logo=n8n&logoColor=white)
![Docker](https://img.shields.io/badge/Demo-Docker-2496ED?logo=docker&logoColor=white)

[Portfolio case](https://mayconxzdev.github.io/en/cases/central-iso/) · [Architecture](docs/ARCHITECTURE.md) · [Security](docs/SECURITY.md) · [Testing](docs/TESTING.md) · [Português](README.md)

<img src="docs/images/01-dashboard-reference.png" alt="Sanitized demonstrative Central ISO dashboard" width="100%">

</div>

> Technical pilot for Quality Management System (QMS) document automation, combining read-only document scanning, deterministic business rules, traceability and n8n orchestration.

## Why it exists

The project came from a real industrial-quality problem: controlled documents, certificates and nonconformity records were spread across network folders and required recurring manual checks. The pilot validates that part of this work can be converted into a deterministic, auditable pipeline without modifying official source files.

**Real status:** functional proof of concept / technical pilot. It is not presented as an ISO-certified system, an automated auditor, or a production corporate deployment.

## Highlights

- requirements discovery from Quality stakeholders;
- read-only document repository scanning;
- SHA-256 based idempotency and change-based reprocessing;
- local extraction for PDF, DOCX, XLSX, ODT, TXT and CSV;
- certificate and nonconformity tracking;
- deterministic rules and human review;
- FastAPI REST API and relational persistence;
- n8n workflows for scheduling, queries, alerts and recovery;
- Tauri v2 desktop wrapper;
- Docker Compose demo environment.

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

## Visual references

These are **authorized demonstrative references of the pilot**. They explain the interface without exposing corporate documents, paths, names or operational counts.

| Dashboard | Certificates |
|---|---|
| ![Central ISO reference dashboard](docs/images/01-dashboard-reference.png) | ![Central ISO certificate reference](docs/images/02-certificates-reference.png) |

They are not presented as production or certification proof. See [`docs/SCREENSHOTS.md`](docs/SCREENSHOTS.md) for the evidence boundary.

## Tech stack

Python · FastAPI · SQLAlchemy · PostgreSQL · SQLite · n8n · Docker · Tauri v2 · Rust · PyMuPDF · python-docx · openpyxl · pytest · GitHub Actions

## Current validation

The latest successful `main` CI run recorded:

```text
32 passed
compileall passed
public-safety scan passed
Docker Compose validated
API smoke test passed
```

## Public-demo safety

The repository ships with synthetic data only. Demo identifiers, people and scenarios are fictional. Corporate paths, credentials, brands and private infrastructure are not included. External AI is disabled by default and the demo does not make regulatory decisions automatically.

For deeper review, see the [case study](docs/CASE_STUDY.md), [architecture](docs/ARCHITECTURE.md), [security](docs/SECURITY.md) and [testing](docs/TESTING.md).

## Scope limits

This public edition does not claim ISO certification, automatic regulatory compliance, corporate SSO, running RAG, replacement of Quality ownership or an official production deployment.

## Author

**Maycon Ferreira** — automation, applied AI, integrations and internal systems.

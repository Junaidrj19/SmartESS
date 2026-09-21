# SmartESS

Configurable agentic reliability-intelligence platform for SiC MOSFET power modules used in EV power electronics.

This repository contains the authoritative design documents, the implementation baseline, and the M1–M2 data contracts (**ModuleProfile**, **TestProfile**). Later application layers (API, UI, ML, agents, telemetry) are not implemented yet.

## Authoritative documents

- [PRD.md](PRD.md) — product requirements (BurnInGuard AI)
- [tech-stack.md](tech-stack.md) — technology choices
- [architecture.md](architecture.md) — system architecture
- [agent-rules.md](agent-rules.md) — agent safety and evidence rules
- [docs/implementation-status.md](docs/implementation-status.md) — repository state and roadmap
- [docs/data-model/module-profile.md](docs/data-model/module-profile.md) — ModuleProfile data model
- [docs/data-model/test-profile.md](docs/data-model/test-profile.md) — TestProfile data model

## Current milestone

**M2 — Test Profile Schema** (completed)

**Next:** M3 — Telemetry Schema

## Intended layout

```text
frontend/        Next.js UI
backend/         FastAPI, domain services, ML, agents, RAG
ml/              datasets, generators, features, models, evaluation
knowledge_base/  documents, processed data, metadata
scripts/
docs/
```

## Run / validate

```text
python3 -m pip install -e ".[dev]"
python3 -m pytest
```

Regenerate committed JSON Schemas from the Pydantic models:

```text
python3 scripts/export_module_profile_schema.py
```

Do not treat the illustrative reference profiles as verified manufacturer datasheets or test procedures. Do not treat synthetic data as production telemetry when they are introduced.

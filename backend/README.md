# Backend Phase 5

This directory contains the FastAPI backend skeleton, reusable STEP parser, and
internal manufacturing-oriented CAD feature extraction and CNC budgetary pricing
workflow with STEP-derived preview mesh generation.

The environment is managed by conda through `environment.yml` because
`pythonocc-core` is distributed reliably through conda-forge. Docker Compose
builds this environment and mounts the backend directory at `/workspace`.

## Commands

From the repository root:

```powershell
docker compose build
docker compose run --rm backend pytest -q
docker compose run --rm backend python scripts/validate_cad_stack.py
```

Start the API:

```powershell
docker compose up backend
```

The API exposes:

- `GET /`
- `GET /health/live`
- `GET /health/ready`
- `POST /cad/preview`
- `POST /quotes/cnc`
- `GET /openapi.json`

To analyze a real STEP file:

```powershell
docker compose run --rm backend python scripts/validate_cad_stack.py tests/fixtures/<file>.step
```

To extract feature inventory and conservative feature candidates:

```powershell
docker compose run --rm backend python scripts/extract_features.py tests/fixtures/<file>.step
docker compose run --rm backend python scripts/extract_features.py tests/fixtures/<file>.step --json
```

To generate a budgetary 3-axis CNC milling estimate:

```powershell
docker compose run --rm backend python scripts/price_cnc.py tests/fixtures/<file>.step --material aluminum_6061 --quantity 5
docker compose run --rm backend python scripts/price_cnc.py tests/fixtures/<file>.step --material aluminum_6061 --quantity 5 --json
```

The reusable parser lives under `app/cad/` and returns Pydantic data from
`app/schemas/cad.py`. Live OpenCascade objects must not cross that boundary.
The feature extractor also lives under `app/cad/` and returns Pydantic data from
`app/schemas/features.py`; API startup, health routes, pricing, and schemas do
not import OCC.
The CNC pricer lives under `app/pricing/`, consumes only OCC-free feature
schemas, and uses a versioned YAML rate card for budgetary coefficients.
The preview and quote workflows write uploaded STEP files to ephemeral
request-scoped temp directories, generate backend mesh previews from real
OpenCascade geometry, and delete uploads after each request.

## What This Contains

- FastAPI app factory
- Pydantic Settings configuration
- Thin API router structure
- Typed liveness/readiness responses
- Internal STEP parser service
- OCC-free CAD parsing schemas
- Internal feature extractor service
- OCC-free feature extraction schemas
- OpenCascade and pythonOCC imports
- Python 3.10 compatibility
- STEP reader availability
- Shape validity checks
- Exact B-Rep-derived bounding box, volume, surface area, and topology counts
- Face surface classification
- Edge curve classification
- Face adjacency through shared topological edges
- Simple through-hole and blind-hole candidates
- Simple planar-bottom pocket candidates
- Deterministic 0-100 heuristic complexity score
- Internal 3-axis CNC milling budgetary pricer
- Versioned CNC YAML rate card
- Pricing schemas with line items, warnings, assumptions, confidence, and diagnostics
- Synchronous CAD preview multipart endpoint
- Synchronous CNC multipart quote endpoint
- Backend STEP-derived preview mesh generation
- Structured upload, CAD, preview, and pricing API errors

## What This Does Not Do

This phase does not implement async quote jobs, retained upload storage, quote
history, production vendor pricing, CNC turning, setup orientation planning,
shape healing, XDE assembly/name/color traversal, sheet-metal recognition,
draft/undercut analysis, advanced machining features, or ML-based segmentation.

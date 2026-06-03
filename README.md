# RFQ Engine - Upload-to-Quote Workflow

This repository currently contains the Phase 5 upload-to-quote workflow for the
manufacturing RFQ engine.

Phase 0 CAD stack validation is preserved through the standalone diagnostic
script. Phase 1 adds the FastAPI application shell, typed health endpoints,
configuration, and routing conventions. Phase 2 adds reusable STEP parsing.
Phase 3 adds conservative manufacturing-oriented feature extraction from real
OpenCascade B-Rep geometry. Phase 4 adds internal research-informed 3-axis CNC
milling budgetary pricing with a versioned YAML rate card. Phase 5 adds a
synchronous CNC quote API, immediate backend-generated STEP-derived mesh
preview, and a React/Vite frontend workflow.

Async jobs, retained upload storage, quote history, shape healing, production
vendor pricing, and ML feature recognition remain deferred.

## Canonical Runtime

Docker Compose is the source of truth for this phase. Native Windows execution is
optional and is not considered the acceptance environment.

Build the validation image:

```powershell
docker compose build
```

Run the test suite:

```powershell
docker compose run --rm backend pytest -q
```

Start the API:

```powershell
docker compose up backend
```

Start the backend and frontend:

```powershell
docker compose up backend frontend
```

Health endpoints:

```powershell
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
```

Print the CAD stack report:

```powershell
docker compose run --rm backend python scripts/validate_cad_stack.py
```

Analyze a real STEP fixture:

```powershell
docker compose run --rm backend python scripts/validate_cad_stack.py tests/fixtures/example.step
```

Extract conservative feature candidates from a real STEP fixture:

```powershell
docker compose run --rm backend python scripts/extract_features.py tests/fixtures/example.step
docker compose run --rm backend python scripts/extract_features.py tests/fixtures/example.step --json
```

Generate a budgetary 3-axis CNC milling estimate:

```powershell
docker compose run --rm backend python scripts/price_cnc.py tests/fixtures/example.step --material aluminum_6061 --quantity 5
docker compose run --rm backend python scripts/price_cnc.py tests/fixtures/example.step --material aluminum_6061 --quantity 5 --json
```

Use the frontend:

```powershell
cd frontend
npm install
npm run build
npm run dev
```

## Current Scope

Included:

- Python 3.10 runtime
- `pythonocc-core` from conda-forge
- FastAPI backend shell
- Typed health and readiness endpoints
- Pydantic Settings configuration
- API router structure
- Reusable internal STEP parser service
- OCC-free CAD parsing schemas
- Reusable internal feature extraction service
- OCC-free feature extraction schemas
- OpenCascade import smoke checks
- Real STEP parsing when fixtures are provided
- Shape validity, bounding box, volume, surface area, and topology counts
- Face and edge inventories from exact B-Rep topology
- Shared-edge face adjacency graph
- Simple through-hole, blind-hole, and planar-bottom pocket candidates
- Deterministic heuristic complexity score
- Versioned CNC 3-axis milling budgetary rate card
- Internal CNC pricing service independent from CAD extraction
- CNC pricing CLI with line-item breakdowns and JSON output
- Synchronous `POST /cad/preview` multipart upload endpoint
- Synchronous `POST /quotes/cnc` multipart upload endpoint
- Backend-generated STEP-derived preview mesh
- React/Vite frontend with upload-time Three.js preview and quote breakdown
- pytest-based environment and fixture checks

Deferred:

- Async quote jobs
- Retained upload storage
- Quote history
- Persistent storage
- Production-calibrated vendor pricing
- CNC turning and advanced setup/orientation planning
- Mocked geometry
- Placeholder extraction
- Advanced manufacturing feature recognition
- Counterbores, countersinks, threads, tapped holes, hole patterns, interacting pockets, slots, bosses, fillets, chamfers
- Sheet-metal bends, draft analysis, undercuts, parting lines, and setup orientation
- Assembly/name/color traversal with STEPCAFControl/XDE
- Shape healing

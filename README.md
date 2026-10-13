# Orbixa — computational chemistry web platform

Orbixa is an **early-stage**, independent, Gaussian-inspired molecular workbench. It is **not** Gaussian-equivalent or scientifically validated.

## Deployed previews
- Frontend: https://orbixa-science-preview.onrender.com
- API: https://orbixa-api-preview.onrender.com/health

The frontend is a 3D molecular visualization preview with XYZ editing, method/basis inputs, and API connectivity. Anonymous scientific computation is intentionally disabled on the public API. The Python backend contains initial RHF/UHF and DFT RKS/UKS PySCF computation code for controlled, nonpublic development only.

## Project structure
- `frontend/index.html`: responsive web workbench with 3Dmol.js
- `backend/app/main.py`: FastAPI validation and gated prototype computation
- `backend/requirements-preview.txt`: lightweight web API dependencies (no PySCF)
- `backend/requirements.txt`: complete development dependencies (PySCF and geomeTRIC)
- `backend/tests`: initial API validation tests

## Local development

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
ORBIXA_ENABLE_JOBS=true uvicorn app.main:app --reload
```

For visualization: `cd frontend && python -m http.server 8080`.

Tests: `cd backend && PYTHONPATH=. pytest -q`.

## Safety and accuracy

Compute execution currently uses a local in-process thread pool and in-memory job registry. Do **not** enable public calculations or use this directly for untrusted multi-user workloads. Before real public computational service: authentication, tenant isolation, hard CPU/RAM/time limits, process/container isolation, durable job queues, quotas, payments/abuse prevention, audit logs, and numerical benchmarks are required.

This initial GitHub deployment revision is a reduced safe preview and **does not yet contain every feature from the earlier Orbixa v0.4 local ZIP**, including its SQLite job history. Do not treat the deployed API as equivalent to the local v0.4 prototype.

## Roadmap
1. Restore durable job persistence behind isolated workers.
2. Validate RHF/DFT numerical energies against published reference cases and establish a CI matrix.
3. Add secure authentication and persisted research projects.
4. Orbitals, density maps, vibrational spectra, transition states, excited-state methods, robust visualization.
5. Production observability, scaling, HPC integration and benchmark suite.

© Orbixa project. No Gaussian proprietary source included.

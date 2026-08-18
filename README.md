# AID GRID

Evaluation 1 web MVP for a privacy-preserving humanitarian coordination platform.

## What works now

- Crisis intake from the web dashboard
- Deterministic, explainable agent allocation using seeded organization capability summaries
- A visible privacy boundary: shared coordination data versus protected organizational data
- FastAPI endpoint that turns a crisis request into a response plan
- Browser fallback that keeps the visual demo usable while the API is offline

## Run locally

In one terminal:

```powershell
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

In a second terminal:

```powershell
cd web
pnpm dev
```

Open `http://localhost:3000`. The web app uses `http://localhost:8000` by default. Set `NEXT_PUBLIC_API_BASE_URL` to use a different API address.

## Evaluation 1 demo

1. Submit a critical medical-kit need for Region A.
2. Show the generated allocation plan and agent decision trace.
3. Explain the privacy panel: only capability summaries are shared, not donor, staff, inventory, warehouse, or route information.

## Deliberately deferred

Redis/PostGIS persistence, SMS processing, MapLibre, Android field workflows, authentication, and dynamic replanning are subsequent-evaluation work.

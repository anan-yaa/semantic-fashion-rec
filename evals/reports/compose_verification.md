# Docker Compose verification

Run on 2026-10-06 to check that `docker compose up --build` produces a working system.

| | |
|---|---|
| Machine | WSL2 on a laptop, 3.7 GB RAM available to WSL, no GPU used (CPU only) |
| Docker / Compose | Docker 29.1.3, Compose v5.6.0 |
| Stack | db (PostgreSQL 16 + pgvector), ollama (Gemma 3 1B), migrate (one-shot), app (FastAPI), frontend (Next.js) |
| Data | 2,000-product sample (not the full 44,072) |

## Result: works

| Step | Result |
|---|---|
| `docker compose up --build` from scratch (image pulls, builds, model download) | succeeded in 992 s (about 16.5 min) |
| Rebuild with changes | 35 s |
| Services | db, ollama and app healthy; `migrate` and `ollama-pull` exited 0; frontend serving `/` and `/outfit` (HTTP 200) |
| Schema | created by the `migrate` service |
| Load 2,000 products inside the container | ingest 66 s (includes dataset download), embed 102 s (about 20 products/s on CPU), keyword index 3 s; 0 errors; 2,000 rows with embeddings and search vectors |
| `POST /search` "black leather jacket for men" | 200; LLM used (gender=Men, color=Black); 5.0 s for a new query, 0.07 s repeated (LLM cache hit) |
| `POST /outfit` "outfit for the beach this summer" | 200; all four slots filled; LLM used; 4.1 s |
| CORS preflight from `http://localhost:3000` | allowed |
| Logs | JSON, with `request_id` and the LLM fields |
| Memory while running | app 1.0 GiB, ollama 0.97 GiB, frontend 49 MiB, db 47 MiB |

First search after the app starts took 64 s (models loading); on a cold first run it took 134 s because the first LLM call also timed out and fell back to plain search.

## Problems found and fixed during this run

| Problem | Fix |
|---|---|
| `numpy==1.24.3` has no Python 3.12 wheel, so the API image could not build | Pinned the versions the tests run on; CPU-only torch in the image |
| `next build` failed type-checking `vitest.config.ts` | Excluded it in `frontend/tsconfig.json` |
| Database had no schema, so `/products` returned 500 | Added the one-shot `migrate` service |
| Ollama on CPU takes about 8 s per call, equal to the 8 s timeout | Compose sets `LLM_QUERY_UNDERSTANDING_TIMEOUT_SECONDS=25` (use 8 with the GPU override) |
| API image copied `frontend/node_modules` and `.parquet` files (2.79 GB) | Extended `.dockerignore` (2.13 GB) |

## Not verified

- The full 44,072-product catalogue in Compose (estimated 35 min to embed on CPU).
- The GPU override (`docker-compose.gpu.yml`).
- The UI in a browser (only HTTP status codes were checked).

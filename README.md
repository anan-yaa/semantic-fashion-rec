# Semantic Fashion Recommendation System

A search microservice for a 44,072-product fashion catalogue that understands human-like, multilingual queries such as *"I need an outfit to go to the beach this summer"* or *"महिलाओं के लिए गहने"* (jewellery for women), not just keywords like "t-shirt".

It combines **semantic vector search** (multilingual-e5 embeddings in PostgreSQL + pgvector), **keyword search** (PostgreSQL full-text search) and **LLM query understanding** (TinyLlama, running locally through Ollama), behind a FastAPI backend with a Next.js frontend.

| Requirement | How it's met |
|---|---|
| 1. Parse natural-language, multilingual queries | multilingual-e5 understands queries in English, Hindi and other languages; TinyLlama extracts keywords and filters (color, gender, season) from English queries |
| 2. Find relevant products with semantic search and LLMs | Hybrid search: vector + keyword results fused with Reciprocal Rank Fusion, with LLM-inferred filters and product-type detection |
| 3. Handle an evolving product catalogue | One sync command, run nightly by cron: adds new products, updates changed ones, hides removed ones, and re-embeds only what changed |

**Contents:** [Architecture](#architecture) · [How a search works](#how-a-search-works) · [Evolving catalogue](#evolving-catalogue) · [Evaluation](#evaluation) · [Getting started](#getting-started) · [API](#api) · [Configuration](#configuration) · [Testing](#testing) · [Project structure](#project-structure) · [Known limitations](#known-limitations)

---

## Architecture

```mermaid
flowchart LR
    UI["Next.js frontend<br/>(search, filters, sort, pages)"] -->|HTTP| API["FastAPI backend"]
    API -->|"query understanding<br/>(keywords + filters)"| LLM["Ollama<br/>TinyLlama 1.1B"]
    API -->|embed query| E5["multilingual-e5-base<br/>(768-dim, GPU if available)"]
    API -->|"vector (HNSW) +<br/>keyword (GIN) search"| DB[("PostgreSQL 16<br/>+ pgvector")]
    CRON["cron: nightly sync"] --> SYNC["sync_catalogue.py"]
    FEED["Catalogue feed<br/>(Hugging Face dataset)"] --> SYNC
    SYNC -->|"ingest, embed changed,<br/>index changed"| DB
```

| Component | Technology |
|---|---|
| API | FastAPI, Pydantic, SQLAlchemy 2 |
| Database | PostgreSQL 16 with pgvector: HNSW index for vectors, GIN index for full-text search |
| Embeddings | `intfloat/multilingual-e5-base` via sentence-transformers (768 dimensions, L2-normalized, `query:` / `passage:` prefixes) |
| LLM | TinyLlama 1.1B (Q4) via Ollama, local; the Gemini API is supported as an alternative provider |
| Frontend | Next.js 14, React 18, Tailwind CSS |
| Data | [`HEBA2002/fashion-product-images-small`](https://huggingface.co/datasets/HEBA2002/fashion-product-images-small): 44,072 products, 141 product types (no prices or images are used) |

## How a search works

```mermaid
flowchart TD
    Q["POST /search<br/>'black leather jacket for men'"] --> U["1. LLM query understanding<br/>keywords: 'black leather jacket'<br/>filters: gender=Men, color=Black"]
    Q --> T["2. Product-type detection<br/>'jacket' → Jackets"]
    U --> K["4. Keyword search<br/>LLM keywords + user and LLM filters"]
    Q --> V["3. Vector search<br/>original query + user filters only"]
    T --> V
    T --> K
    V --> F["5. Reciprocal Rank Fusion (k=60)"]
    K --> F
    F --> S["6. Sort and paginate the top 100 matches"]
```

1. **LLM query understanding** ([`app/providers/ollama_llm.py`](app/providers/ollama_llm.py), [`app/services/query_understanding/`](app/services/query_understanding/))
   - TinyLlama turns the query into a keyword phrase plus optional gender, color and season filters.
   - Its output is forced into a **JSON schema** whose allowed values are the catalogue's own, read from the database and cached for 5 minutes. So it can't invent a color like "Male" or "Black, White".
   - A filter is kept only if the query actually **mentions** it ("autumn" counts as Fall, "ladies" as Women). That stops guesses like *woollen coat → Summer*.
   - Category isn't inferred: the small model got it wrong too often (*saree → Footwear*).
   - Non-Latin-script queries (e.g. Hindi) skip the LLM; TinyLlama mistranslated them into unrelated products.
   - **Any failure falls back** to plain search with the original query: timeout (8 s), connection error or invalid output. Search never fails because of the LLM.
   - **Circuit breaker** ([`circuit_breaker.py`](app/services/query_understanding/circuit_breaker.py)): after 3 timeouts or connection errors in a row (or one rate limit), the LLM is skipped instantly for 30 s instead of every search waiting for it. After the cooldown one request checks whether it has recovered. Invalid answers and skipped Hindi queries don't count, since the service is still up.
   - The response's `understanding` field reports what the LLM understood, or why it wasn't used. The UI shows it as "Understood as: …".
2. **Product-type detection** ([`app/services/search/product_types.py`](app/services/search/product_types.py))
   - If the query names one of the catalogue's 141 product types, results are limited to that type.
   - Matching uses the same English stemming as keyword search. Words after *for / to / with / under* are ignored, so "warm layer to wear under a jacket" doesn't become a jacket search.
   - This fixes *black leather jacket for men* returning leather wallets: the catalogue has no leather jackets, and embeddings weigh "black leather" heavily.
3. **Vector search** ([`vector_search.py`](app/services/search/vector_search.py)): cosine similarity on e5 embeddings through the HNSW index, always using the **original** query. This is what handles Hindi and vague, descriptive queries.
4. **Keyword search** ([`keyword_search.py`](app/services/search/keyword_search.py))
   - PostgreSQL full-text search (`ts_rank`) on the LLM's keyword phrase, with the LLM's filters applied.
   - In hybrid mode a product must match at least 75% of the query's words; partial matches of long queries were mostly noise.
   - Within a detected product type, this relaxes to 50% if nothing matches.
5. **Fusion:** results from both searches are combined with Reciprocal Rank Fusion.
6. **Sorting and pages:** the top 100 matches can be sorted by relevance, newest (product year) or name, and are returned in pages.

Filters chosen by the user always override the LLM's, and apply to both searches. LLM-inferred filters apply to keyword search only, so a wrong guess can't hide good semantic matches. Products that left the catalogue are excluded unless a request asks for them.

## Evolving catalogue

```bash
PYTHONPATH=. python3 scripts/sync_catalogue.py [--dataset-path PATH]
```

| Catalogue change | What the sync does |
|---|---|
| New product | Inserted, embedded and keyword-indexed |
| Changed product | Updated; only that product is re-embedded and re-indexed (detected via a SHA-256 `content_hash` of its text) |
| Unchanged product | Skipped, nothing recomputed |
| Product missing from the feed | Marked unavailable and hidden from search and browsing (not deleted) |
| Product returns to the feed | Made available again |
| Empty or broken feed | Refuses to hide the whole catalogue |
| New filter value (e.g. a new color) | Read from the database and usable by the LLM within 5 minutes, without a restart |

It's safe to re-run: on an unchanged catalogue it takes about a minute and changes nothing. Product IDs stay stable across syncs.

**Scheduled sync:** [`scripts/cron_sync_catalogue.sh`](scripts/cron_sync_catalogue.sh) runs the sync from cron. It skips a run if the previous one is still going, and logs to `logs/sync_catalogue.log`. To install it daily at 02:00:

```bash
(crontab -l 2>/dev/null; echo "0 2 * * * $PWD/scripts/cron_sync_catalogue.sh") | crontab -
```

## Evaluation

80 queries (keyword-style, natural-language, occasion, gender, vague and 10 Hindi) are scored against an answer key of 20 relevant products per query. Full results, the per-query breakdown and the Gemini comparison are in **[`evals/EVAL_RESULTS.md`](evals/EVAL_RESULTS.md)**.

Hybrid search (what the app uses), same code with and without the LLM:

| | NDCG@10 | Precision@10 | MRR | Recall@20 | Recall@50 |
|---|---|---|---|---|---|
| Without LLM | 0.820 | 0.720 | 0.925 | 0.585 | 0.706 |
| With TinyLlama | **0.831** | **0.731** | **0.931** | **0.594** | 0.705 |

- **TinyLlama used for all 70 English queries with 0 failures** (10 Hindi queries skipped by design). On a GTX 1650 it takes about 0.3 s per query (about 1.2 s on CPU).
- **The gain is real but small:** 3 queries improved and none got worse. In an earlier run on older code, the Gemini API made hybrid search slightly worse (0.825 → 0.803), mostly by shortening vague queries to one word.
- **Caveat:** the answer key was built from the embedding model's own top results, so it favours vector search (0.923 NDCG@10) and understates what keyword search and the LLM add.

```bash
PYTHONPATH=. python3 scripts/run_eval.py \
  --ground-truth evals/ground_truth/ground_truth_v2_real.json \
  --output-prefix evals/reports/my_run --use-query-understanding
```

## Getting started

### Prerequisites

- Python 3.12, Node.js 18+, Docker
- [Ollama](https://ollama.com)
- Optional: an NVIDIA GPU (a 4 GB GTX 1650 is enough for both models); without one, everything runs on CPU, more slowly
- About **6 GB of free RAM** to run everything at once. On WSL, raise the default memory limit in `%UserProfile%\.wslconfig`, e.g. `memory=5GB` and `swap=4GB`.

### 1. Install and configure

```bash
pip install -r requirements.txt
cp .env.example .env          # defaults work for local development
```

### 2. Start PostgreSQL with pgvector

```bash
docker compose up -d db
# or, without Compose:
docker run -d --name fashion_rec_db -p 5432:5432 \
  -e POSTGRES_DB=fashion_rec -e POSTGRES_USER=fashion_rec -e POSTGRES_PASSWORD=dev_password \
  pgvector/pgvector:pg16
```

### 3. Create the schema

```bash
alembic upgrade head
```

### 4. Load the catalogue

```bash
PYTHONPATH=. python3 scripts/sync_catalogue.py
```

This downloads the dataset, ingests the 44,072 products, computes their embeddings and builds the keyword index. Embedding every product is the slow part without a GPU. If you don't have one, you can compute the embeddings on a free Colab GPU instead:
1. `scripts/export_embedding_batch.py`
2. [`colab/compute_embeddings_colab.ipynb`](colab/compute_embeddings_colab.ipynb)
3. `scripts/import_embeddings.py`

### 5. Start the LLM

```bash
ollama pull tinyllama
ollama ps      # after the first query: PROCESSOR should say "100% GPU" if you have one
```

If `ollama ps` says CPU on a GPU machine (for example after a WSL restart), run `sudo systemctl restart ollama`.

### 6. Run the backend and frontend

```bash
# Terminal 1: API on http://localhost:8000 (docs at /docs)
PYTHONPATH=. python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Terminal 2: UI on http://localhost:3000
cd frontend && npm install && npm run dev
```

The embedding model and TinyLlama load in the background when the backend starts (about a minute). Searches made during that time are slower.

### Docker Compose

`docker compose up` starts PostgreSQL, Redis, Ollama (it pulls TinyLlama automatically) and the API. For GPU support, add the override: `docker compose -f docker-compose.yml -f docker-compose.gpu.yml up` (requires the NVIDIA Container Toolkit). The frontend isn't included in Compose yet; see [Known limitations](#known-limitations).

## API

Interactive documentation: **http://localhost:8000/docs**.

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/search` | Hybrid, vector or keyword search with filters, sorting and pages |
| `GET` | `/products` | Browse available products: `page`, `page_size`, `category`, `gender`, `color`, `season`, `sort` |
| `GET` | `/products/facets` | Filter values in the catalogue (for dropdowns) |
| `GET` | `/health` | 200 when the database is reachable, 503 otherwise |

**Rate limiting:** each search can call the LLM and the embedding model, so `POST /search` is limited per client IP: 30 searches per minute, with bursts of up to 10. Over the limit, the API returns `429 Too Many Requests` with a `Retry-After` header and `{"detail": "Too many searches. Try again in N seconds."}`, and the UI shows that message. Browsing, facets and `/health` aren't limited.

Example:

```bash
curl -X POST http://localhost:8000/search -H "Content-Type: application/json" \
  -d '{"query": "black leather jacket for men", "limit": 24, "page": 1, "sort": "relevance",
       "filters": {"season": "Fall"}}'
```

```jsonc
{
  "products": [{"name": "ADIDAS Men Black Jacket", "article_type": "Jackets", "color": "Black", "gender": "Men", "...": "..."}],
  "query": "black leather jacket for men",
  "method": "hybrid",
  "total_products": 100,          // matches across all pages (top 100 at most)
  "page": 1, "page_size": 24, "total_pages": 5,
  "took_ms": 640.2,
  "understanding": {
    "used_llm": true,
    "keywords": "black leather jacket",
    "inferred_filters": {"gender": "Men", "color": "Black"},
    "fallback_reason": null         // or "unsupported_query" / "llm_unavailable"
  }
}
```

Request fields:
- `query`: required, 1–500 characters
- `method`: `hybrid` (default), `vector` or `keyword`
- `filters`: any of `category`, `gender`, `color`, `season`, `availability`
- `limit`: results per page, 1–100
- `page`: starting at 1
- `sort`: `relevance`, `newest` or `name`

## Configuration

All settings come from environment variables or `.env` ([`core/config.py`](core/config.py)).

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://fashion_rec:dev_password@localhost:5432/fashion_rec` | PostgreSQL connection |
| `EMBEDDING_MODEL` | `intfloat/multilingual-e5-base` | Embedding model (768 dimensions) |
| `EMBEDDING_BATCH_SIZE` | `64` | Batch size when embedding products |
| `QUERY_UNDERSTANDING_ENABLED` | `true` | Use the LLM on each search |
| `LLM_PROVIDER` | `ollama` | `ollama` (local) or `gemini` |
| `OLLAMA_MODEL` | `tinyllama` | Ollama model name |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | – / `gemini-3.5-flash-lite` | Only for `LLM_PROVIDER=gemini` |
| `LLM_QUERY_UNDERSTANDING_TIMEOUT_SECONDS` | `8.0` | LLM time limit per search before falling back |
| `LLM_QUERY_UNDERSTANDING_EVAL_TIMEOUT_SECONDS` | `15.0` | LLM time limit during evals |
| `LLM_CIRCUIT_FAILURE_THRESHOLD` | `3` | Consecutive LLM timeouts or connection errors before it's skipped |
| `LLM_CIRCUIT_COOLDOWN_SECONDS` | `30` | How long the LLM is skipped before checking whether it has recovered |
| `CATALOGUE_FACETS_CACHE_SECONDS` | `300` | How often filter values and product types are re-read from the database |
| `WARM_UP_MODELS_ON_STARTUP` | `true` | Load the models in the background at startup |
| `RATE_LIMIT_ENABLED` | `true` | Limit how often each client can search |
| `SEARCH_RATE_LIMIT_PER_MINUTE` | `30` | Sustained searches allowed per client per minute |
| `SEARCH_RATE_LIMIT_BURST` | `10` | Searches a client can make in a quick burst |
| `TRUST_PROXY_HEADERS` | `false` | Read the client IP from `X-Forwarded-For`; enable only behind a reverse proxy that sets it |
| `LOG_LEVEL` | `INFO` | Logging level |

Frontend: `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`).

## Testing

```bash
python3 -m pytest tests/                 # backend: ~355 tests, about 1–5 minutes
python3 -m pytest tests/ -m slow         # opt-in tests that load the real embedding model
cd frontend && npx vitest --run          # frontend: 55 tests
```

- The backend tests use a fake LLM and fake embeddings, so they don't need Ollama or a GPU.
- Integration tests use a separate `fashion_rec_test` database on the same PostgreSQL server, created automatically. Without PostgreSQL they're skipped.
- Stop the backend and frontend while running the full suite on a machine with little memory.

Current status: 355 passed and 2 known failures, both present before the latest changes:
- `test_llm_inferred_filter_is_applied_and_changes_results` expects LLM filters to restrict *all* results, but they were deliberately limited to keyword search.
- `test_e5_prefixes::test_batch_processing` is an embedding-model test that returns 4 results where it expects 3.

## Project structure

```
app/
  api/routes/          search.py (POST /search), products.py (browse, facets)
  providers/           e5.py (embeddings), ollama_llm.py, llm.py (Gemini), fakes for tests
  services/
    search/            hybrid.py, vector_search.py, keyword_search.py, rank_fusion.py,
                       product_types.py, sorting.py
    query_understanding/  LLM orchestration, fallback, filter validation, circuit breaker
    ingestion/         dataset loading, normalization, hashing, insert/update/deactivate
    embedding/         batch embedding of new or changed products, Colab export/import
    keyword_index/     full-text index for new or changed products
    eval/              metrics (NDCG, Precision, MRR, Recall) and eval runner
  db/                  SQLAlchemy model and repository
alembic/               database migrations
scripts/               sync_catalogue.py, cron_sync_catalogue.sh, run_eval.py, ...
evals/                 queries, answer keys, reports, EVAL_RESULTS.md
frontend/              Next.js app (app/, components/, lib/api.ts)
tests/                 unit/, integration/, model/ (slow)
```

## Known limitations

- **The LLM step only helps Latin-script queries.** TinyLlama can't handle Hindi, so Hindi queries rely on the multilingual embedding search alone. The LLM's measured gain is small (+0.011 NDCG@10).
- **Evaluation:** the answer key favours vector search, and 80 queries can only show fairly large differences. An earlier, human-reviewed answer key (`ground_truth_v1.json`) no longer matches the database's product IDs.
- **The vector index may miss matches.** Vector Recall@20 is 0.71 against an answer key made of the embedding model's own top 20. Approximate HNSW search with the default `ef_search = 40` is the likely cause, but this isn't confirmed yet.
- **Data:** the dataset has no prices or usable images, so there's no price sorting and product cards show a color tile instead of a photo. "Outfit" queries return a single ranked list, not a combination of items.
- **Reliability:**
  - Search returns 500, not 503, when the database is down.
  - There's no overall request timeout.
  - The circuit breaker's state is kept per process, so with several API workers each one finds an outage separately.
- **Security and operations:**
  - No authentication or HTTPS.
  - Rate limits are per IP address, so people sharing one IP (an office network) share a limit. They're also per API process; several workers or servers would need a shared store such as Redis.
  - The default database password is a development one.
  - CORS allows only localhost.
  - No request IDs, structured (JSON) logs, metrics, dashboards or alerts.
- **Deployment:**
  - Docker Compose hasn't been run end-to-end, and doesn't include the frontend.
  - Redis is configured but not used.
  - There's no CI/CD and no production configuration.
- **Catalogue sync** runs from cron or by hand; there's no endpoint or event-driven trigger.

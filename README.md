# Semantic Fashion Recommendation System

A search microservice for a 44,072-product fashion catalogue that understands human-like, multilingual queries such as *"I need an outfit to go to the beach this summer"* or *"महिलाओं के लिए गहने"* (jewellery for women), not just keywords like "t-shirt".

It combines **semantic vector search** (multilingual-e5 embeddings in PostgreSQL + pgvector), **keyword search** (PostgreSQL full-text search) and **LLM query understanding** (Gemma 3 1B, running locally through Ollama), behind a FastAPI backend with a Next.js frontend.

| Requirement | How it's met |
|---|---|
| 1. Parse natural-language, multilingual queries | The query's language is detected (10 languages: English, Spanish, French, German, Italian, Portuguese, Hindi, Arabic, Chinese, Russian). Gemma 3 1B translates non-English queries into English and extracts filters (color, gender, season); the multilingual-e5 embedding model matches meaning across languages |
| 2. Find relevant products with semantic search and LLMs | Hybrid search: vector + keyword results fused with Reciprocal Rank Fusion, with LLM-inferred filters and product-type detection |
| 3. Handle an evolving product catalogue | One sync command, run nightly by cron: adds new products, updates changed ones, hides removed ones, and re-embeds only what changed |

**Contents:** [Architecture](#architecture) · [How a search works](#how-a-search-works) · [Outfit builder](#outfit-builder) · [Evolving catalogue](#evolving-catalogue) · [Evaluation](#evaluation) · [Getting started](#getting-started) · [API](#api) · [Configuration](#configuration) · [Testing](#testing) · [Project structure](#project-structure) · [Known limitations](#known-limitations)

---

## Architecture

```mermaid
flowchart LR
    UI["Next.js frontend<br/>(search, filters, sort, pages)"] -->|HTTP| API["FastAPI backend"]
    API -->|"query understanding<br/>(translation + filters)"| LLM["Ollama<br/>Gemma 3 1B"]
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
| LLM | Gemma 3 1B via Ollama, local (chosen over TinyLlama and Qwen 2.5 1.5B, see [`evals/LLM_COMPARISON.md`](evals/LLM_COMPARISON.md)); the Gemini API is supported as an alternative provider |
| Language detection | [lingua](https://github.com/pemistahl/lingua-py), recognising 10 languages: six Latin-script ones statistically, Hindi, Arabic, Chinese and Russian by script (~40 MB RAM) |
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
   - **The language is detected first,** by a small language-identification library rather than the LLM: a 1B model can't reliably tell Spanish or French from English. It recognises 10 languages: English, Spanish, French, German, Italian and Portuguese (statistically), and Hindi, Arabic, Chinese and Russian (by script). Other scripts (Japanese, Korean, Tamil and so on) are labelled "non-English" and still sent for translation. A query only counts as non-English when that's clearly more likely than English, and single words stay English (fashion is full of loanwords such as "poncho" and "mules"), so almost all short English queries aren't misread. Detection scored 260 of 263 labelled queries ([`evals/EXPLORATION.md`](evals/EXPLORATION.md#extending-to-10-languages)).
   - **Gemma 3 1B is told the language** ("Query (Spanish): …"). It returns the query in English, translating non-English queries, plus optional gender, color and season filters.
   - **Non-English queries are searched in English,** on both vector and keyword search: the catalogue is English, and the embedding model alone matches some words by spelling ("chaqueta" → "Red Chief" shoes). **English queries keep the user's own words;** the LLM only adds filters, because measured LLM rewrites of English queries dropped useful words.
   - Its output is forced into a **JSON schema** whose allowed values are the catalogue's own, read from the database and cached for 5 minutes. So it can't invent a color like "Male" or "Black, White".
   - A filter is kept only if the query actually **mentions** it ("autumn" counts as Fall, "ladies" as Women). That stops guesses like *woollen coat → Summer*.
   - Category isn't inferred: the small model got it wrong too often (*saree → Footwear*).
   - English-only models can skip non-Latin-script queries instead (`LLM_SKIP_NON_LATIN_QUERIES=true`, used with TinyLlama).
   - **Any failure falls back** to plain search with the original query: timeout (8 s), connection error or invalid output. Search never fails because of the LLM.
   - **Circuit breaker** ([`circuit_breaker.py`](app/services/query_understanding/circuit_breaker.py)): after 3 timeouts or connection errors in a row (or one rate limit), the LLM is skipped instantly for 30 s instead of every search waiting for it. After the cooldown one request checks whether it has recovered. Invalid answers and skipped Hindi queries don't count, since the service is still up.
   - The response's `understanding` field reports the filters, the English translation when there was one, or why the LLM wasn't used. The UI shows it as "Understood as: …" or "Searched in English as: …".
2. **Product-type detection** ([`app/services/search/product_types.py`](app/services/search/product_types.py))
   - If the query names one of the catalogue's 141 product types, results are limited to that type.
   - Matching uses the same English stemming as keyword search. Words after *for / to / with / under* are ignored, so "warm layer to wear under a jacket" doesn't become a jacket search.
   - This fixes *black leather jacket for men* returning leather wallets: the catalogue has no leather jackets, and embeddings weigh "black leather" heavily.
3. **Vector search** ([`vector_search.py`](app/services/search/vector_search.py)): cosine similarity on e5 embeddings through the HNSW index. It uses the user's query, or the English translation for non-English queries.
4. **Keyword search** ([`keyword_search.py`](app/services/search/keyword_search.py))
   - PostgreSQL full-text search (`ts_rank`) on the LLM's keyword phrase, with the LLM's filters applied.
   - In hybrid mode a product must match at least 75% of the query's words; partial matches of long queries were mostly noise.
   - Within a detected product type, this relaxes to 50% if nothing matches.
5. **Fusion:** results from both searches are combined with Reciprocal Rank Fusion.
6. **Sorting and pages:** the top 100 matches can be sorted by relevance, newest (product year) or name, and are returned in pages.

Filters chosen by the user always override the LLM's, and apply to both searches. LLM-inferred filters apply to keyword search only, so a wrong guess can't hide good semantic matches. Products that left the catalogue are excluded unless a request asks for them.

## Outfit builder

Beyond search, **`POST /outfit`** (and the **Outfit builder** page in the UI) answers a request like "I need an outfit to go to the beach this summer" with a *combination* of items instead of one ranked list: a **top, bottom, footwear and accessory**, each with a pick and alternatives.

How it works ([`app/services/outfit.py`](app/services/outfit.py)):

1. **Fixed slots over the catalogue's own subcategories:** Top (Topwear), Bottom (Bottomwear), Footwear, and Accessory (Bags, Watches, Eyewear, Jewellery). An LLM doesn't invent the slots, because a 1B model can't reliably split a request into parts.
2. **One hybrid search per slot**, with the full query restricted to that slot. The occasion therefore decides which footwear or accessory ranks first: for the beach query, sandals and a beach bag; for a men's wedding, formal shoes and sunglasses.
3. **The LLM adds what it already adds to search:** gender, colour and season, with the same rules (user filters win, LLM filters apply to the keyword side only, the result is cached). Non-English requests are translated first, as in search.
4. **One wearer per outfit.** The gender comes from the user's filter, else the LLM's, else a vote among the first slot's top 10 results, so the outfit isn't men's shorts with women's sandals.
5. **Repeat listings are collapsed:** the catalogue lists some products twice under one name.

```bash
curl -X POST localhost:8000/outfit -H 'Content-Type: application/json' \
  -d '{"query": "formal outfit for a wedding for men", "per_slot": 3}'
```

The response lists `slots` (`top`, `bottom`, `footwear`, `accessory`, each with `products`), the `gender` it was built for, and what the LLM understood. It shares the search rate limit, since each outfit runs one search per slot.

**Measured:** about 1.3 to 1.9 s per outfit on the real catalogue once the models are warm (about 1 s of it is the LLM; a repeated request skips that), checked by reading outfits for several occasions. It has **no quality evaluation** like the search eval, because there is no answer key for "a good outfit".

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

80 queries (keyword-style, natural-language, occasion, gender, vague and 10 Hindi) are scored against an answer key of 20 relevant products per query. Full results, the per-query breakdown and the Gemini comparison are in **[`evals/EVAL_RESULTS.md`](evals/EVAL_RESULTS.md)**. **System health** (latency, throughput, reliability when the LLM fails, startup, memory), measured with the current LLM: **[`evals/SYSTEM_HEALTH.md`](evals/SYSTEM_HEALTH.md)**. Headlines: p50 0.8 s for one user, about 1.4 searches/s under load (the LLM is the bottleneck), 0 errors in 1,360 requests, and no failed searches when the LLM hangs. The experiments behind the design choices (LLM selection, local vs hosted, multilingual handling, keyword strictness, how far to trust the answer key) are collected in **[`evals/EXPLORATION.md`](evals/EXPLORATION.md)**.

**Choosing the LLM:** TinyLlama, Qwen 2.5 1.5B and Gemma 3 1B were compared, one at a time on the GPU ([`evals/LLM_COMPARISON.md`](evals/LLM_COMPARISON.md)):

| | TinyLlama 1.1B (before) | **Gemma 3 1B (now)** |
|---|---|---|
| Multilingual queries: share of top 10 that's relevant (22 Hindi/Spanish/French queries) | 0.69 | **0.85** |
| ↳ Spanish / French / Hindi | 0.54 / 0.72 / 0.79 | **0.89 / 1.00** / 0.76 |
| English queries: hybrid NDCG@10 (70 queries) | 0.808 | 0.794 |
| LLM time per query (GTX 1650) | ~0.3 s | ~0.9 s |

- **Multilingual search improves a lot; English is essentially unchanged.** English is level with search without any LLM (0.795). The extra ~0.6 s per search is a deliberate trade of speed for accuracy.
- **Qwen 2.5 1.5B was ruled out:** it invented Hindi translations (red saree → "lilac").
- **Why a dedicated test for non-English queries:** the main answer key was built from the embedding model's own top results. It favours vector search (0.923 NDCG@10), and for Hindi it rewards searching the Hindi text unchanged, even over a correct translation. Multilingual quality is therefore measured with written relevance rules ([`evals/EXPLORATION.md`](evals/EXPLORATION.md#3-multilingual-queries)).

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
ollama pull gemma3:1b
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

The embedding model and the LLM load in the background when the backend starts (about a minute). Searches made during that time are slower.

### Docker Compose

Copy `.env.example` to `.env` and set `POSTGRES_PASSWORD` (Compose refuses to start without it). Then:

```bash
docker compose up --build        # first run: about 15 minutes (image pulls and builds)
```

This starts PostgreSQL, Ollama (it pulls the configured model automatically), a one-shot `migrate` step that creates the schema, the API on http://localhost:8000 and the UI on http://localhost:3000. The database starts **empty**, so load a catalogue:

```bash
# Quick demo: 2,000 products (about 3 minutes on CPU)
docker compose exec -e PYTHONPATH=/app app python scripts/ingest_catalogue.py --sample 2000
docker compose exec -e PYTHONPATH=/app app python scripts/embed_catalogue.py
docker compose exec -e PYTHONPATH=/app app python scripts/index_keywords.py --limit 100000

# Full catalogue (44,072 products): downloads the dataset and embeds on CPU, about 35 minutes
docker compose exec -e PYTHONPATH=/app app python scripts/sync_catalogue.py
```

Run the quick demo with the memory limit in mind: the embedding script loads a second copy of the embedding model (about 1.1 GB).

**CPU or GPU:** without the GPU override, Ollama runs on CPU and each LLM call takes about 8 s (about 1 s on a GPU), so Compose sets a 25 s LLM timeout (`LLM_QUERY_UNDERSTANDING_TIMEOUT_SECONDS`). For a GPU, add the override (requires the NVIDIA Container Toolkit) and set the timeout back to 8: `docker compose -f docker-compose.yml -f docker-compose.gpu.yml up`. The first search after startup takes about a minute while the models load; repeating a query takes about 0.1 s.

**Verified:** the stack was run end to end on CPU (WSL2, 3.7 GB of RAM) with the 2,000-product sample: schema creation, ingest, embed, index, search with the LLM, outfit builder, CORS and the UI responding. **Not run in Compose:** the full 44k load, and the GPU override. Details: [`evals/reports/compose_verification.md`](evals/reports/compose_verification.md).

## API

Interactive documentation: **http://localhost:8000/docs**.

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/search` | Hybrid, vector or keyword search with filters, sorting and pages. 429 when rate limited, 503 when the database is down |
| `POST` | `/outfit` | Build an outfit for an occasion: a top, bottom, footwear and accessory, each with alternatives. Same 429 and 503 behaviour as `/search` |
| `GET` | `/products` | Browse available products: `page`, `page_size`, `category`, `gender`, `color`, `season`, `sort` |
| `GET` | `/products/facets` | Filter values in the catalogue (for dropdowns) |
| `POST` | `/feedback` | Thumbs up (1), down (-1) or remove (0) on one search result, with its context |
| `GET` | `/feedback/votes` | This browser's votes for a query (`client_id`, `query`) |
| `GET` | `/feedback/summary` | Totals, share of good matches, queries with the most bad results, recent votes |
| `GET` | `/health` | 200 when the database is reachable, 503 otherwise |

**Search feedback:** each search result has 👍/👎 buttons, and the **Feedback** page in the UI summarizes the votes.
- Each browser gets an anonymous ID (no accounts). Voting again on the same result for the same query replaces the vote.
- Each vote is stored with its context: position, search method, sort, filters and what the LLM understood. That makes it possible to see *why* a result was bad, and later to turn votes into evaluation labels.

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
| `OLLAMA_MODEL` | `gemma3:1b` | Ollama model name |
| `LLM_SKIP_NON_LATIN_QUERIES` | `false` | Skip the LLM for non-Latin-script queries; set `true` for English-only models such as TinyLlama |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | – / `gemini-3.5-flash-lite` | Only for `LLM_PROVIDER=gemini` |
| `LLM_QUERY_UNDERSTANDING_TIMEOUT_SECONDS` | `8.0` | LLM time limit per search before falling back |
| `LLM_QUERY_UNDERSTANDING_EVAL_TIMEOUT_SECONDS` | `15.0` | LLM time limit during evals |
| `LLM_CIRCUIT_FAILURE_THRESHOLD` | `3` | Consecutive LLM timeouts or connection errors before it's skipped |
| `LLM_CIRCUIT_COOLDOWN_SECONDS` | `30` | How long the LLM is skipped before checking whether it has recovered |
| `LLM_CACHE_TTL_SECONDS` / `LLM_CACHE_MAX_ENTRIES` | `600` / `1000` | Successful LLM results are cached per query, so paging, sorting and filter changes skip the LLM; `0` disables. Failures are never cached |
| `CATALOGUE_FACETS_CACHE_SECONDS` | `300` | How often filter values and product types are re-read from the database |
| `WARM_UP_MODELS_ON_STARTUP` | `true` | Load the models in the background at startup |
| `RATE_LIMIT_ENABLED` | `true` | Limit how often each client can search |
| `SEARCH_RATE_LIMIT_PER_MINUTE` | `30` | Sustained searches allowed per client per minute |
| `SEARCH_RATE_LIMIT_BURST` | `10` | Searches a client can make in a quick burst |
| `FEEDBACK_RATE_LIMIT_PER_MINUTE` / `FEEDBACK_RATE_LIMIT_BURST` | `120` / `30` | The same limits for `POST /feedback` |
| `TRUST_PROXY_HEADERS` | `false` | Read the client IP from `X-Forwarded-For`; enable only behind a reverse proxy that sets it |
| `LOG_LEVEL` | `INFO` | Logging level |
| `LOG_FORMAT` | `text` | `json` for one structured object per line, with `request_id` and fields such as `llm_latency_ms` |
| `CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Comma-separated browser origins allowed to call the API |
| `POSTGRES_PASSWORD` | – | Required by Docker Compose; also used in its `DATABASE_URL` |

Frontend: `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`).

## Testing

```bash
python3 -m pytest tests/                 # backend: ~420 tests, about 1–5 minutes
python3 -m pytest tests/ -m slow         # opt-in tests that load the real embedding model
cd frontend && npx vitest --run          # frontend: 70 tests
```

- The backend tests use a fake LLM and fake embeddings, so they don't need Ollama or a GPU.
- Integration tests use a separate `fashion_rec_test` database on the same PostgreSQL server, created automatically. Without PostgreSQL they're skipped.
- Stop the backend and frontend while running the full suite on a machine with little memory.

Current status: 418 passed and 2 known failures, both present before the latest changes:
- `test_llm_inferred_filter_is_applied_and_changes_results` expects LLM filters to restrict *all* results, but they were deliberately limited to keyword search.
- `test_e5_prefixes::test_batch_processing` is an embedding-model test that returns 4 results where it expects 3.

## Project structure

```
app/
  api/routes/          search.py (POST /search), outfit.py (POST /outfit), products.py (browse, facets)
  providers/           e5.py (embeddings), ollama_llm.py, llm.py (Gemini), fakes for tests
  services/
    search/            hybrid.py, vector_search.py, keyword_search.py, rank_fusion.py,
                       product_types.py, sorting.py
    outfit.py          outfit slots, per-slot search, one gender per outfit
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

- **Multilingual coverage:**
  - Language detection covers 10 languages. Other Latin-script languages (Dutch, Turkish and so on) may be read as English and searched untranslated.
  - Detection was measured on 263 labelled queries (260 correct). Known misreads: "beige sandals" (English read as German) and "veste en cuir marron" (French read as English).
  - **Translation was tested on 100 queries in 9 languages** (all but English): relevant@10 is 0.887 with Gemma against 0.492 with the LLM off, and 94 of 100 translations are correct on my review ([`evals/EXPLORATION.md`](evals/EXPLORATION.md#translation-and-search-quality-in-10-languages)). Weak spots: Gemma sometimes returns the query unchanged (German compound words), and literal wordings such as "sun protection glasses" can miss the catalogue's terms. Hindi is slightly worse with translation than without.
  - Gemma 3 1B still mistranslates some queries, e.g. "काली जूती" (black jutti) → "black kurta".
  - The LLM adds about 0.7 s per search on a GTX 1650 (0.9 s on the multilingual queries), and Ollama serves one request at a time, which caps throughput at about 1.4 searches/s for new queries ([`evals/SYSTEM_HEALTH.md`](evals/SYSTEM_HEALTH.md)). Repeated queries (paging, sorting, filter changes) are served from the LLM cache and skip that cost.
- **Evaluation:** the answer key favours vector search, and 80 queries can only show fairly large differences. An earlier, human-reviewed answer key (`ground_truth_v1.json`) no longer matches the database's product IDs.
- **The vector index may miss matches.** Vector Recall@20 is 0.71 against an answer key made of the embedding model's own top 20. Approximate HNSW search with the default `ef_search = 40` is the likely cause, but this isn't confirmed yet.
- **Outfit builder:**
  - Slots are fixed (no dresses, sarees or layers such as jackets), and picks are the best match per slot, so items aren't checked against each other for colour or style.
  - Quality depends on the embedding model and catalogue labels: a winter query can still return sandals, and the dataset has mislabelled items (a "Kids Boys" short filed under Men).
  - A category filter is ignored, since an outfit spans categories.
- **Data:** the dataset has no prices or usable images, so there's no price sorting and product cards show a color tile instead of a photo. `POST /search` returns one ranked list even for "outfit" queries; use the outfit builder for combinations.
- **Reliability:**
  - There's no overall request timeout.
  - The circuit breaker's state is kept per process, so with several API workers each one finds an outage separately.
- **Security and operations:**
  - No authentication or HTTPS.
  - Rate limits are per IP address, so people sharing one IP (an office network) share a limit. They're also per API process; several workers or servers would need a shared store such as Redis. The circuit breaker and the LLM result cache are per process for the same reason.
  - The default database password in `core/config.py` is a development one; Compose requires you to set your own.
  - No metrics, dashboards or alerts (logs are structured and carry request IDs).
- **Deployment:**
  - Compose was verified with a 2,000-product sample on CPU, not with the full catalogue or the GPU override. The catalogue load is a manual step after `up`.
  - There's no CI/CD and no production configuration.
- **Catalogue sync** runs from cron or by hand; there's no endpoint or event-driven trigger.
- **Feedback isn't used yet:** votes are collected and summarized, but they don't change ranking or feed the evaluation. The browser ID is anonymous and per device, so clearing site data starts fresh, and nothing stops someone voting many times from different browsers.

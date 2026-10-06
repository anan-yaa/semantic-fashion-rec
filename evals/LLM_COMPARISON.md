# LLM comparison: TinyLlama vs Qwen 2.5 1.5B vs Gemma 3 1B

**Question:** which small local LLM should do query understanding: extracting filters, and translating non-English queries into English, the catalogue's language?

**Constraint:** one 4 GB GPU (GTX 1650) and 3.7 GB of RAM under WSL, so only one LLM can be loaded at a time, next to the embedding model (~1.1 GB on the GPU).

All numbers are read from result files in [`reports/`](reports/); nothing is copied by hand. Each model was tested **alone on the GPU** (confirmed with `ollama ps`: 100% GPU) after unloading the others.

## Summary

| | TinyLlama 1.1B (before) | Qwen 2.5 1.5B | Gemma 3 1B, first run | **Gemma 3 1B, final (now in use)** |
|---|---|---|---|---|
| Multilingual relevant@10: **All 22 queries** | 0.69 | 0.71 | 0.74 | 0.85 |
| Multilingual relevant@10: Hindi (10) | 0.79 | 0.73 | 0.85 | 0.76 |
| Multilingual relevant@10: Spanish (8) | 0.54 | 0.66 | 0.60 | 0.89 |
| Multilingual relevant@10: French (4) | 0.72 | 0.75 | 0.72 | 1.00 |
| Main eval: hybrid NDCG@10, all 80 queries | 0.832 | 0.748 | 0.767 | 0.727 |
| ↳ 70 English queries | 0.808 | 0.736 | 0.770 | 0.794 |
| ↳ 10 Hindi queries *(not a fair measure, see finding 4)* | 1.000 | 0.826 | 0.745 | 0.258 |
| Main eval: hybrid MRR@10, all 80 *(includes the Hindi effect)* | 0.931 | 0.891 | 0.911 | 0.842 |
| Main eval: hybrid Recall@50, all 80 *(includes the Hindi effect)* | 0.704 | 0.709 | 0.706 | 0.621 |
| ↳ Recall@50, 70 English queries | 0.687 | 0.693 | 0.689 | 0.688 |
| Queries that used the LLM (main eval) | 70 of 80 | 80 of 80 | 80 of 80 | 80 of 80 |
| Hindi translations | skipped (can't translate) | mostly wrong | 10 of 10 right | 8 of 10 right |
| LLM time per query (median) | ~316 ms | ~547 ms | ~950 ms | ~908 ms |
| LLM size on GPU | 694 MB, 100% GPU | 1.2 GB, 100% GPU | 877 MB, 100% GPU | 877 MB, 100% GPU |
| Total GPU memory used (with embedding model) | 1943 MiB | 2372 MiB | 2114 MiB | 2114 MiB |

**What the tests measure:**
- **Multilingual relevant@10:** the share of the top 10 results matching a written rule for what the query asks for (product type, plus color and gender when stated). There are 22 Hindi, Spanish and French queries; see [`EXPLORATION.md`](EXPLORATION.md#3-multilingual-queries). This test doesn't depend on the embedding model.
- **Main eval:** the 80-query answer key from [`EVAL_RESULTS.md`](EVAL_RESULTS.md). Its labels come from the embedding model's own top results, so it favours plain vector search and penalises changes to the search text, including correct translations (see finding 4).

## Findings

1. **TinyLlama can't handle non-English queries.** It's essentially English-only, so Hindi queries skip it, and Spanish and French queries go to it untranslated. Multilingual search then relies entirely on the embedding model. That works for Hindi (0.79) but fails on many Spanish words, which it matches by spelling: "chaqueta" → "Red Chief" shoes.
2. **Qwen 2.5 1.5B invents Hindi translations:** red saree → "lilac", leather bag → "camera", jewellery for women → "strong shoes". It's ruled out.
3. **Gemma 3 1B translates Hindi correctly** (10 of 10): "red saree", "winter wool coat", "white shoes", "women jewelry". With Gemma, *translate first, then search* works: **0.84** on the multilingual test, versus 0.69 for TinyLlama and 0.56 for the dedicated translator opus-mt (which mistranslated Hindi).
4. **The main eval can't judge translation for Hindi.** For the 10 Hindi queries, the answer key *is* the embedding model's own top 20 for the Hindi text. Searching the Hindi text unchanged scores a perfect 1.000 by definition, and any translation, even a correct one, scores lower. The fair test of Hindi is the multilingual test above. The first Gemma run lowered the main eval (TinyLlama 0.832 → Gemma 0.767), for two reasons:
   - **Answer-key bias:** Gemma translated Hindi queries correctly ("सफेद जूते" → "white shoes"), keyword search then found genuinely white shoes, and the answer key, built from the embedding model's own picks for the Hindi text, counted them wrong.
   - **A real problem:** Gemma (and Qwen) shortened English queries, e.g. "durable sandals for everyday wear" → "durable sandals" (−0.93 on that query). This led to the second change below.
5. **Speed:** Gemma is about 3× slower per LLM call than TinyLlama, and Qwen about 1.7×. Ollama handles one request at a time, so under load search throughput drops roughly in proportion. That's an accepted trade of speed for accuracy.
6. **Reliability:** every model answered every query in valid JSON (0 fallbacks), and each fitted fully on the GPU next to the embedding model.

## Making Gemma 3 1B work: three runs

| Run | Multilingual, all 22 | Hindi | Spanish | French | English queries, main eval NDCG@10 | LLM time |
|---|---|---|---|---|---|---|
| TinyLlama (before, for reference) | 0.69 | 0.79 | 0.54 | 0.72 | 0.808 | ~316 ms |
| 1. Gemma, as TinyLlama was used (LLM keywords → keyword search) | 0.74 | 0.85 | 0.60 | 0.72 | 0.770 | ~950 ms |
| 2. + translate first, Gemma detects the language; English keeps its words | 0.65 | 0.76 | 0.47 | 0.72 | 0.794 | ~1020 ms |
| **3. + language detected by a library (final, in use)** | 0.85 | 0.76 | 0.89 | 1.00 | 0.794 | ~908 ms |

1. **First run:** Gemma's translations were good, but the app only used them for keyword search. It also shortened English queries ("durable sandals for everyday wear" → "durable sandals"), which lowered English quality.
2. **Second run, two changes:**
   - **Non-English queries searched in English:** both vector and keyword search use Gemma's English translation.
   - **English queries keep their own words:** keyword search uses the user's text, and the LLM only adds filters.

   The second change fixed English. The first failed for Spanish and French: asked to say whether a query was English, Gemma labelled every Spanish and French query as English and repeated it untranslated.
3. **Third run:** the language is detected by **lingua**, a small language-identification library (about 40 MB of RAM, 0.03 ms per query), limited to English, Spanish, French and Hindi. A query only counts as non-English when that's clearly more likely than English. On the eval queries it labels **all 77 English queries English and all 22 others correctly**. Gemma is then told the language ("Query (Spanish): …") and only translates. Result: Spanish and French translations are almost all right, e.g. "winter jacket for man", "red dress for woman", "black handbag".

## Decision

**Gemma 3 1B, with library language detection, translate-first for non-English queries, and English queries kept whole, is now the app's LLM.**

| | TinyLlama (before) | Gemma 3 1B (now) | Change |
|---|---|---|---|
| Multilingual relevant@10 | 0.69 | 0.85 | **+0.16** |
| English queries, NDCG@10 | 0.808 | 0.794 | -0.014 |
| LLM time per query | ~316 ms | ~908 ms | about 2.9× slower |

**Why:**
- Multilingual search improves a lot: Spanish 0.54 → 0.89, French 0.72 → 1.00.
- English stays essentially unchanged, level with search without any LLM (0.795).
- The extra ~0.6 s per search is an accepted trade of speed for accuracy.

**Remaining weak spots:**
- Two Hindi queries were mistranslated or didn't match: "काली जूती" (black jutti) → "black kurta", and "बच्चों के कपड़े" (children's clothes).
- "atuendo playero" → "playero outfit".

## Multilingual results in detail

| Setup | All | Hindi | Spanish | French |
|---|---|---|---|---|
| TinyLlama: app as it was (Hindi skips the LLM) | 0.69 | 0.79 | 0.54 | 0.72 |
| opus-mt translation, then search | 0.56 | 0.24 | 0.99 | 0.50 |
| Qwen: app (LLM keywords → keyword search only) | 0.71 | 0.73 | 0.66 | 0.75 |
| Qwen: its translation as the search query | 0.62 | 0.35 | 0.90 | 0.75 |
| Gemma: app (LLM keywords → keyword search only) | 0.74 | 0.85 | 0.60 | 0.72 |
| Gemma: its translation as the search query | 0.84 | 0.86 | 0.88 | 0.72 |
| **Gemma + changes** (app, translate-first for non-English) | 0.65 | 0.76 | 0.47 | 0.72 |

### Translations side by side

| Query | Meaning | opus-mt | Qwen 2.5 1.5B | Gemma 3 1B |
|---|---|---|---|---|
| नीली शर्ट | blue shirt | Blue Shirt | blue shorts | blue shirt |
| सर्दियों का ऊनी कोट | winter woollen coat | The Unicorn’s Unicorn | saree for boys | winter wool coat |
| काली जूती | black jutti (flat shoe) | black joker | kale green kurti | black shoes |
| महिलाओं के लिए गहने | jewellery for women | The Wounds of Women | strong shoes | women jewelry |
| पुरुषों के लिए घड़ी | watch for men | A Time for Men | clock for men | men's watch |
| लाल साड़ी | red saree | red joker | lilac | red saree |
| बच्चों के कपड़े | children's clothes | Children’s Picture Search | boys pants | children's clothes |
| सफेद जूते | white shoes | Whitechess-side | saffron jacket | white shoes |
| चमड़े का बैग | leather bag | the jack of clubs | camera | leather bag |
| गर्मियों के कपड़े | summer clothes | The clothes of the men of war | summer clothes | summer clothes |
| atuendo playero | beach outfit | playing a player | swimwear | playero outfit |
| vestido rojo para mujer | red dress for women | Red dress for women | red dress | red dress for woman |
| chaqueta de invierno para hombre | men's winter jacket | winter jacket for man | winter jacket | jacket winter man |
| zapatos deportivos | sports shoes | Sports shoes | sport shoes | sports shoes |
| reloj de mujer | women's watch | women's watches | woman's watch | woman watch |
| gafas de sol | sunglasses | sunglasses | sunglasses | sunglasses |
| camisa azul de hombre | men's blue shirt | man's blue shirt | blue shirt | blue shirt |
| bolso de cuero negro | black leather handbag | black leather bag | black leather bag | leather bolso |
| robe rouge pour femme | red dress for women | Red dress for women | red robe | robe rouge |
| chaussures de sport pour homme | men's sports shoes | sports shoes for man | sport shoes | shoes sport man |
| sac à main noir | black handbag | black joker | black handbag | sac à main noir |
| lunettes de soleil | sunglasses | Sunshines | sunglasses | sunglasses |

## How each model was tested

For each model in turn:
1. Unload every other model from Ollama.
2. Start the backend with that model (`OLLAMA_MODEL=…`).
3. Check `ollama ps` shows **100% GPU**; the run stops otherwise.
4. Run the multilingual test through the real API (`scripts/multilingual_experiment.py llm`).
5. Stop the backend, so two copies of the embedding model never compete for RAM.
6. Run the main eval (`scripts/run_eval.py --use-query-understanding`).

TinyLlama's numbers come from the system-health runs on the same code and hardware.

**Latency caveat:** TinyLlama's figure is the LLM stage's median over the 80-query eval mix, one request at a time. Qwen's and Gemma's are medians over the 22 multilingual queries, whose outputs are longer because they include translation. Treat them as approximate ratios rather than exact comparisons.

## Caveats

- **Small multilingual test:** 22 queries with hand-written relevance rules. It shows clear differences between models, not precise numbers.
- **Biased main eval:** the answer key favours vector search and penalises translation (finding 4), so main-eval drops for multilingual models overstate the real loss.
- **One machine:** a single small GPU. Larger models (e.g. Gemma 3 4B, 3.3 GB) would likely do better but don't fit next to the embedding model on a 4 GB card.

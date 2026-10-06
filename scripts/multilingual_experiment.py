#!/usr/bin/env python3
"""Does translating non-English queries to English first improve search?

For each non-English query, runs the real search API four ways:
    hybrid / vector-only  x  original text / opus-mt English translation
and scores each with "relevant@10": the share of the top 10 results that match
a hand-written rule for what the query asks for (product type, plus color and
gender when the query states them). This avoids the main answer key, whose
labels come from the embedding model being tested.

Runs in two phases so the translation model and the backend never need memory
at the same time (on a small machine, loading both can get the backend killed):

    # 1. backend stopped: translate and time
    PYTHONPATH=. python3 scripts/multilingual_experiment.py translate --translations evals/reports/multilingual_translations.json
    # 2. backend running on :8000: search both ways and score
    PYTHONPATH=. python3 scripts/multilingual_experiment.py search --translations evals/reports/multilingual_translations.json \\
        --output evals/reports/multilingual_experiment.json

A third phase uses the app's own LLM as the translator: it searches the
original query (the app's normal path) and reads the LLM's English keywords
from the response, then searches those keywords as the query:

    PYTHONPATH=. python3 scripts/multilingual_experiment.py llm --output evals/reports/multilingual_llm_<model>.json

Searches are spaced to stay under the search rate limit.
"""
import argparse
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

MODEL = "Helsinki-NLP/opus-mt-mul-en"

FOOTWEAR = {"Casual Shoes", "Sports Shoes", "Formal Shoes", "Flats", "Heels", "Sandals", "Sports Sandals",
            "Flip Flops", "Booties"}
JEWELLERY = {"Earrings", "Necklace and Chains", "Pendant", "Ring", "Bangle", "Bracelet", "Jewellery Set"}
BAGS = {"Handbags", "Clutches", "Laptop Bag", "Messenger Bag", "Duffel Bag", "Backpacks", "Rucksacks",
        "Trolley Bag", "Waist Pouch", "Mobile Pouch", "Tablet Sleeve"}
WARM_LAYERS = {"Jackets", "Rain Jacket", "Nehru Jackets", "Blazers", "Sweaters", "Sweatshirts", "Waistcoat", "Shrug"}
JACKETS = {"Jackets", "Rain Jacket", "Nehru Jackets", "Blazers"}
BEACHWEAR = {"Shorts", "Tshirts", "Tops", "Flip Flops", "Sandals", "Sunglasses", "Swimwear", "Caps", "Hat",
             "Dresses", "Shirts", "Capris", "Lounge Shorts"}
BLUE = {"Blue", "Navy Blue", "Turquoise Blue"}
RED = {"Red", "Maroon"}
KIDS = {"Boys", "Girls"}

# (query, language, meaning, rule): rule fields must all match. "types" -> article_type in set.
CASES = [
    ("नीली शर्ट", "hi", "blue shirt", {"types": {"Shirts", "Tshirts"}, "colors": BLUE}),
    ("सर्दियों का ऊनी कोट", "hi", "winter woollen coat", {"types": WARM_LAYERS}),
    ("काली जूती", "hi", "black jutti (flat shoe)", {"types": FOOTWEAR, "colors": {"Black"}}),
    ("महिलाओं के लिए गहने", "hi", "jewellery for women", {"types": JEWELLERY}),
    ("पुरुषों के लिए घड़ी", "hi", "watch for men", {"types": {"Watches"}, "genders": {"Men", "Unisex"}}),
    ("लाल साड़ी", "hi", "red saree", {"types": {"Sarees"}, "colors": RED}),
    ("बच्चों के कपड़े", "hi", "children's clothes", {"categories": {"Apparel"}, "genders": KIDS}),
    ("सफेद जूते", "hi", "white shoes", {"types": FOOTWEAR, "colors": {"White"}}),
    ("चमड़े का बैग", "hi", "leather bag", {"types": BAGS}),
    ("गर्मियों के कपड़े", "hi", "summer clothes", {"categories": {"Apparel"}, "seasons": {"Summer"}}),
    ("atuendo playero", "es", "beach outfit", {"types": BEACHWEAR, "seasons": {"Summer"}}),
    ("vestido rojo para mujer", "es", "red dress for women", {"types": {"Dresses"}, "colors": RED}),
    ("chaqueta de invierno para hombre", "es", "men's winter jacket", {"types": JACKETS, "genders": {"Men"}}),
    ("zapatos deportivos", "es", "sports shoes", {"types": {"Sports Shoes"}}),
    ("reloj de mujer", "es", "women's watch", {"types": {"Watches"}, "genders": {"Women", "Unisex"}}),
    ("gafas de sol", "es", "sunglasses", {"types": {"Sunglasses"}}),
    ("camisa azul de hombre", "es", "men's blue shirt", {"types": {"Shirts"}, "colors": BLUE, "genders": {"Men"}}),
    ("bolso de cuero negro", "es", "black leather handbag", {"types": BAGS, "colors": {"Black"}}),
    ("robe rouge pour femme", "fr", "red dress for women", {"types": {"Dresses"}, "colors": RED}),
    ("chaussures de sport pour homme", "fr", "men's sports shoes", {"types": {"Sports Shoes"}, "genders": {"Men"}}),
    ("sac à main noir", "fr", "black handbag", {"types": {"Handbags", "Clutches"}, "colors": {"Black"}}),
    ("lunettes de soleil", "fr", "sunglasses", {"types": {"Sunglasses"}}),
]

FIELDS = {"types": "article_type", "colors": "color", "genders": "gender", "categories": "category", "seasons": "season"}


def matches(product: dict, rule: dict) -> bool:
    return all(product.get(FIELDS[key]) in allowed for key, allowed in rule.items())


def load_translator():
    import torch
    from transformers import MarianMTModel, MarianTokenizer

    device = "cuda" if torch.cuda.is_available() else "cpu"
    tokenizer = MarianTokenizer.from_pretrained(MODEL)
    model = MarianMTModel.from_pretrained(MODEL).to(device).eval()

    def translate(text: str) -> str:
        with torch.no_grad():
            batch = tokenizer([text], return_tensors="pt").to(device)
            out = model.generate(**batch, max_new_tokens=40, num_beams=4)
        return tokenizer.decode(out[0], skip_special_tokens=True)

    return translate, device


def search(client: httpx.Client, query: str, method: str) -> list:
    time.sleep(2.1)  # stay under the 30/min search rate limit
    response = client.post("/search", json={"query": query, "method": method, "limit": 10})
    response.raise_for_status()
    return response.json()["products"]


def run_translate(path: str) -> None:
    translate, device = load_translator()
    translate("hola")  # warm-up
    out = {"translator": MODEL, "device": device, "translations": {}}
    for query, *_ in CASES:
        start = time.perf_counter()
        english = translate(query)
        out["translations"][query] = {"english": english, "ms": (time.perf_counter() - start) * 1000}
        print(f"{query!r:36} -> {english!r}  ({out['translations'][query]['ms']:.0f} ms)", flush=True)
    Path(path).write_text(json.dumps(out, indent=2, ensure_ascii=False))


def run_llm(base_url: str, output: str) -> int:
    """The app's LLM as translator: original query through the app, then its English keywords as the query."""
    rows = []
    with httpx.Client(base_url=base_url, timeout=120) as client:
        for query, lang, meaning, rule in CASES:
            time.sleep(2.1)
            response = client.post("/search", json={"query": query, "method": "hybrid", "limit": 10})
            response.raise_for_status()
            data = response.json()
            understanding = data.get("understanding") or {}
            english = (understanding.get("english_query") if understanding.get("translated") else None) or query
            row = {"query": query, "lang": lang, "meaning": meaning, "translation": english,
                   "llm_used": understanding.get("used_llm"), "llm_filters": understanding.get("inferred_filters"),
                   "llm_ms": parse_llm_ms(response.headers.get("server-timing")),
                   "app_hybrid": sum(matches(p, rule) for p in data["products"][:10]) / 10,
                   "app_hybrid_top3": [f"{p['name']} [{p['article_type']}]" for p in data["products"][:3]]}
            for method in ("hybrid", "vector"):
                products = search(client, english, method)
                row[f"{method}_translated"] = sum(matches(p, rule) for p in products[:10]) / 10
            rows.append(row)
            print(f"{query!r:36} -> {english!r:34} filters={row['llm_filters']}  app {row['app_hybrid']:.1f}"
                  f"  translated-hybrid {row['hybrid_translated']:.1f}  ({row['llm_ms']:.0f} ms)", flush=True)

    def mean(key, lang=None):
        values = [r[key] for r in rows if lang is None or r["lang"] == lang]
        return sum(values) / len(values)

    summary = {g: {k: mean(k, None if g == "all" else g) for k in ("app_hybrid", "hybrid_translated", "vector_translated")}
               for g in ("all", "hi", "es", "fr")}
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "translator": "app LLM (Ollama)",
              "llm_ms_median": statistics.median(r["llm_ms"] for r in rows),
              "summary_relevant_at_10": summary, "rows": rows}
    Path(output).write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(json.dumps(summary, indent=2))
    return 0


def parse_llm_ms(header) -> float:
    for part in (header or "").split(","):
        name, _, rest = part.strip().partition(";dur=")
        if name == "llm":
            return float(rest)
    return 0.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["translate", "search", "llm"])
    parser.add_argument("--translations")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--output")
    args = parser.parse_args()

    if args.phase == "translate":
        run_translate(args.translations)
        return 0

    if args.phase == "llm":
        return run_llm(args.base_url, args.output)

    saved = json.loads(Path(args.translations).read_text())
    device = saved["device"]
    rows = []
    with httpx.Client(base_url=args.base_url, timeout=120) as client:
        for query, lang, meaning, rule in CASES:
            english = saved["translations"][query]["english"]
            translate_ms = saved["translations"][query]["ms"]
            row = {"query": query, "lang": lang, "meaning": meaning, "translation": english,
                   "translate_ms": translate_ms}
            for method in ("hybrid", "vector"):
                for variant, text in (("original", query), ("translated", english)):
                    products = search(client, text, method)
                    row[f"{method}_{variant}"] = sum(matches(p, rule) for p in products[:10]) / 10
                    row[f"{method}_{variant}_top3"] = [f"{p['name']} [{p['article_type']}]" for p in products[:3]]
            rows.append(row)
            print(f"{query!r:36} -> {english!r:40} hybrid {row['hybrid_original']:.1f} -> {row['hybrid_translated']:.1f}"
                  f"   vector {row['vector_original']:.1f} -> {row['vector_translated']:.1f}   ({translate_ms:.0f} ms)",
                  flush=True)

    def mean(key, lang=None):
        values = [r[key] for r in rows if lang is None or r["lang"] == lang]
        return sum(values) / len(values)

    summary = {
        group: {key: mean(key, None if group == "all" else group)
                for key in ("hybrid_original", "hybrid_translated", "vector_original", "vector_translated")}
        for group in ("all", "hi", "es", "fr")
    }
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "translator": MODEL,
        "device": device,
        "translate_ms_median": statistics.median(r["translate_ms"] for r in rows),
        "summary_relevant_at_10": summary,
        "rows": rows,
    }
    Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

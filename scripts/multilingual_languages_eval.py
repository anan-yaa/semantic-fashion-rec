#!/usr/bin/env python3
"""How well does the app translate and search queries in 10 languages? (needs the backend running on :8000)

Covers the 22 Hindi/Spanish/French queries of scripts/multilingual_experiment.py plus 78 new German, Italian,
Portuguese, Arabic, Chinese and Russian queries. For each query it measures:
  - translation_ok: does the English translation Gemma produced contain the expected product, colour and gender
    words (EXPECT below, written before any run)? Strict: an acceptable paraphrase can be marked wrong.
  - relevant@10: share of the top 10 matching a hand-written rule (product type, colour, gender), searching the
    original query through the app (what a user gets), and searching Gemma's English translation.

Run it twice: against a backend with the LLM on, and (--baseline) against one started with
QUERY_UNDERSTANDING_ENABLED=false, to see what the multilingual embedding model manages without translation.
Start the backend with RATE_LIMIT_ENABLED=false and LLM_CACHE_TTL_SECONDS=0.

Usage:
    PYTHONPATH=. python3 scripts/multilingual_languages_eval.py --output evals/reports/multilingual_10_languages.json
    PYTHONPATH=. python3 scripts/multilingual_languages_eval.py --baseline --output evals/reports/multilingual_10_languages_baseline.json
"""
import argparse
import json
import re
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from multilingual_experiment import BAGS, BEACHWEAR, BLUE, CASES, JACKETS, RED, WARM_LAYERS, matches, parse_llm_ms

from app.services.query_understanding.language import detect_language

SANDALS = {"Sandals", "Sports Sandals", "Flip Flops"}
SNEAKERS = {"Casual Shoes", "Sports Shoes"}
BACKPACKS = {"Backpacks", "Rucksacks", "Laptop Bag", "Messenger Bag"}
SWEATERS = {"Sweaters", "Sweatshirts"}
MEN, WOMEN_ONLY = {"Men"}, {"Women"}
MEN_UNISEX, WOMEN_UNISEX = {"Men", "Unisex"}, {"Women", "Unisex"}

# Word groups for the translation check: every group must have at least one word (as a word prefix) in the English.
DRESS, W_RED, W_WOMEN, W_MEN = ["dress", "gown", "frock"], ["red"], ["women", "woman", "female", "ladies", "lady"], ["men", "man", "male"]
W_JACKET, W_COAT = ["jacket"], ["coat", "jacket", "overcoat"]
W_WOOL, W_WINTER, W_SUMMER = ["wool", "woollen", "woolen"], ["winter"], ["summer"]
W_RUN_SHOES, W_RUNNING = ["shoe", "sneaker", "trainer"], ["running", "run", "jogging"]
W_SUNGLASSES, W_SHIRT, W_BAG = ["sunglass", "sun glass"], ["shirt"], ["bag", "handbag", "purse"]
W_WATCH, W_BACKPACK = ["watch", "wristwatch"], ["backpack", "rucksack"]
W_BEACH = ["beach", "seaside"]

# (query, language code, meaning, relevance rule or None if the catalogue has no matching type, expected words)
NEW_CASES = [
    ("rotes Kleid für Frauen", "de", "red dress for women", {"types": {"Dresses"}, "colors": RED, "genders": WOMEN_ONLY}, [DRESS, W_RED, W_WOMEN]),
    ("schwarze Lederjacke für Herren", "de", "black leather jacket for men", {"types": JACKETS, "colors": {"Black"}, "genders": MEN}, [W_JACKET, ["leather"], ["black"], W_MEN]),
    ("bequeme Laufschuhe", "de", "comfortable running shoes", {"types": {"Sports Shoes"}}, [W_RUN_SHOES, W_RUNNING]),
    ("Wintermantel aus Wolle", "de", "wool winter coat", {"types": WARM_LAYERS}, [W_COAT, W_WOOL, W_WINTER]),
    ("Sonnenbrille für den Sommer", "de", "sunglasses for summer", {"types": {"Sunglasses"}}, [W_SUNGLASSES, W_SUMMER]),
    ("weißes Hemd für Männer", "de", "white shirt for men", {"types": {"Shirts"}, "colors": {"White"}, "genders": MEN}, [W_SHIRT, ["white"], W_MEN]),
    ("Handtasche aus Leder", "de", "leather handbag", {"types": BAGS}, [W_BAG, ["leather"]]),
    ("Outfit für den Strand im Sommer", "de", "outfit for the beach in summer", {"types": BEACHWEAR, "seasons": {"Summer"}}, [W_BEACH, W_SUMMER]),
    ("vestito rosso da donna", "it", "red dress for women", {"types": {"Dresses"}, "colors": RED, "genders": WOMEN_ONLY}, [DRESS, W_RED, W_WOMEN]),
    ("giacca di pelle nera da uomo", "it", "black leather jacket for men", {"types": JACKETS, "colors": {"Black"}, "genders": MEN}, [W_JACKET, ["leather"], ["black"], W_MEN]),
    ("scarpe da corsa comode", "it", "comfortable running shoes", {"types": {"Sports Shoes"}}, [W_RUN_SHOES, W_RUNNING]),
    ("cappotto invernale di lana", "it", "wool winter coat", {"types": WARM_LAYERS}, [W_COAT, W_WOOL, W_WINTER]),
    ("occhiali da sole per l'estate", "it", "sunglasses for summer", {"types": {"Sunglasses"}}, [W_SUNGLASSES, W_SUMMER]),
    ("camicia bianca da uomo", "it", "white shirt for men", {"types": {"Shirts"}, "colors": {"White"}, "genders": MEN}, [W_SHIRT, ["white"], W_MEN]),
    ("borsa di pelle marrone", "it", "brown leather bag", {"types": BAGS, "colors": {"Brown"}}, [W_BAG, ["leather"], ["brown"]]),
    ("abbigliamento per andare al mare", "it", "clothing to go to the beach", {"types": BEACHWEAR, "seasons": {"Summer"}}, [W_BEACH]),
    ("vestido vermelho feminino", "pt", "red dress for women", {"types": {"Dresses"}, "colors": RED, "genders": WOMEN_ONLY}, [DRESS, W_RED, W_WOMEN]),
    ("jaqueta de couro preta masculina", "pt", "black leather jacket for men", {"types": JACKETS, "colors": {"Black"}, "genders": MEN}, [W_JACKET, ["leather"], ["black"], W_MEN]),
    ("tênis de corrida confortável", "pt", "comfortable running shoes", {"types": {"Sports Shoes"}}, [W_RUN_SHOES, W_RUNNING]),
    ("casaco de lã para o inverno", "pt", "wool coat for winter", {"types": WARM_LAYERS}, [W_COAT, W_WOOL, W_WINTER]),
    ("óculos de sol para o verão", "pt", "sunglasses for summer", {"types": {"Sunglasses"}}, [W_SUNGLASSES, W_SUMMER]),
    ("camisa branca masculina", "pt", "white shirt for men", {"types": {"Shirts"}, "colors": {"White"}, "genders": MEN}, [W_SHIRT, ["white"], W_MEN]),
    ("bolsa de couro marrom", "pt", "brown leather bag", {"types": BAGS, "colors": {"Brown"}}, [W_BAG, ["leather"], ["brown"]]),
    ("roupa para ir à praia", "pt", "clothes to go to the beach", {"types": BEACHWEAR, "seasons": {"Summer"}}, [W_BEACH]),
    ("فستان أحمر للنساء", "ar", "red dress for women", {"types": {"Dresses"}, "colors": RED, "genders": WOMEN_ONLY}, [DRESS, W_RED, W_WOMEN]),
    ("جاكيت جلد أسود للرجال", "ar", "black leather jacket for men", {"types": JACKETS, "colors": {"Black"}, "genders": MEN}, [W_JACKET, ["leather"], ["black"], W_MEN]),
    ("حذاء رياضي مريح", "ar", "comfortable sports shoe", {"types": {"Sports Shoes"}}, [W_RUN_SHOES, ["sport", "athletic", "running"]]),
    ("معطف شتوي من الصوف", "ar", "wool winter coat", {"types": WARM_LAYERS}, [W_COAT, W_WOOL, W_WINTER]),
    ("نظارات شمسية للصيف", "ar", "sunglasses for summer", {"types": {"Sunglasses"}}, [W_SUNGLASSES, W_SUMMER]),
    ("قميص أبيض للرجال", "ar", "white shirt for men", {"types": {"Shirts"}, "colors": {"White"}, "genders": MEN}, [W_SHIRT, ["white"], W_MEN]),
    ("حقيبة يد جلدية بنية", "ar", "brown leather handbag", {"types": BAGS, "colors": {"Brown"}}, [W_BAG, ["leather"], ["brown"]]),
    ("ملابس للذهاب إلى الشاطئ", "ar", "clothes to go to the beach", {"types": BEACHWEAR, "seasons": {"Summer"}}, [W_BEACH]),
    ("女士红色连衣裙", "zh", "red dress for women", {"types": {"Dresses"}, "colors": RED, "genders": WOMEN_ONLY}, [DRESS, W_RED, W_WOMEN]),
    ("男士黑色皮夹克", "zh", "black leather jacket for men", {"types": JACKETS, "colors": {"Black"}, "genders": MEN}, [W_JACKET, ["leather"], ["black"], W_MEN]),
    ("舒适的跑步鞋", "zh", "comfortable running shoes", {"types": {"Sports Shoes"}}, [W_RUN_SHOES, W_RUNNING]),
    ("冬季羊毛大衣", "zh", "wool winter coat", {"types": WARM_LAYERS}, [W_COAT, W_WOOL, W_WINTER]),
    ("夏季太阳镜", "zh", "summer sunglasses", {"types": {"Sunglasses"}}, [W_SUNGLASSES, W_SUMMER]),
    ("男士白衬衫", "zh", "white shirt for men", {"types": {"Shirts"}, "colors": {"White"}, "genders": MEN}, [W_SHIRT, ["white"], W_MEN]),
    ("棕色皮革手提包", "zh", "brown leather handbag", {"types": BAGS, "colors": {"Brown"}}, [W_BAG, ["leather"], ["brown"]]),
    ("去海滩穿的衣服", "zh", "clothes to wear to the beach", {"types": BEACHWEAR, "seasons": {"Summer"}}, [W_BEACH]),
    ("красное платье для женщин", "ru", "red dress for women", {"types": {"Dresses"}, "colors": RED, "genders": WOMEN_ONLY}, [DRESS, W_RED, W_WOMEN]),
    ("чёрная кожаная куртка для мужчин", "ru", "black leather jacket for men", {"types": JACKETS, "colors": {"Black"}, "genders": MEN}, [W_JACKET, ["leather"], ["black"], W_MEN]),
    ("удобные кроссовки для бега", "ru", "comfortable running sneakers", {"types": {"Sports Shoes"}}, [W_RUN_SHOES, W_RUNNING]),
    ("зимнее шерстяное пальто", "ru", "winter wool coat", {"types": WARM_LAYERS}, [W_COAT, W_WOOL, W_WINTER]),
    ("солнцезащитные очки на лето", "ru", "sunglasses for summer", {"types": {"Sunglasses"}}, [W_SUNGLASSES, W_SUMMER]),
    ("белая рубашка мужская", "ru", "white shirt for men", {"types": {"Shirts"}, "colors": {"White"}, "genders": MEN}, [W_SHIRT, ["white"], W_MEN]),
    ("коричневая кожаная сумка", "ru", "brown leather bag", {"types": BAGS, "colors": {"Brown"}}, [W_BAG, ["leather"], ["brown"]]),
    ("одежда для пляжа", "ru", "beach clothes", {"types": BEACHWEAR, "seasons": {"Summer"}}, [W_BEACH]),
    # Held-out detection queries, reused here
    ("Kleid für eine Hochzeit", "de", "dress for a wedding", {"types": {"Dresses"}}, [DRESS, ["wedding"]]),
    ("warme Winterjacke für Damen", "de", "warm winter jacket for women", {"types": JACKETS, "genders": WOMEN_ONLY}, [W_COAT, W_WINTER, W_WOMEN]),
    ("Turnschuhe in Weiß", "de", "white sneakers", {"types": SNEAKERS, "colors": {"White"}}, [W_RUN_SHOES, ["white"]]),
    ("Armbanduhr für Herren", "de", "wristwatch for men", {"types": {"Watches"}, "genders": MEN_UNISEX}, [W_WATCH, W_MEN]),
    ("Rucksack für die Arbeit", "de", "backpack for work", {"types": BACKPACKS}, [W_BACKPACK, ["work", "office"]]),
    ("schicke Sandalen für den Urlaub", "de", "stylish sandals for vacation", {"types": SANDALS}, [["sandal"], ["vacation", "holiday", "trip"]]),
    ("abito elegante per una festa", "it", "elegant dress for a party", {"types": {"Dresses"}}, [DRESS, ["party"]]),
    ("stivali neri da donna", "it", "black boots for women", None, [["boot"], ["black"], W_WOMEN]),
    ("maglione di cotone blu", "it", "blue cotton sweater", {"types": SWEATERS, "colors": BLUE}, [["sweater", "jumper", "pullover", "sweatshirt"], ["blue"], ["cotton"]]),
    ("orologio da polso per uomo", "it", "wristwatch for men", {"types": {"Watches"}, "genders": MEN_UNISEX}, [W_WATCH, W_MEN]),
    ("zaino per l'università", "it", "backpack for university", {"types": BACKPACKS}, [W_BACKPACK, ["universit", "college"]]),
    ("sandali comodi per l'estate", "it", "comfortable sandals for summer", {"types": SANDALS}, [["sandal"], W_SUMMER]),
    ("vestido elegante para festa", "pt", "elegant dress for a party", {"types": {"Dresses"}}, [DRESS, ["party"]]),
    ("botas pretas femininas", "pt", "black boots for women", None, [["boot"], ["black"], W_WOMEN]),
    ("camiseta de algodão azul", "pt", "blue cotton t-shirt", {"types": {"Tshirts"}, "colors": BLUE}, [["t-shirt", "tshirt", "tee", "shirt"], ["blue"], ["cotton"]]),
    ("relógio de pulso masculino", "pt", "men's wristwatch", {"types": {"Watches"}, "genders": MEN_UNISEX}, [W_WATCH, W_MEN]),
    ("mochila para o trabalho", "pt", "backpack for work", {"types": BACKPACKS}, [W_BACKPACK, ["work", "office"]]),
    ("sandálias confortáveis para o verão", "pt", "comfortable sandals for summer", {"types": SANDALS}, [["sandal"], W_SUMMER]),
    ("حذاء كعب عالي أسود", "ar", "black high-heeled shoe", {"types": {"Heels"}, "colors": {"Black"}}, [["heel", "high"], ["black"]]),
    ("ثوب قطني للصيف", "ar", "cotton garment for summer", None, [["cotton"], W_SUMMER]),
    ("ساعة يد للرجال", "ar", "wristwatch for men", {"types": {"Watches"}, "genders": MEN_UNISEX}, [W_WATCH, W_MEN]),
    ("حقيبة ظهر للمدرسة", "ar", "school backpack", {"types": BACKPACKS}, [W_BACKPACK, ["school"]]),
    ("冬天穿的保暖外套", "zh", "warm coat for winter", {"types": WARM_LAYERS}, [W_COAT, W_WINTER]),
    ("女式高跟鞋", "zh", "women's high heels", {"types": {"Heels"}, "genders": WOMEN_ONLY}, [["heel"], W_WOMEN]),
    ("运动手表", "zh", "sports watch", {"types": {"Watches"}}, [W_WATCH, ["sport"]]),
    ("适合上班的衬衫", "zh", "shirt for work", {"types": {"Shirts"}}, [W_SHIRT, ["work", "office"]]),
    ("вечернее платье для свадьбы", "ru", "evening dress for a wedding", {"types": {"Dresses"}}, [DRESS, ["wedding"]]),
    ("кроссовки белого цвета", "ru", "white sneakers", {"types": SNEAKERS, "colors": {"White"}}, [W_RUN_SHOES, ["white"]]),
    ("наручные часы мужские", "ru", "men's wristwatch", {"types": {"Watches"}, "genders": MEN_UNISEX}, [W_WATCH, W_MEN]),
    ("рюкзак для работы", "ru", "backpack for work", {"types": BACKPACKS}, [W_BACKPACK, ["work", "office"]]),
]

# Expected words for the 22 existing cases, so every language is checked the same way.
EXISTING_EXPECT = {
    "नीली शर्ट": [W_SHIRT, ["blue"]],
    "सर्दियों का ऊनी कोट": [W_COAT, W_WOOL, W_WINTER],
    "काली जूती": [["shoe", "jutti", "juti", "mojari", "flat", "slipper"], ["black"]],
    "महिलाओं के लिए गहने": [["jewel"], W_WOMEN],
    "पुरुषों के लिए घड़ी": [W_WATCH, W_MEN],
    "लाल साड़ी": [["saree", "sari"], W_RED],
    "बच्चों के कपड़े": [["children", "child", "kids", "kid", "boys", "girls"], ["clothes", "clothing", "apparel", "wear", "garment"]],
    "सफेद जूते": [["shoe", "sneaker"], ["white"]],
    "चमड़े का बैग": [W_BAG, ["leather"]],
    "गर्मियों के कपड़े": [W_SUMMER, ["clothes", "clothing", "apparel", "wear", "garment", "outfit"]],
    "atuendo playero": [W_BEACH],
    "vestido rojo para mujer": [DRESS, W_RED, W_WOMEN],
    "chaqueta de invierno para hombre": [W_COAT, W_WINTER, W_MEN],
    "zapatos deportivos": [W_RUN_SHOES, ["sport", "athletic", "running"]],
    "reloj de mujer": [W_WATCH, W_WOMEN],
    "gafas de sol": [W_SUNGLASSES],
    "camisa azul de hombre": [W_SHIRT, ["blue"], W_MEN],
    "bolso de cuero negro": [W_BAG, ["leather"], ["black"]],
    "robe rouge pour femme": [DRESS, W_RED, W_WOMEN],
    "chaussures de sport pour homme": [W_RUN_SHOES, ["sport", "athletic"], W_MEN],
    "sac à main noir": [W_BAG, ["black"]],
    "lunettes de soleil": [W_SUNGLASSES],
}

ORDER = ["hi", "es", "fr", "de", "it", "pt", "ar", "zh", "ru"]
LANGUAGE_NAMES = {"hi": "Hindi", "es": "Spanish", "fr": "French", "de": "German", "it": "Italian", "pt": "Portuguese",
                  "ar": "Arabic", "zh": "Chinese", "ru": "Russian"}


def all_cases() -> list[tuple]:
    cases = [(q, lang, meaning, rule, EXISTING_EXPECT[q]) for q, lang, meaning, rule in CASES]
    return cases + NEW_CASES


def translation_ok(english: str, groups: list[list[str]]) -> bool:
    text = english.lower()
    return all(any(re.search(r"\b" + re.escape(word), text) for word in group) for group in groups)


def relevance(products: list[dict], rule: dict | None) -> float | None:
    return None if rule is None else sum(matches(p, rule) for p in products[:10]) / 10


def search(client: httpx.Client, query: str, method: str, delay: float) -> dict:
    time.sleep(delay)
    response = client.post("/search", json={"query": query, "method": method, "limit": 10})
    response.raise_for_status()
    return {"data": response.json(), "headers": response.headers}


def mean(values: list[float | None]) -> float | None:
    scored = [v for v in values if v is not None]
    return sum(scored) / len(scored) if scored else None


def run(base_url: str, baseline: bool, delay: float) -> list[dict]:
    rows = []
    with httpx.Client(base_url=base_url, timeout=180) as client:
        for query, lang, meaning, rule, expect in all_cases():
            app = search(client, query, "hybrid", delay)
            understanding = app["data"].get("understanding") or {}
            translated = bool(understanding.get("translated"))
            english = understanding.get("english_query") if translated else None
            row = {
                "query": query, "lang": lang, "meaning": meaning, "detected": detect_language(query),
                "scored": rule is not None,
                "llm_used": understanding.get("used_llm"), "translated": translated, "translation": english,
                "translation_ok": translation_ok(english, expect) if english else False,
                "llm_ms": parse_llm_ms(app["headers"].get("server-timing")),
                "app_hybrid": relevance(app["data"]["products"], rule),
                "app_top3": [f"{p['name']} [{p['article_type']}]" for p in app["data"]["products"][:3]],
            }
            if baseline:
                row["app_vector"] = relevance(search(client, query, "vector", delay)["data"]["products"], rule)
            elif english:
                for method in ("hybrid", "vector"):
                    row[f"{method}_translated"] = relevance(search(client, english, method, delay)["data"]["products"], rule)
            rows.append(row)
            shown = english or "(not translated)"
            print(f"[{lang}] {query!r:38} -> {shown!r:44} ok={row['translation_ok']!s:5} app={row['app_hybrid']}", flush=True)
    return rows


def summarize(rows: list[dict], baseline: bool) -> dict:
    summary = {}
    for group in ["all", *ORDER]:
        subset = [r for r in rows if group == "all" or r["lang"] == group]
        entry = {"queries": len(subset), "scored_queries": sum(r["scored"] for r in subset),
                 "app_hybrid": mean([r["app_hybrid"] for r in subset])}
        if baseline:
            entry["app_vector"] = mean([r["app_vector"] for r in subset])
        else:
            entry.update({
                "llm_used": sum(bool(r["llm_used"]) for r in subset),
                "translated": sum(r["translated"] for r in subset),
                "translation_ok": sum(r["translation_ok"] for r in subset),
                "hybrid_translated": mean([r.get("hybrid_translated") for r in subset]),
                "vector_translated": mean([r.get("vector_translated") for r in subset]),
                "llm_ms_median": statistics.median(r["llm_ms"] for r in subset),
            })
        summary[group] = entry
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Translation and search quality in 10 languages")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--baseline", action="store_true", help="Backend has the LLM off: search the original text only")
    parser.add_argument("--delay", type=float, default=0.2, help="Seconds between searches (rate limiting must be off)")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    rows = run(args.base_url, args.baseline, args.delay)
    summary = summarize(rows, args.baseline)
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "baseline_without_llm": args.baseline,
              "summary": summary, "rows": rows}
    Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

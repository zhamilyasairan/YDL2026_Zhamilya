"""
scrape_yessenov.py
==================
Scraper for https://yessenovfoundation.org/ — English, Russian, Kazakh.

Outputs:
  data/yessenov_en.txt      ← English pages
  data/yessenov_ru.txt      ← Russian pages
  data/yessenov_kk.txt      ← Kazakh pages
  data/yessenov_pages.json  ← all pages: {title, url, lang, lang_label, text}
  data/yessenov_text.txt    ← combined text (all languages)

Run:  python scrape_yessenov.py
Requirements: pip install requests beautifulsoup4
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import os
from urllib.parse import urljoin, urlparse

# ─── CONFIG ──────────────────────────────────────────────────────────────────

DOMAIN          = "yessenovfoundation.org"
DELAY_SECONDS   = 1.5
MAX_CRAWL_PAGES = 80    # limit for auto-discovered pages per language
OUTPUT_DIR      = "data"

LANGUAGES = [
    {"code": "en", "label": "English",  "prefix": "/en/"},
    {"code": "ru", "label": "Русский",  "prefix": "/ru/"},
    {"code": "kk", "label": "Қазақша", "prefix": "/kk/"},
]

# ─── ACTIVE PROGRAM SLUGS ────────────────────────────────────────────────────
# URLs containing any of these slugs are treated as priority regardless of the
# crawl-page cap. This ensures detailed program pages are never skipped.

ACTIVE_PROGRAM_SLUGS = [
    "research-internships",
    "programma-nauchnyh-stazhirovok",   # Russian slug for detailed RI pages
    "yessenov-scholarship",
    "stipendiya-im-akademika",          # Russian slug for scholarship editions
    "english-language-program",
    "yessenov-data-lab",
    "yessenov-launch-pad",
]


def is_active_program_url(url: str) -> bool:
    return any(slug in url for slug in ACTIVE_PROGRAM_SLUGS)


# ─── PRIORITY URL TEMPLATES ──────────────────────────────────────────────────
# Written in /en/ — replaced automatically to /ru/ and /kk/.

_PRIORITY_EN = [
    # ── About ──
    "https://yessenovfoundation.org/en/about-us/mission-and-reports/",
    "https://yessenovfoundation.org/en/about-us/galimzhan-yessenov/",
    "https://yessenovfoundation.org/en/about-us/programs/",
    "https://yessenovfoundation.org/en/about-us/the-board-of-trustees/",
    "https://yessenovfoundation.org/en/about-us/the-expert-board/",

    # ── S. Yessenov ──
    "https://yessenovfoundation.org/en/sh-esenov/biografiya/",
    "https://yessenovfoundation.org/en/sh-esenov/publikatsii-v-smi/",

    # ── Active Programs (overview pages) ──
    "https://yessenovfoundation.org/en/about-us/programs/science/research-internships/",
    "https://yessenovfoundation.org/en/about-us/programs/science/yessenov-scholarship/",
    "https://yessenovfoundation.org/en/about-us/programs/knowledge/english-language-program/",
    "https://yessenovfoundation.org/en/about-us/programs/resources/yessenov-data-lab/",
    "https://yessenovfoundation.org/en/about-us/programs/resources/yessenov-launch-pad/",

    # ── Research Internships — detailed pages with application requirements ──
    "https://yessenovfoundation.org/en/about-us/programs/science/research-internships/programma-nauchnyh-stazhirovok-v-laboratoriyah-mira-2026/",
    "https://yessenovfoundation.org/en/about-us/programs/science/research-internships/programma-nauchnyh-stazhirovok-v-laboratoriyah-mira-2025/",
    "https://yessenovfoundation.org/en/about-us/programs/science/research-internships/ri-2024/",
    "https://yessenovfoundation.org/en/about-us/programs/science/research-internships/ri-2023/",

    # ── Yessenov Scholarship — recent editions ──
    "https://yessenovfoundation.org/en/about-us/programs/science/yessenov-scholarship/%d2%9baz-stipendiya-im-akademika-sh-esenova-2026/",
    "https://yessenovfoundation.org/en/about-us/programs/science/yessenov-scholarship/stipendiya-im-akademika-sh-esenova-2025/",
    "https://yessenovfoundation.org/en/about-us/programs/science/yessenov-scholarship/stipendiya-im-akademika-sh-esenova-2024/",
    "https://yessenovfoundation.org/en/about-us/programs/science/yessenov-scholarship/shakhmardan-yessenov-scholarship-2023/",

    # ── Yessenov Data Lab — recent editions ──
    "https://yessenovfoundation.org/en/about-us/programs/resources/yessenov-data-lab/yessenov-data-lab-2026/",
    "https://yessenovfoundation.org/en/about-us/programs/resources/yessenov-data-lab/yessenov-data-lab-2025/",
    "https://yessenovfoundation.org/en/about-us/programs/resources/yessenov-data-lab/yessenov-data-lab-2024/",

    # ── Yessenov Launch Pad — recent editions ──
    "https://yessenovfoundation.org/en/about-us/programs/resources/yessenov-launch-pad/eng-yessenov-launch-pad-2025/",
    "https://yessenovfoundation.org/en/about-us/programs/resources/yessenov-launch-pad/yessenov-launch-pad-2023/",

    # ── English Language Program — recent editions ──
    "https://yessenovfoundation.org/en/about-us/programs/knowledge/english-language-program/grant-dlya-universitetov-obuchenie-anglijskomu-yazyku-studentov-i-prepodavatelej-2024-2025/",
    "https://yessenovfoundation.org/en/about-us/programs/knowledge/english-language-program/2022-2023/",

    # ── News & Stories ──
    "https://yessenovfoundation.org/en/category/novosti/novosti-fonda/",
    "https://yessenovfoundation.org/en/category/novosti/istorii-uspeha/",
    "https://yessenovfoundation.org/en/i-ih-ostalos-92/",
    "https://yessenovfoundation.org/en/kakoj-budet-ydl-2026/",
    "https://yessenovfoundation.org/en/andrej-kim/",
    "https://yessenovfoundation.org/en/dimash-davletov/",
]

# Extra URLs that have NO language prefix in the path (e.g. legacy redirects).
# Scraped once under Russian since that's what the site typically serves at /.
EXTRA_URLS_RU = [
    "https://yessenovfoundation.org/about-us/programs/science/research-internships/programma-nauchnyh-stazhirovok-v-laboratoriyah-mira-2026/",
]


def priority_urls_for(lang_prefix: str) -> list[str]:
    return [u.replace("/en/", lang_prefix) for u in _PRIORITY_EN]


# ─── BOILERPLATE LINES ───────────────────────────────────────────────────────

BOILERPLATE_LINES = {
    "our mission: to develop kazakhstan's intellectual potential",
    "stay in touch", "bookshelf", "menu",
    "1st floor, 7/75 shevchenko street, almaty, kazakhstan",
    "+7 (771) 759-59-44", "info@yessenovfoundation.org",
    "mission and reports", "founder", "programs",
    "the board of trustees", "the expert board",
    "biography", "publications in mass media", "multimedia",
    "newsfeed", "stories", "facebook", "youtube", "linkedin", "telegram",
    "қаз", "рус", "eng", "(рус)", "(eng)", "(қаз)",
    "миссия и отчёты", "попечительский совет", "экспертный совет",
    "биография", "публикации в сми", "мультимедиа",
    "наша миссия: развивать интеллектуальный потенциал казахстана",
    "оставайтесь на связи",
    "миссия және есептер", "қамқоршылар кеңесі", "сараптама кеңесі",
    "өмірбаяны", "бұқаралық ақпарат құралдарындағы жарияланымдар",
}


def clean_text(soup) -> str:
    for tag in soup(["script", "style", "nav", "footer", "header",
                     "noscript", "iframe", "img", "svg", "form"]):
        tag.decompose()
    raw = soup.get_text(separator="\n")
    lines = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.lower() in BOILERPLATE_LINES:
            continue
        if len(line) < 4:
            continue
        if line.startswith("http") and " " not in line:
            continue
        lines.append(line)
    return "\n".join(lines)


# ─── URL HELPERS ─────────────────────────────────────────────────────────────

def is_valid_url(url: str, lang_prefix: str) -> bool:
    parsed = urlparse(url)
    if DOMAIN not in parsed.netloc:
        return False
    # Accept both the standard lang-prefixed path AND no-prefix active-program URLs
    if not parsed.path.startswith(lang_prefix) and not is_active_program_url(url):
        return False
    skip_ext = (".jpg", ".jpeg", ".png", ".gif", ".pdf",
                ".mp4", ".mp3", ".zip", ".svg", ".webp")
    if any(parsed.path.lower().endswith(e) for e in skip_ext):
        return False
    if "page=" in parsed.query:
        return False
    return True


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    return parsed._replace(fragment="").geturl()


# ─── FETCHING ────────────────────────────────────────────────────────────────

def fetch_page(url: str, session: requests.Session):
    try:
        headers = {"User-Agent": "YessenovBot/1.0 (educational chatbot project)"}
        resp = session.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        print(f"  ⚠️  {url}: {e}")
        return None


def get_page_title(soup) -> str:
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)
    t = soup.find("title")
    if t:
        return t.get_text(strip=True).split(" — ")[0].strip()
    return "No title"


def extract_links(soup, current_url: str, lang_prefix: str) -> set[str]:
    links = set()
    for a in soup.find_all("a", href=True):
        full = normalize_url(urljoin(current_url, a["href"].strip()))
        if is_valid_url(full, lang_prefix):
            links.add(full)
    return links


# ─── SAVE HELPERS ────────────────────────────────────────────────────────────

def save_txt(pages: list[dict], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for page in pages:
            f.write(f"\n{'='*60}\n")
            f.write(f"PAGE: {page['title']}\n")
            f.write(f"URL:  {page['url']}\n")
            f.write(f"{'='*60}\n\n")
            f.write(page["text"])
            f.write("\n")


# ─── SCRAPE ONE LANGUAGE ─────────────────────────────────────────────────────

def scrape_language(lang: dict, session: requests.Session,
                    extra_urls: list[str] | None = None) -> list[dict]:
    code   = lang["code"]
    label  = lang["label"]
    prefix = lang["prefix"]
    base   = f"https://{DOMAIN}{prefix}"

    print(f"\n{'─'*60}")
    print(f"  Language: {label} ({code})  →  {base}")
    print(f"{'─'*60}")

    priority_set = set(normalize_url(u) for u in priority_urls_for(prefix))
    extra_set    = set(normalize_url(u) for u in (extra_urls or []))

    # Seed the queue: home page first, then priority, then extras
    to_visit = (
        [normalize_url(base)]
        + sorted(priority_set)
        + sorted(extra_set)
    )
    visited = set(to_visit)
    results = []
    crawl_count = 0  # counts only auto-discovered (non-priority, non-active-program) pages

    i = 0
    while i < len(to_visit):
        url = to_visit[i]
        i += 1

        # Decide whether this counts against the crawl cap
        is_priority       = url in priority_set or url == normalize_url(base)
        is_extra          = url in extra_set
        is_active_program = is_active_program_url(url)

        if not (is_priority or is_extra or is_active_program):
            if crawl_count >= MAX_CRAWL_PAGES:
                continue
            crawl_count += 1

        print(f"[{len(results)+1}] {url}")
        soup = fetch_page(url, session)
        if soup is None:
            time.sleep(DELAY_SECONDS)
            continue

        title = get_page_title(soup)
        text  = clean_text(soup)

        if len(text) < 100:
            print("       ↳ skipped (too little text)")
            time.sleep(DELAY_SECONDS)
            continue

        results.append({
            "title":      title,
            "url":        url,
            "lang":       code,
            "lang_label": label,
            "text":       text,
        })
        print(f"       ↳ ✅ '{title}' ({len(text)} chars)")

        new_links = extract_links(soup, url, prefix)
        added = 0
        for link in sorted(new_links):
            if link not in visited:
                visited.add(link)
                to_visit.append(link)
                added += 1
        if added:
            print(f"       ↳ 🔗 {added} new links")

        time.sleep(DELAY_SECONDS)

    print(f"\n  Done: {len(results)} pages — {label}")
    return results


# ─── MAIN ────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  Yessenov Foundation Scraper — EN / RU / KK")
    print("=" * 60)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    session     = requests.Session()
    all_results = []

    for lang in LANGUAGES:
        # Pass no-prefix extra URLs only to Russian (that's where they serve)
        extras = EXTRA_URLS_RU if lang["code"] == "ru" else []
        pages  = scrape_language(lang, session, extra_urls=extras)
        all_results.extend(pages)

        txt_path = os.path.join(OUTPUT_DIR, f"yessenov_{lang['code']}.txt")
        save_txt(pages, txt_path)
        print(f"  📄 {txt_path}  ({len(pages)} pages)")

    json_path = os.path.join(OUTPUT_DIR, "yessenov_pages.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\n  💾 JSON → {json_path}  ({len(all_results)} total)")

    legacy_path = os.path.join(OUTPUT_DIR, "yessenov_text.txt")
    save_txt(all_results, legacy_path)
    print(f"  📄 Legacy → {legacy_path}")

    print("\n" + "=" * 60)
    for lang in LANGUAGES:
        n = sum(1 for p in all_results if p["lang"] == lang["code"])
        c = sum(len(p["text"]) for p in all_results if p["lang"] == lang["code"])
        print(f"  {lang['label']:12} {n:3} pages  {c:>9,} chars")
    total_c = sum(len(p["text"]) for p in all_results)
    print(f"  {'TOTAL':12} {len(all_results):3} pages  {total_c:>9,} chars")


if __name__ == "__main__":
    main()

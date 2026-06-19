"""
scrape_yessenov.py
==================
Scraper for https://yessenovfoundation.org/en/
Goal: Collect detailed text data from all key pages for a Streamlit chatbot.

How it works:
1. Starts from a curated list of priority URLs (programs, about, news, stories)
2. Also crawls the site to discover more pages automatically
3. Cleans each page (removes menus, footers, scripts)
4. Saves results to data/yessenov_pages.json and data/yessenov_text.txt

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

BASE_URL = "https://yessenovfoundation.org/en/"
DOMAIN   = "yessenovfoundation.org"

# Delay between requests (be polite to the server)
DELAY_SECONDS = 1.5

# Maximum pages to scrape total (crawled pages; priority list is always included)
MAX_CRAWL_PAGES = 60

# Where to save results
OUTPUT_DIR  = "data"
JSON_FILE   = os.path.join(OUTPUT_DIR, "yessenov_pages.json")
TEXT_FILE   = os.path.join(OUTPUT_DIR, "yessenov_text.txt")

# ─── PRIORITY URLS ───────────────────────────────────────────────────────────
# These are always scraped first and in full, regardless of crawl limit.
# Covers every tab/section from the site map.

PRIORITY_URLS = [
    # ── About ──
    "https://yessenovfoundation.org/en/about-us/mission-and-reports/",
    "https://yessenovfoundation.org/en/about-us/galimzhan-yessenov/",
    "https://yessenovfoundation.org/en/about-us/programs/",
    "https://yessenovfoundation.org/en/about-us/the-board-of-trustees/",
    "https://yessenovfoundation.org/en/about-us/the-expert-board/",

    # ── S. Yessenov ──
    "https://yessenovfoundation.org/en/sh-esenov/biografiya/",
    "https://yessenovfoundation.org/en/sh-esenov/publikatsii-v-smi/",
    "https://yessenovfoundation.org/en/sh-esenov/multimedia/",

    # ── Active Programs ──
    "https://yessenovfoundation.org/en/about-us/programs/science/research-internships/",
    "https://yessenovfoundation.org/en/about-us/programs/science/yessenov-scholarship/",
    "https://yessenovfoundation.org/en/about-us/programs/knowledge/english-language-program/",
    "https://yessenovfoundation.org/en/about-us/programs/resources/yessenov-data-lab/",
    "https://yessenovfoundation.org/en/about-us/programs/knowledge/yessenov-lectures/find-your-way/",
    "https://yessenovfoundation.org/en/about-us/programs/resources/yessenov-launch-pad/",

    # ── YDL editions ──
    "https://yessenovfoundation.org/en/about-us/programs/resources/yessenov-data-lab/yessenov-data-lab-2026/",
    "https://yessenovfoundation.org/en/about-us/programs/resources/yessenov-data-lab/yessenov-data-lab-2025/",
    "https://yessenovfoundation.org/en/about-us/programs/resources/yessenov-data-lab/yessenov-data-lab-2024/",
    "https://yessenovfoundation.org/en/about-us/programs/resources/yessenov-data-lab/ydl-2023/",
    "https://yessenovfoundation.org/en/about-us/programs/resources/yessenov-data-lab/ydl-2020/",
    "https://yessenovfoundation.org/en/about-us/programs/resources/yessenov-data-lab/ydl-2019/",
    "https://yessenovfoundation.org/en/about-us/programs/resources/yessenov-data-lab/ydl-2018/",

    # ── Scholarship editions ──
    "https://yessenovfoundation.org/en/about-us/programs/science/yessenov-scholarship/%d2%9baz-stipendiya-im-akademika-sh-esenova-2026/",
    "https://yessenovfoundation.org/en/about-us/programs/science/yessenov-scholarship/stipendiya-im-akademika-sh-esenova-2025/",
    "https://yessenovfoundation.org/en/about-us/programs/science/yessenov-scholarship/stipendiya-im-akademika-sh-esenova-2024/",
    "https://yessenovfoundation.org/en/about-us/programs/science/yessenov-scholarship/shakhmardan-yessenov-scholarship-2023/",

    # ── Archive Programs (2013–2024) ──
    "https://yessenovfoundation.org/en/about-us/programs/science/orleu/",
    "https://yessenovfoundation.org/en/about-us/programs/knowledge/chess/",
    "https://yessenovfoundation.org/en/about-us/programs/knowledge/books/scientific-conferences/",
    "https://yessenovfoundation.org/en/about-us/programs/science/travel-grants/",
    "https://yessenovfoundation.org/en/about-us/programs/science/graduate-studies/",
    "https://yessenovfoundation.org/en/about-us/programs/knowledge/yessenov-lectures/yessenov-lectures/",
    "https://yessenovfoundation.org/en/about-us/programs/resources/internships-in-it-startups/",
    "https://yessenovfoundation.org/en/about-us/programs/knowledge/books/",

    # ── Partner Programs ──
    "https://yessenovfoundation.org/en/about-us/programs/resources/almaty-marathon/",

    # ── News & Stories ──
    "https://yessenovfoundation.org/en/category/novosti/novosti-fonda/",
    "https://yessenovfoundation.org/en/category/novosti/istorii-uspeha/",

    # ── Recent News Posts ──
    "https://yessenovfoundation.org/en/i-ih-ostalos-92/",
    "https://yessenovfoundation.org/en/kakoj-budet-ydl-2026/",
    "https://yessenovfoundation.org/en/naczionalnyj-otbor-na-ieso-2026-zavershyon/",

    # ── Success Stories ──
    "https://yessenovfoundation.org/en/andrej-kim/",
    "https://yessenovfoundation.org/en/dimash-davletov/",
    "https://yessenovfoundation.org/en/aliya-zhadyranova/",
    "https://yessenovfoundation.org/en/ernar-sakenov/",
]

# ─── TEXT CLEANING ────────────────────────────────────────────────────────────

# Repeated footer/menu lines to remove (exact matches after strip)
BOILERPLATE_LINES = {
    "our mission: to develop kazakhstan's intellectual potential",
    "stay in touch",
    "bookshelf",
    "menu",
    "қаз",
    "рус",
    "eng",
    "1st floor, 7/75 shevchenko street, almaty, kazakhstan",
    "+7 (771) 759-59-44",
    "info@yessenovfoundation.org",
    "mission and reports",
    "founder",
    "programs",
    "the board of trustees",
    "the expert board",
    "biography",
    "publications in mass media",
    "multimedia",
    "newsfeed",
    "stories",
    "facebook",
    "youtube",
    "linkedin",
    "telegram",
}

def clean_text(soup):
    """
    Extract clean readable text from a BeautifulSoup page object.
    Removes scripts, styles, nav, footer, and boilerplate lines.
    """
    # Remove unwanted HTML tags entirely
    for tag in soup(["script", "style", "nav", "footer", "header",
                      "noscript", "iframe", "img", "svg", "form"]):
        tag.decompose()

    # Get raw text
    raw = soup.get_text(separator="\n")

    # Clean line by line
    lines = []
    for line in raw.splitlines():
        line = line.strip()
        # Skip empty lines
        if not line:
            continue
        # Skip boilerplate (case-insensitive)
        if line.lower() in BOILERPLATE_LINES:
            continue
        # Skip very short lines (likely nav fragments)
        if len(line) < 4:
            continue
        # Skip lines that are just URLs
        if line.startswith("http") and " " not in line:
            continue
        lines.append(line)

    # Collapse multiple blank lines into one
    cleaned = "\n".join(lines)
    return cleaned


# ─── URL FILTERING ────────────────────────────────────────────────────────────

def is_valid_url(url):
    """
    Return True if the URL should be scraped:
    - Must be on yessenovfoundation.org
    - Must be under /en/ (English version)
    - Skip media files, pagination, anchors, external links
    """
    parsed = urlparse(url)

    if DOMAIN not in parsed.netloc:
        return False
    if not parsed.path.startswith("/en/"):
        return False
    # Skip media files
    skip_extensions = (".jpg", ".jpeg", ".png", ".gif", ".pdf",
                       ".mp4", ".mp3", ".zip", ".svg", ".webp")
    if any(parsed.path.lower().endswith(ext) for ext in skip_extensions):
        return False
    # Skip pagination (?page=2 etc)
    if "page=" in parsed.query:
        return False
    # Skip anchors-only
    if parsed.fragment and not parsed.path:
        return False
    return True


def normalize_url(url):
    """Remove fragments and trailing slashes inconsistencies."""
    parsed = urlparse(url)
    # Remove fragment
    clean = parsed._replace(fragment="")
    return clean.geturl()


# ─── SCRAPING ─────────────────────────────────────────────────────────────────

def fetch_page(url, session):
    """Fetch a URL and return BeautifulSoup object, or None on error."""
    try:
        headers = {"User-Agent": "YessenovBot/1.0 (educational chatbot project)"}
        response = session.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        return soup
    except Exception as e:
        print(f"  ⚠️  Error fetching {url}: {e}")
        return None


def get_page_title(soup):
    """Get the page title from <h1> or <title> tag."""
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)
    title = soup.find("title")
    if title:
        # Clean up " — Shakhmardan Yessenov Foundation" suffix
        t = title.get_text(strip=True)
        return t.split(" — ")[0].strip()
    return "No title"


def extract_links(soup, current_url):
    """Extract all internal English links from the page."""
    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        # Make absolute
        full_url = urljoin(current_url, href)
        full_url = normalize_url(full_url)
        if is_valid_url(full_url):
            links.add(full_url)
    return links


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  Yessenov Foundation Scraper")
    print("=" * 60)

    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Track all visited URLs and collected data
    visited   = set()
    to_visit  = []   # queue of URLs to scrape
    results   = []   # list of {title, url, text} dicts

    # Start with priority URLs (always scraped)
    print(f"\n📌 Priority URLs: {len(PRIORITY_URLS)}")
    for url in PRIORITY_URLS:
        url = normalize_url(url)
        if url not in visited:
            to_visit.append(url)
            visited.add(url)

    # Also seed crawler from home page
    home = normalize_url(BASE_URL)
    if home not in visited:
        to_visit.insert(0, home)
        visited.add(home)

    session = requests.Session()
    crawl_count = 0   # counts only auto-discovered pages (not priority)

    print(f"🚀 Starting scrape...\n")

    i = 0
    while i < len(to_visit):
        url = to_visit[i]
        i += 1

        # Check if this is a priority URL or auto-discovered
        is_priority = url in [normalize_url(u) for u in PRIORITY_URLS] or url == home

        # Enforce crawl limit only for auto-discovered pages
        if not is_priority:
            if crawl_count >= MAX_CRAWL_PAGES:
                continue
            crawl_count += 1

        print(f"[{len(results)+1}] Scraping: {url}")

        soup = fetch_page(url, session)
        if soup is None:
            time.sleep(DELAY_SECONDS)
            continue

        # Extract title and clean text
        title = get_page_title(soup)
        text  = clean_text(soup)

        # Skip pages with almost no content
        if len(text) < 100:
            print(f"       ↳ Skipped (too little text)")
            time.sleep(DELAY_SECONDS)
            continue

        results.append({
            "title": title,
            "url":   url,
            "text":  text
        })
        print(f"       ↳ ✅ '{title}' ({len(text)} chars)")

        # Discover new links and add to queue
        new_links = extract_links(soup, url)
        added = 0
        for link in sorted(new_links):  # sorted for reproducibility
            if link not in visited:
                visited.add(link)
                to_visit.append(link)
                added += 1

        if added:
            print(f"       ↳ 🔗 Found {added} new links")

        # Polite delay
        time.sleep(DELAY_SECONDS)

    # ─── SAVE RESULTS ─────────────────────────────────────────────────────────

    print("\n" + "=" * 60)
    print(f"  Scraping complete! Total pages: {len(results)}")
    print("=" * 60)

    # Save JSON
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n💾 JSON saved → {JSON_FILE}")

    # Save plain text (all pages concatenated, good for TF-IDF / embeddings)
    with open(TEXT_FILE, "w", encoding="utf-8") as f:
        for page in results:
            f.write(f"\n{'='*60}\n")
            f.write(f"PAGE: {page['title']}\n")
            f.write(f"URL:  {page['url']}\n")
            f.write(f"{'='*60}\n\n")
            f.write(page["text"])
            f.write("\n")
    print(f"📄 Text saved  → {TEXT_FILE}")

    # Print summary table
    print("\n📊 Pages scraped:")
    print(f"  {'#':<4} {'Title':<50} {'Chars':>6}")
    print(f"  {'-'*4} {'-'*50} {'-'*6}")
    for idx, page in enumerate(results, 1):
        title_short = page["title"][:48] + ".." if len(page["title"]) > 50 else page["title"]
        print(f"  {idx:<4} {title_short:<50} {len(page['text']):>6}")

    total_chars = sum(len(p["text"]) for p in results)
    print(f"\n  Total text collected: {total_chars:,} characters")
    print(f"  Saved to: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
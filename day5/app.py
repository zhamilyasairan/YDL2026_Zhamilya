import os
import re
import requests
import streamlit as st
from dotenv import load_dotenv

# ── API keys — loaded from .env, never hardcoded ──────────────────────────────
load_dotenv()
LLM_MODEL   = os.getenv("LLM_MODEL")
LLM_URL     = os.getenv("LLM_URL")
LLM_API_KEY = os.getenv("LLM_API_KEY")

# ── Language detection ────────────────────────────────────────────────────────
try:
    from langdetect import detect, LangDetectException, DetectorFactory
    DetectorFactory.seed = 0
    LANGDETECT_OK = True
except ImportError:
    LANGDETECT_OK = False

# ── Data files ────────────────────────────────────────────────────────────────
DATA_FILES = {
    "en": ["data/yessenov_en.txt", "data/yessenov_text.txt"],
    "ru": ["data/yessenov_ru.txt"],
    "kk": ["data/yessenov_kk.txt"],
}

LANG_MAP    = {"en": "en", "ru": "ru", "kk": "kk", "uk": "ru", "be": "ru"}
LANG_LABELS = {"en": "English", "ru": "Русский", "kk": "Қазақша"}

# ── Multilingual UI strings ───────────────────────────────────────────────────
CLARIFY_TEXT = {
    "en": "Which program are you interested in?",
    "ru": "Какая именно программа вас интересует?",
    "kk": "Қай бағдарлама сізді қызықтырады?",
}
SELECT_LABEL   = {"en": "Select a program:",  "ru": "Выберите программу:",      "kk": "Бағдарламаны таңдаңыз:"}
CONTINUE_LABEL = {"en": "Continue →",         "ru": "Продолжить →",             "kk": "Жалғастыру →"}
NO_DATA_TEXT   = {
    "en": "I don't have this information.",
    "ru": "У меня нет такой информации.",
    "kk": "Менде бұл ақпарат жоқ.",
}

# ── Active programs ───────────────────────────────────────────────────────────
# Only these 5 programs appear in the clarification selectbox.
# "url_slug"    → used to filter pages to those belonging to this program
# "detail_slug" → additional slug that marks a *detailed* child page (gets bonus
#                 score so specific pages rank above general overview pages)
# "aliases"     → search terms appended to the query; covers translated names
#                 so Russian/Kazakh pages score correctly
PROGRAMS = [
    {
        "name":        "Yessenov Scholarship",
        "url_slug":    "yessenov-scholarship",
        "detail_slug": "stipendiya-im-akademika",
        "aliases": [
            "yessenov scholarship", "scholarship",
            "стипендия", "есенов стипендия", "академика есенова",
            "шәкіртақы", "есенов шәкіртақысы",
        ],
    },
    {
        "name":        "Research Internships",
        "url_slug":    "research-internships",
        "detail_slug": "programma-nauchnyh-stazhirovok",
        "aliases": [
            "Research Internships", "research internship", "research internships",
            "научные стажировки", "научных стажировок",
            "программа научных стажировок", "лабораториях мира",
            "стажировка", "стажировки",
            "programma-nauchnyh-stazhirovok", "research-internships",
            "ғылыми тағылымдама", "зертханаларда",
        ],
    },
    {
        "name":        "English Language Program",
        "url_slug":    "english-language-program",
        "detail_slug": "grant-dlya-universitetov",
        "aliases": [
            "english language", "english program",
            "английский язык", "английского языка",
            "ағылшын тілі", "ағылшын тілін",
        ],
    },
    {
        "name":        "Yessenov Data Lab",
        "url_slug":    "yessenov-data-lab",
        "detail_slug": "ydl-202",
        "aliases": [
            "data lab", "ydl", "yessenov data lab",
            "дата лаб", "машинное обучение", "machine learning",
            "деректер зертханасы",
        ],
    },
    {
        "name":        "Yessenov Launch Pad",
        "url_slug":    "yessenov-launch-pad",
        "detail_slug": "launch-pad-202",
        "aliases": [
            "launch pad", "yessenov launch pad",
            "стартап", "startup", "стартаптар",
        ],
    },
]

PROGRAM_NAMES    = [p["name"]        for p in PROGRAMS]
PROGRAM_SLUG     = {p["name"]: p["url_slug"]    for p in PROGRAMS}
PROGRAM_DETAIL   = {p["name"]: p["detail_slug"] for p in PROGRAMS}
PROGRAM_ALIASES  = {p["name"]: p["aliases"]     for p in PROGRAMS}

# ── Ambiguity detection keywords ──────────────────────────────────────────────
# If the question contains any of these AND does not name a specific program,
# ask the user to clarify which program they mean.
AMBIGUOUS_KEYWORDS = [
    # English
    "document", "apply", "application", "require", "requirement",
    "eligib", "criteria", "criterion", "deadline", "submit", "submission",
    "who can", "how to", "how do", "participate", "enroll", "register",
    # Russian
    "документ", "подать", "подача", "заявк", "требован",
    "критери", "дедлайн", "срок", "кто может", "как участв", "участвовать",
    "записаться", "зарегистрироваться",
    # Kazakh
    "құжат", "өтінім", "талап", "мерзім", "қалай", "кім", "қатысу", "тіркел",
]

# Built automatically from all aliases — if the question mentions any of these
# the question is specific enough and no clarification is needed.
PROGRAM_DETECT_KEYWORDS = (
    [alias.lower() for prog in PROGRAMS for alias in prog["aliases"]]
    + [p["name"].lower() for p in PROGRAMS]
)

# ── Stop words ────────────────────────────────────────────────────────────────
STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "what", "who", "how", "when", "where", "which", "do", "does",
    "i", "me", "my", "you", "your", "it", "its", "this", "that",
    "and", "or", "of", "to", "in", "for", "on", "with", "about", "tell",
    "и", "в", "на", "с", "по", "что", "как", "не", "это", "из",
    "за", "от", "до", "для", "но", "же", "о", "я", "вы", "он", "та",
    "мне", "расскажи", "можете", "пожалуйста",
    "бұл", "және", "не", "ол", "да", "де", "үшін", "бар", "жоқ",
}

# ── Regex for parsing scraped txt files ───────────────────────────────────────
_SEP = re.compile(r"={20,}\nPAGE:\s*(.+?)\nURL:\s*(\S+)\n={20,}", re.MULTILINE)

# ── LLM system prompt ─────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are an assistant for the Shakhmardan Yessenov Foundation.

STRICT RULES — no exceptions:
1. Answer ONLY using the SOURCE sections provided. Never use your own training knowledge.
2. Do NOT invent program names, subcategories, deadlines, amounts, or requirements.
3. Do NOT add structure (bullet points, sections) that is not in the sources.
4. At the end of every answer, cite which source(s) you used: page title and URL.
5. If the answer is not in the sources, respond:
   English → "I don't have this information."
   Russian → "У меня нет такой информации."
   Kazakh  → "Менде бұл ақпарат жоқ."
6. Always reply in the same language the user wrote in."""


# ─────────────────────────────────────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def detect_lang(text: str) -> str:
    if not LANGDETECT_OK:
        return "en"
    try:
        return LANG_MAP.get(detect(text), "en")
    except LangDetectException:
        return "en"


@st.cache_data
def load_pages(lang: str) -> list[dict]:
    """Parse the language-specific txt file into [{title, url, text}]."""
    path = next((p for p in DATA_FILES.get(lang, []) if os.path.exists(p)), None)
    if path is None:
        return []
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    pages = []
    matches = list(_SEP.finditer(content))
    for i, match in enumerate(matches):
        title = match.group(1).strip()
        url   = match.group(2).strip()
        start = match.end()
        end   = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        text  = content[start:end].strip()
        if text:
            pages.append({"title": title, "url": url, "text": text})
    return pages


def detect_ambiguous_question(question: str) -> bool:
    """True if the question asks about requirements/documents without naming a program."""
    q = question.lower()
    for kw in PROGRAM_DETECT_KEYWORDS:
        if kw in q:
            return False
    for kw in AMBIGUOUS_KEYWORDS:
        if kw in q:
            return True
    return False


def filter_by_program(pages: list[dict], url_slug: str | None) -> list[dict]:
    """Keep only pages whose URL contains the program slug. Falls back to all pages."""
    if not url_slug:
        return pages
    filtered = [p for p in pages if url_slug in p["url"]]
    return filtered if filtered else pages


# ── Year detection helpers ─────────────────────────────────────────────────────
# Valid year range: 2013 (foundation year) – 2030.
_YEAR_RE = re.compile(r'\b(201[3-9]|202[0-9]|2030)\b')


def detect_year(question: str) -> int | None:
    """Return a 4-digit year if the user explicitly mentioned one, else None."""
    match = _YEAR_RE.search(question)
    return int(match.group()) if match else None


def extract_year_from_page(page: dict) -> int | None:
    """
    Find the most prominent year for a page.
    Looks in URL first (most reliable), then title, then first 300 chars of text.
    Returns the highest year found, or None for general/overview pages.
    """
    years = _YEAR_RE.findall(page["url"] + " " + page["title"])
    if not years:
        years = _YEAR_RE.findall(page["text"][:300])
    return max(int(y) for y in years) if years else None


def select_year_filtered_pages(
    pages: list[dict],
    asked_year: int | None,
) -> tuple[list[dict], int | None, str]:
    """
    Filter program pages so the LLM only sees one year's content.

    Rules:
    - Pages with no year in URL/title (overview pages) are ALWAYS included.
    - If the user asked about a specific year: keep only that year's pages.
    - If no year in question: keep only the latest year's pages.

    Returns (filtered_pages, selected_year, mode_label).
    mode_label is "latest" or "exact year" (shown in debug panel).
    """
    tagged       = [(page, extract_year_from_page(page)) for page in pages]
    overview     = [p for p, y in tagged if y is None]   # always keep
    with_year    = [(p, y) for p, y in tagged if y is not None]

    if not with_year:
        # No year-tagged pages — return everything unchanged
        return pages, None, "latest (no dated pages)"

    all_years = [y for _, y in with_year]

    if asked_year is not None:
        year_pages = [p for p, y in with_year if y == asked_year]
        if year_pages:
            return overview + year_pages, asked_year, "exact year"
        # Asked year has no pages — fall back to latest so the bot can say "not found"
        latest = max(all_years)
        return overview + [p for p, y in with_year if y == latest], latest, "exact year (not found, using latest)"

    # No year asked → use the latest year only
    latest = max(all_years)
    return overview + [p for p, y in with_year if y == latest], latest, "latest"


def score_and_retrieve(
    pages: list[dict],
    query: str,
    top_k: int = 5,
    detail_slug: str | None = None,
) -> tuple[list[dict], list[dict]]:
    """
    Score pages by keyword overlap and return (top_k_pages, all_scored).

    Scoring weights:
      - query word in page body  → +1 per word
      - query word in page title → +3 per word
      - page URL contains detail_slug (specific child page) → +5 bonus
        (so "programma-nauchnyh-stazhirovok-2026" outranks the overview page)

    Returns:
      selected  — top_k pages to use as LLM context
      all_scored — all pages with scores, for the debug panel
    """
    words = set(re.findall(r"\w+", query.lower())) - STOPWORDS

    scored = []
    for page in pages:
        if words:
            score  = sum(1 for w in words if w in page["text"].lower())
            score += sum(3 for w in words if w in page["title"].lower())
        else:
            score = 0

        # Bonus: detailed/specific pages rank above generic overview pages
        if detail_slug and detail_slug in page["url"]:
            score += 5

        scored.append((score, page))

    scored.sort(key=lambda x: -x[0])
    relevant = [(s, p) for s, p in scored if s > 0]
    top = (relevant or scored)[:top_k]
    return [p for _, p in top], scored


def build_context(pages: list[dict], max_chars: int = 1400) -> str:
    """Format pages as a clearly labelled context block for the LLM."""
    parts = []
    for page in pages:
        text = page["text"]
        if len(text) > max_chars:
            text = text[:max_chars] + "\n[…]"
        parts.append(
            f"=== SOURCE: {page['title']} ===\n"
            f"URL: {page['url']}\n\n"
            f"{text}"
        )
    return "\n\n---\n\n".join(parts)


def ask_llm(question: str, context: str) -> str:
    """Send question + context to the LLM and return the answer text."""
    url = LLM_URL.rstrip("/")
    if not url.endswith("/chat/completions"):
        url += "/chat/completions"
    resp = requests.post(
        url,
        headers={"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": LLM_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": f"SOURCES:\n\n{context}\n\n---\n\nQUESTION: {question}"},
            ],
            "temperature": 0.1,
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def answer_question(
    question: str,
    lang: str,
    program_name: str | None = None,
) -> str:
    """
    Full pipeline:
      1. Load language-specific pages
      2. Filter to program pages (if program selected)
      3. Build search query (question + program name + aliases)
      4. Score and retrieve top-5 pages
      5. Call LLM
      6. Store debug info in st.session_state["last_debug"]
    """
    pages = load_pages(lang)
    if not pages:
        return (
            f"Data file for **{LANG_LABELS[lang]}** is not available yet. "
            f"Run the scraper first.\n\n{NO_DATA_TEXT[lang]}"
        )

    # Narrow to program pages first
    url_slug    = PROGRAM_SLUG.get(program_name)         if program_name else None
    detail_slug = PROGRAM_DETAIL.get(program_name)       if program_name else None
    aliases     = PROGRAM_ALIASES.get(program_name, [])  if program_name else []

    if url_slug:
        pages = filter_by_program(pages, url_slug)

    # Year filtering — keeps the LLM from mixing old and new edition details
    asked_year = detect_year(question)
    if program_name:
        pages, selected_year, year_mode = select_year_filtered_pages(pages, asked_year)
    else:
        selected_year, year_mode = None, "—"

    # Build query: original question + program name + all aliases
    # Aliases are essential for Russian/Kazakh pages that use translated program names
    alias_str = " ".join(aliases)
    query = f"{program_name or ''} {alias_str} {question}".strip()

    selected_pages, all_scored = score_and_retrieve(
        pages, query, top_k=5, detail_slug=detail_slug
    )
    context = build_context(selected_pages)

    # Save debug info for the sidebar
    st.session_state["last_debug"] = {
        "lang":           lang,
        "program":        program_name or "—",
        "question":       question,
        "asked_year":     asked_year,
        "selected_year":  selected_year,
        "year_mode":      year_mode,
        "query":          query,
        "aliases":        aliases,
        "selected_titles": [p["title"] for p in selected_pages],
        "selected_urls":   [p["url"]   for p in selected_pages],
        "all_scores":     [(p["title"][:60], s) for s, p in all_scored[:15]],
    }

    try:
        return ask_llm(question, context)
    except Exception as e:
        return f"Error calling the model: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# STREAMLIT UI
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(page_title="Yessenov Foundation Assistant", page_icon="🤖")
st.title("Yessenov Foundation Assistant")

# ── Startup checks ────────────────────────────────────────────────────────────
if not LLM_API_KEY or not LLM_URL or not LLM_MODEL:
    st.error("Missing LLM_API_KEY, LLM_URL, or LLM_MODEL in .env")
    st.stop()

if not LANGDETECT_OK:
    st.warning("langdetect not installed — defaulting to English. Run: pip install langdetect")

# ── Debug sidebar ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Settings")
    show_debug = st.checkbox("Show debug info", value=False)

    if show_debug and "last_debug" in st.session_state:
        d = st.session_state["last_debug"]
        st.divider()
        st.subheader("Last request — debug")
        st.write(f"**Detected language:** {LANG_LABELS.get(d['lang'], d['lang'])}")
        st.write(f"**Selected program:** {d['program']}")
        st.write(f"**Original question:** {d['question']}")
        st.write(f"**Year in question:** {d['asked_year'] or '—'}")
        st.write(f"**Year used for filtering:** {d['selected_year'] or '—'}")
        st.write(f"**Search mode:** {d['year_mode']}")
        st.write("**Search query sent to scorer:**")
        st.code(d["query"], language=None)
        st.write(f"**Matched aliases:** {d['aliases'] or '—'}")
        st.write("**Pages sent to LLM (top 5):**")
        for title, url in zip(d["selected_titles"], d["selected_urls"]):
            st.markdown(f"- [{title}]({url})")
        st.write("**All page scores (top 15):**")
        for title, score in d["all_scores"]:
            st.write(f"  `{score:4}` {title}")

# ── Session state ─────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

# ── STEP 1: Render chat history ───────────────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "user" and "lang" in msg:
            st.caption(f"Detected language: {LANG_LABELS[msg['lang']]}")
        st.write(msg["content"])

# ── STEP 2: Clarification widget ──────────────────────────────────────────────
# Appears when the bot asked "which program?" and is waiting for the user to pick.
if st.session_state.get("pending_question"):
    lang = st.session_state["pending_lang"]

    with st.form("clarify_form"):
        st.write(f"**{SELECT_LABEL[lang]}**")
        selected_program = st.selectbox(
            label="program",
            options=PROGRAM_NAMES,
            label_visibility="collapsed",
        )
        submitted = st.form_submit_button(CONTINUE_LABEL[lang], use_container_width=True)

    if submitted:
        original_q = st.session_state["pending_question"]
        with st.spinner("Thinking..."):
            answer = answer_question(original_q, lang, selected_program)

        st.session_state.messages.append({
            "role": "user",
            "content": f"*(Selected program: **{selected_program}**)*",
        })
        st.session_state.messages.append({"role": "assistant", "content": answer})
        del st.session_state["pending_question"]
        del st.session_state["pending_lang"]
        st.rerun()

# ── STEP 3: Chat input ────────────────────────────────────────────────────────
question = st.chat_input("Ask a question / Задайте вопрос / Сұрақ қойыңыз")

if question:
    # Cancel any pending clarification if user types a new question
    if "pending_question" in st.session_state:
        del st.session_state["pending_question"]
        del st.session_state["pending_lang"]

    lang = detect_lang(question)
    st.session_state.messages.append({"role": "user", "content": question, "lang": lang})

    if detect_ambiguous_question(question):
        # Save original question, add bot clarification to history, show form
        clarify_msg = CLARIFY_TEXT[lang]
        st.session_state.messages.append({"role": "assistant", "content": clarify_msg})
        st.session_state["pending_question"] = question
        st.session_state["pending_lang"]     = lang
        st.rerun()

    else:
        # Render the new user message + answer directly (history loop already ran)
        with st.chat_message("user"):
            st.caption(f"Detected language: {LANG_LABELS[lang]}")
            st.write(question)
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                answer = answer_question(question, lang)
            st.write(answer)
            st.session_state.messages.append({"role": "assistant", "content": answer})

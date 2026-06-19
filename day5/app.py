import os
import re
import requests
import streamlit as st
from dotenv import load_dotenv

# ── API keys — loaded from .env, never hardcoded ──────────────────────────────
load_dotenv()
LLM_MODEL      = os.getenv("LLM_MODEL")
LLM_URL        = os.getenv("LLM_URL")
LLM_API_KEY    = os.getenv("LLM_API_KEY")
MAILERSEND_KEY = os.getenv("MAILERSEND_KEY")
FROM_EMAIL     = os.getenv("FROM_EMAIL", "info@app.commit.kz")
ADMIN_EMAIL    = os.getenv("ADMIN_EMAIL")

# ── Language detection ────────────────────────────────────────────────────────
try:
    from langdetect import detect, LangDetectException, DetectorFactory
    DetectorFactory.seed = 0
    LANGDETECT_OK = True
except ImportError:
    LANGDETECT_OK = False

# ── MailerSend ────────────────────────────────────────────────────────────────
try:
    from mailersend import emails
    MAILERSEND_OK = True
except ImportError:
    MAILERSEND_OK = False

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

# ── Порог для отправки email ──────────────────────────────────────────────────
EMAIL_TRIGGER_COUNT = 5   # отправляем после 5-го вопроса от пользователя

# ── Quick question buttons ────────────────────────────────────────────────────
QUICK_QUESTIONS = [
    {"label": "📋 Какие программы есть?",      "question": "Какие программы есть у фонда Есенова?"},
    {"label": "📅 Дедлайн YDL 2026?",          "question": "Когда дедлайн подачи заявки на Yessenov Data Lab 2026?"},
    {"label": "📄 Документы для стипендии?",   "question": "Какие документы нужны для Yessenov Scholarship?"},
    {"label": "🎓 Кто может подать на YDL?",   "question": "Кто может участвовать в Yessenov Data Lab?"},
    {"label": "📆 Даты школы YDL 2026?",       "question": "Когда проходит Yessenov Data Lab 2026?"},
    {"label": "🚀 Что такое Launch Pad?",       "question": "Что такое Yessenov Launch Pad?"},
]

# ── Active programs ───────────────────────────────────────────────────────────
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

PROGRAM_NAMES   = [p["name"]        for p in PROGRAMS]
PROGRAM_SLUG    = {p["name"]: p["url_slug"]    for p in PROGRAMS}
PROGRAM_DETAIL  = {p["name"]: p["detail_slug"] for p in PROGRAMS}
PROGRAM_ALIASES = {p["name"]: p["aliases"]     for p in PROGRAMS}

AMBIGUOUS_KEYWORDS = [
    "document", "apply", "application", "require", "requirement",
    "eligib", "criteria", "criterion", "deadline", "submit", "submission",
    "who can", "how to", "how do", "participate", "enroll", "register",
    "документ", "подать", "подача", "заявк", "требован",
    "критери", "дедлайн", "срок", "кто может", "как участв", "участвовать",
    "записаться", "зарегистрироваться",
    "құжат", "өтінім", "талап", "мерзім", "қалай", "кім", "қатысу", "тіркел",
]

PROGRAM_DETECT_KEYWORDS = (
    [alias.lower() for prog in PROGRAMS for alias in prog["aliases"]]
    + [p["name"].lower() for p in PROGRAMS]
)

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

_SEP     = re.compile(r"={20,}\nPAGE:\s*(.+?)\nURL:\s*(\S+)\n={20,}", re.MULTILINE)
_YEAR_RE = re.compile(r'\b(201[3-9]|202[0-9]|2030)\b')

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
6. Always reply in the same language the user wrote in.
7. IMPORTANT: Answer only about ONE specific program edition (year).
   Do NOT compare multiple years unless the user explicitly asks to compare."""

SUMMARY_PROMPT = """You are a helpful assistant. 
Summarize the following chat conversation in 3-5 bullet points in Russian.
Focus on: what programs the user asked about, what information they received,
and any important details (deadlines, requirements, documents).
Be concise and factual. Do not add anything not in the conversation."""


# ─────────────────────────────────────────────────────────────────────────────
# EMAIL FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def generate_summary(messages: list[dict]) -> str:
    """Просим LLM сделать краткое саммари разговора."""
    # Собираем историю в текст
    history = ""
    for msg in messages:
        role = "Пользователь" if msg["role"] == "user" else "Бот"
        history += f"{role}: {msg['content']}\n\n"

    url = LLM_URL.rstrip("/")
    if not url.endswith("/chat/completions"):
        url += "/chat/completions"

    try:
        resp = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {LLM_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": SUMMARY_PROMPT},
                    {"role": "user",   "content": f"Вот разговор:\n\n{history}"},
                ],
                "temperature": 0.1,
            },
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Не удалось сгенерировать саммари: {e}"


def send_summary_email(summary: str, messages: list[dict]) -> bool:
    """Отправляем саммари + полную историю на ADMIN_EMAIL через MailerSend."""
    if not MAILERSEND_OK:
        return False
    if not MAILERSEND_KEY or not ADMIN_EMAIL:
        return False

    # Полная история для тела письма
    full_history = ""
    for msg in messages:
        role = "👤 Пользователь" if msg["role"] == "user" else "🤖 Бот"
        full_history += f"<p><b>{role}:</b><br>{msg['content']}</p><hr>"

    html_body = f"""
    <h2>Саммари разговора — Yessenov Foundation Assistant</h2>
    <h3>📋 Краткое резюме:</h3>
    <p>{summary.replace(chr(10), '<br>')}</p>
    <hr>
    <h3>💬 Полная история ({len([m for m in messages if m['role'] == 'user'])} вопросов):</h3>
    {full_history}
    """

    try:
        mailer = emails.NewEmail(MAILERSEND_KEY)
        mail_body = {}
        mailer.set_mail_from({"email": FROM_EMAIL, "name": "Yessenov Data Lab"}, mail_body)
        mailer.set_mail_to([{"email": ADMIN_EMAIL, "name": "Admin"}], mail_body)
        mailer.set_subject("📬 Новый разговор в боте Есенова", mail_body)
        mailer.set_html_content(html_body, mail_body)
        mailer.set_plaintext_content(f"Саммари:\n{summary}", mail_body)
        response = mailer.send(mail_body)
        return True
    except Exception as e:
        st.sidebar.error(f"Ошибка отправки email: {e}")
        return False


def maybe_send_email():
    """
    Проверяем количество вопросов пользователя.
    Если достигли EMAIL_TRIGGER_COUNT и письмо ещё не отправлено — отправляем.
    """
    messages = st.session_state.get("messages", [])
    user_messages = [m for m in messages if m["role"] == "user"]
    already_sent  = st.session_state.get("email_sent_at", 0)

    # Считаем сколько новых вопросов с последней отправки
    count = len(user_messages)
    if count > 0 and count % EMAIL_TRIGGER_COUNT == 0 and count != already_sent:
        # Генерируем саммари через LLM
        with st.spinner("📧 Сохраняем историю разговора..."):
            summary = generate_summary(messages)
            success = send_summary_email(summary, messages)

        if success:
            st.session_state["email_sent_at"] = count
            st.toast("📧 История разговора сохранена!", icon="✅")


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


def detect_program_from_question(question: str) -> str | None:
    q = question.lower()
    for prog in PROGRAMS:
        if prog["name"].lower() in q:
            return prog["name"]
        for alias in prog["aliases"]:
            if alias.lower() in q:
                return prog["name"]
    return None


@st.cache_data
def load_pages(lang: str) -> list[dict]:
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
    q = question.lower()
    for kw in PROGRAM_DETECT_KEYWORDS:
        if kw in q:
            return False
    for kw in AMBIGUOUS_KEYWORDS:
        if kw in q:
            return True
    return False


def filter_by_program(pages: list[dict], url_slug: str | None) -> list[dict]:
    if not url_slug:
        return pages
    filtered = [p for p in pages if url_slug in p["url"]]
    return filtered if filtered else pages


def detect_year(question: str) -> int | None:
    match = _YEAR_RE.search(question)
    return int(match.group()) if match else None


def extract_year_from_page(page: dict) -> int | None:
    years = _YEAR_RE.findall(page["url"] + " " + page["title"])
    if not years:
        years = _YEAR_RE.findall(page["text"][:300])
    return max(int(y) for y in years) if years else None


def select_year_filtered_pages(pages, asked_year):
    tagged    = [(page, extract_year_from_page(page)) for page in pages]
    overview  = [p for p, y in tagged if y is None]
    with_year = [(p, y) for p, y in tagged if y is not None]

    if not with_year:
        return pages, None, "latest (no dated pages)"

    all_years = [y for _, y in with_year]

    if asked_year is not None:
        year_pages = [p for p, y in with_year if y == asked_year]
        if year_pages:
            return overview + year_pages, asked_year, "exact year"
        latest = max(all_years)
        return overview + [p for p, y in with_year if y == latest], latest, "exact year (not found, using latest)"

    latest = max(all_years)
    return overview + [p for p, y in with_year if y == latest], latest, "latest"


def score_and_retrieve(pages, query, top_k=5, detail_slug=None):
    words = set(re.findall(r"\w+", query.lower())) - STOPWORDS
    scored = []
    for page in pages:
        if words:
            score  = sum(1 for w in words if w in page["text"].lower())
            score += sum(3 for w in words if w in page["title"].lower())
        else:
            score = 0
        if detail_slug and detail_slug in page["url"]:
            score += 5
        scored.append((score, page))
    scored.sort(key=lambda x: -x[0])
    relevant = [(s, p) for s, p in scored if s > 0]
    top = (relevant or scored)[:top_k]
    return [p for _, p in top], scored


def build_context(pages, max_chars=1400):
    parts = []
    for page in pages:
        text = page["text"]
        if len(text) > max_chars:
            text = text[:max_chars] + "\n[…]"
        parts.append(f"=== SOURCE: {page['title']} ===\nURL: {page['url']}\n\n{text}")
    return "\n\n---\n\n".join(parts)


def ask_llm(question: str, context: str) -> str:
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


def answer_question(question: str, lang: str, program_name: str | None = None) -> str:
    pages = load_pages(lang)
    if not pages:
        return (
            f"Data file for **{LANG_LABELS[lang]}** is not available yet. "
            f"Run the scraper first.\n\n{NO_DATA_TEXT[lang]}"
        )

    FALLBACK_THRESHOLD = 5
    if lang != "en":
        en_pages = load_pages("en")
        if en_pages:
            program_name_check = detect_program_from_question(question)
            slug_check = PROGRAM_SLUG.get(program_name_check) if program_name_check else None
            if slug_check:
                lang_program_pages = [p for p in pages if slug_check in p["url"]]
                if len(lang_program_pages) < FALLBACK_THRESHOLD:
                    en_program_pages = [p for p in en_pages if slug_check in p["url"]]
                    pages = pages + en_program_pages

    if program_name is None:
        program_name = detect_program_from_question(question)

    url_slug    = PROGRAM_SLUG.get(program_name)        if program_name else None
    detail_slug = PROGRAM_DETAIL.get(program_name)      if program_name else None
    aliases     = PROGRAM_ALIASES.get(program_name, []) if program_name else []

    if url_slug:
        pages = filter_by_program(pages, url_slug)

    asked_year = detect_year(question)
    if program_name:
        pages, selected_year, year_mode = select_year_filtered_pages(pages, asked_year)
    else:
        selected_year, year_mode = None, "—"

    if program_name and selected_year:
        query = question
    else:
        alias_str = " ".join(aliases)
        query = f"{program_name or ''} {alias_str} {question}".strip()

    selected_pages, all_scored = score_and_retrieve(pages, query, top_k=5, detail_slug=detail_slug)
    context = build_context(selected_pages)

    st.session_state["last_debug"] = {
        "lang":            lang,
        "program":         program_name or "—",
        "question":        question,
        "asked_year":      asked_year,
        "selected_year":   selected_year,
        "year_mode":       year_mode,
        "query":           query,
        "aliases":         aliases,
        "selected_titles": [p["title"] for p in selected_pages],
        "selected_urls":   [p["url"]   for p in selected_pages],
        "all_scores":      [(p["title"][:60], s) for s, p in all_scored[:15]],
    }

    try:
        return ask_llm(question, context)
    except Exception as e:
        return f"Error calling the model: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# HANDLE QUESTION
# ─────────────────────────────────────────────────────────────────────────────

def handle_question(question: str):
    """Единая функция обработки вопроса."""

    # Специальный ответ для вопроса о списке программ
    PROGRAMS_KEYWORDS = [
        "какие программы", "список программ", "what programs",
        "программы фонда", "programs", "бағдарламалар"
    ]
    q_lower = question.lower()
    if any(kw in q_lower for kw in PROGRAMS_KEYWORDS):
        lang = detect_lang(question)
        st.session_state.messages.append({"role": "user", "content": question, "lang": lang})
        if lang == "ru":
            answer = (
                "У фонда Есенова есть следующие **активные программы**:\n\n"
                "1. **Yessenov Scholarship** — ежемесячная стипендия для студентов\n"
                "2. **Research Internships** — научные стажировки в лабораториях мира\n"
                "3. **English Language Program** — программа изучения английского языка\n"
                "4. **Yessenov Data Lab** — летняя школа по анализу данных\n"
                "5. **Yessenov Launch Pad** — поддержка стартапов\n\n"
                "Подробнее: https://yessenovfoundation.org/ru/about-us/programs/"
            )
        elif lang == "kk":
            answer = (
                "Есенов қорының **белсенді бағдарламалары**:\n\n"
                "1. **Yessenov Scholarship** — студенттерге ай сайынғы шәкіртақы\n"
                "2. **Research Internships** — әлем зертханаларындағы ғылыми тағылымдама\n"
                "3. **English Language Program** — ағылшын тілі бағдарламасы\n"
                "4. **Yessenov Data Lab** — деректерді талдау жазғы мектебі\n"
                "5. **Yessenov Launch Pad** — стартап қолдауы\n\n"
                "Толығырақ: https://yessenovfoundation.org/kk/about-us/programs/"
            )
        else:
            answer = (
                "The Yessenov Foundation has the following **active programs**:\n\n"
                "1. **Yessenov Scholarship** — monthly scholarship for students\n"
                "2. **Research Internships** — scientific internships in world laboratories\n"
                "3. **English Language Program** — English language program\n"
                "4. **Yessenov Data Lab** — summer school for data analysis\n"
                "5. **Yessenov Launch Pad** — startup support\n\n"
                "Learn more: https://yessenovfoundation.org/en/about-us/programs/"
            )
        with st.chat_message("user"):
            st.caption(f"Detected language: {LANG_LABELS[lang]}")
            st.write(question)
        with st.chat_message("assistant"):
            st.write(answer)
        st.session_state.messages.append({"role": "assistant", "content": answer})

        # Проверяем нужно ли отправить email
        maybe_send_email()
        return

    if "pending_question" in st.session_state:
        del st.session_state["pending_question"]
        del st.session_state["pending_lang"]

    lang = detect_lang(question)
    st.session_state.messages.append({"role": "user", "content": question, "lang": lang})

    if detect_ambiguous_question(question):
        clarify_msg = CLARIFY_TEXT[lang]
        st.session_state.messages.append({"role": "assistant", "content": clarify_msg})
        st.session_state["pending_question"] = question
        st.session_state["pending_lang"]     = lang
        st.rerun()
    else:
        with st.chat_message("user"):
            st.caption(f"Detected language: {LANG_LABELS[lang]}")
            st.write(question)
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                answer = answer_question(question, lang)
            st.write(answer)
        st.session_state.messages.append({"role": "assistant", "content": answer})

        # Проверяем нужно ли отправить email
        maybe_send_email()


# ─────────────────────────────────────────────────────────────────────────────
# STREAMLIT UI
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(page_title="Yessenov Foundation Assistant", page_icon="🤖")
st.title("Yessenov Foundation Assistant")

if not LLM_API_KEY or not LLM_URL or not LLM_MODEL:
    st.error("Missing LLM_API_KEY, LLM_URL, or LLM_MODEL in .env")
    st.stop()

if not LANGDETECT_OK:
    st.warning("langdetect not installed. Run: pip install langdetect")

if not MAILERSEND_OK:
    st.warning("mailersend not installed. Run: pip install mailersend")

# ── Debug sidebar ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Settings")
    show_debug = st.checkbox("Show debug info", value=False)

    # Счётчик вопросов
    user_q_count = len([m for m in st.session_state.get("messages", []) if m["role"] == "user"])
    st.caption(f"Вопросов задано: {user_q_count} / следующий email после {EMAIL_TRIGGER_COUNT - (user_q_count % EMAIL_TRIGGER_COUNT) if user_q_count % EMAIL_TRIGGER_COUNT != 0 else 0} вопросов")

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
if "email_sent_at" not in st.session_state:
    st.session_state.email_sent_at = 0

# ── Chat history ──────────────────────────────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "user" and "lang" in msg:
            st.caption(f"Detected language: {LANG_LABELS[msg['lang']]}")
        st.write(msg["content"])

# ── Clarification selectbox ───────────────────────────────────────────────────
if st.session_state.get("pending_question"):
    lang = st.session_state["pending_lang"]
    with st.form("clarify_form"):
        st.write(f"**{SELECT_LABEL[lang]}**")
        selected_program = st.selectbox(
            label="program", options=PROGRAM_NAMES, label_visibility="collapsed",
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
        maybe_send_email()
        st.rerun()

# ── Chat input ────────────────────────────────────────────────────────────────
question = st.chat_input("Ask a question / Задайте вопрос / Сұрақ қойыңыз")
if question:
    handle_question(question)

# ── Quick question buttons ────────────────────────────────────────────────────
st.divider()
st.caption("Быстрые вопросы / Quick questions:")

row1 = st.columns(3)
row2 = st.columns(3)
for i, btn in enumerate(QUICK_QUESTIONS):
    col = row1[i] if i < 3 else row2[i - 3]
    if col.button(btn["label"], use_container_width=True, key=f"quick_{i}"):
        handle_question(btn["question"])
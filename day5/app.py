import os
import json
import re
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

LLM_MODEL = os.getenv("LLM_MODEL")
LLM_URL = os.getenv("LLM_URL")
LLM_API_KEY = os.getenv("LLM_API_KEY")

st.set_page_config(page_title="Yessenov Foundation Assistant", page_icon="🤖")

st.title("🤖 Yessenov Foundation Assistant")
st.write("Ask questions about the Shakhmardan Yessenov Foundation — programs, grants, FAQ.")

if not LLM_API_KEY or not LLM_URL or not LLM_MODEL:
    st.error("Missing LLM_API_KEY, LLM_URL, or LLM_MODEL in .env file.")
    st.stop()


@st.cache_data
def load_pages():
    with open("data/yessenov_pages.json", "r", encoding="utf-8") as f:
        return json.load(f)


try:
    pages = load_pages()
except FileNotFoundError:
    st.error("data/yessenov_pages.json not found. Run: python scrape_yessenov.py")
    st.stop()


STOPWORDS = {
    # English
    "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "what", "who", "how", "when", "where", "which", "do", "does",
    "i", "me", "my", "you", "your", "it", "its", "this", "that",
    "and", "or", "of", "to", "in", "for", "on", "with", "about",
    # Russian
    "и", "в", "на", "с", "по", "что", "как", "не", "это", "из",
    "за", "от", "до", "для", "но", "же", "о", "я", "вы", "он",
    # Kazakh
    "бұл", "және", "не", "ол", "да", "де", "үшін", "бар", "жоқ",
}


def find_relevant_pages(question: str, top_k: int = 5) -> list[dict]:
    words = set(re.findall(r'\w+', question.lower())) - STOPWORDS

    scored = []
    for page in pages:
        text_lower = page["text"].lower()
        title_lower = page["title"].lower()
        # Title matches count double — they signal the page is directly about the topic
        score = sum(1 for w in words if w in text_lower)
        score += sum(2 for w in words if w in title_lower)
        scored.append((score, page))

    scored.sort(key=lambda x: -x[0])
    relevant = [(s, p) for s, p in scored if s > 0]

    # If nothing matched at all, return the homepage and programs page as fallback
    if not relevant:
        return [p for p in pages if "programs" in p["url"] or p["url"].endswith("/en/")][:top_k]

    return [p for _, p in relevant[:top_k]]


def build_context(relevant: list[dict]) -> str:
    parts = []
    for page in relevant:
        parts.append(
            f"=== SOURCE: {page['title']} ===\n"
            f"URL: {page['url']}\n\n"
            f"{page['text'].strip()}"
        )
    return "\n\n---\n\n".join(parts)


SYSTEM_PROMPT = """You are an assistant for the Shakhmardan Yessenov Foundation.

STRICT RULES — follow every one, no exceptions:
1. Answer ONLY using the SOURCE sections provided in the user message.
2. Never invent, infer, or guess any detail not explicitly stated in the sources — this includes program names, subcategories, deadlines, grant amounts, eligibility requirements, or any other specifics.
3. Do not create structure (bullet lists, subcategories, sections) that is not present in the sources.
4. At the end of every answer, cite which source(s) you used: write the page title and its URL.
5. If the answer is not found in the provided sources, say so in the same language as the question:
   • English → "I don't have this information in the available data."
   • Russian → "У меня нет этой информации в доступных данных."
   • Kazakh → "Менде бұл ақпарат жоқ."
6. Always reply in the same language the user wrote in."""


def ask_llm(user_question: str) -> str:
    relevant = find_relevant_pages(user_question)
    context = build_context(relevant)

    user_prompt = f"SOURCES:\n\n{context}\n\n---\n\nQUESTION: {user_question}"

    url = LLM_URL.rstrip("/")
    if not url.endswith("/chat/completions"):
        url += "/chat/completions"

    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
    }

    response = requests.post(url, headers=headers, json=payload, timeout=60)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

question = st.chat_input("Ask about the Yessenov Foundation...")

if question:
    st.session_state.messages.append({"role": "user", "content": question})

    with st.chat_message("user"):
        st.write(question)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                answer = ask_llm(question)
                st.write(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})
            except Exception as e:
                st.error(f"Error calling the model: {e}")

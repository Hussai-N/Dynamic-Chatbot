import streamlit as st
from scraper.web_scraper import scrape_website
from utils.helpers import chunk_text_smart, build_idf, select_top_chunks
import requests
import json
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from config import GEMINI_API_KEY, CONTEXT_MAX_CHARS, MAX_HISTORY_TURNS, GEMINI_TIMEOUT, CHUNK_SIZE, CHUNK_OVERLAP_WORDS

# Networking helpers with retry for transient errors
def make_session():
    retry_strategy = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["GET", "POST"])
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

def post_with_retry(url, headers, payload, timeout):
    session = make_session()
    return session.post(url, headers=headers, data=json.dumps(payload), timeout=timeout)

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("Login to Dynamic Website Chatbot")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if username == "admin" and password == "admin123":
            st.session_state.logged_in = True
            if hasattr(st, "rerun"):
                st.rerun()
            else:
                st.experimental_rerun()
        else:
            st.error("Invalid username or password")

    # Styles for login page
    st.markdown("""
    <style>
    .stTextInput input {
        border-radius: 5px;
        border: 1px solid #ccc;
    }
    .stButton button {
        background-color: #007bff;
        color: white;
        border-radius: 5px;
        border: none;
        padding: 10px 20px;
    }
    .stButton button:hover {
        background-color: #0056b3;
    }
    .stAlert {
        border-radius: 5px;
        padding: 10px;
    }
    </style>
    """, unsafe_allow_html=True)
else:
    st.title("Dynamic Website Chatbot")

    # Custom styles
    st.markdown("""
    <style>
    .main {
        background-color: #f5f5f5;
    }
    .stHeader {
        background-color: #ffffff;
    }
    .stTextInput input {
        border-radius: 5px;
        border: 1px solid #ccc;
    }
    .stButton button {
        background-color: #007bff;
        color: white;
        border-radius: 5px;
        border: none;
        padding: 10px 20px;
    }
    .stButton button:hover {
        background-color: #0056b3;
    }
    .stChatMessage {
        border-radius: 10px;
        margin-bottom: 10px;
        padding: 10px;
    }
    .stAlert {
        border-radius: 5px;
        padding: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

    url = st.text_input("Enter Website URL:")

    if url:
        with st.spinner("Scraping website..."):
            content = scrape_website(url)
        if content.startswith("Error"):
            st.error(content)
        else:
            st.success("Website scraped successfully!")
            # Initialize or reset session state for chat when URL changes
            if "last_url" not in st.session_state or st.session_state["last_url"] != url:
                st.session_state["last_url"] = url
                st.session_state["messages"] = []

            # Prepare retrieval data once and store (sentence-aware chunking with overlap)
            chunks = chunk_text_smart(content, CHUNK_SIZE, CHUNK_OVERLAP_WORDS)
            st.session_state["chunks"] = chunks
            st.session_state["idf"] = build_idf(chunks)
            st.session_state["site_context"] = "\n\n".join(chunks)  # Full context for debug
            chunk_lengths = [len(chunk) for chunk in chunks]
            st.session_state["chunk_lengths"] = chunk_lengths

            st.caption("Chat about this website below. The assistant answers using only the scraped content.")

            debug_mode = st.checkbox("Debug mode (show chunk info)")
            show_content = st.checkbox("Show full scraped content")
            if show_content:
                st.text_area("Scraped website content:", value=st.session_state.get("site_context", ""), height=200)

            if debug_mode:
                chunk_lengths = st.session_state["chunk_lengths"]
                st.write(f"Total chunks: {len(st.session_state['chunks'])}")
                st.write(f"Total characters in site context: {len(st.session_state['site_context'])}")
                st.write(f"Average chunk size: {sum(chunk_lengths) / len(chunk_lengths):.1f} chars")
                st.write(f"Min chunk size: {min(chunk_lengths)} chars")
                st.write(f"Max chunk size: {max(chunk_lengths)} chars")
                st.write(f"Unique words in IDF: {len(st.session_state['idf'])}")

            # Render chat history
            if "messages" in st.session_state:
                for m in st.session_state["messages"]:
                    with st.chat_message("user" if m["role"] == "user" else "assistant"):
                        st.write(m["content"])

            # Optional: clear chat
            if st.button("Clear chat"):
                st.session_state["messages"] = []
                # Streamlit API compatibility: prefer st.rerun(), fallback to experimental API if older version
                if hasattr(st, "rerun"):
                    st.rerun()
                else:
                    st.experimental_rerun()

            # Chat input (multi-turn)
            prompt = st.chat_input("Ask a question about this website")
            if prompt:
                # Echo user message
                st.session_state["messages"].append({"role": "user", "content": prompt})
                with st.chat_message("user"):
                    st.write(prompt)

                with st.spinner("Generating answer..."):
                    model = "gemini-1.5-flash-latest"
                    url_endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
                    headers = {"Content-Type": "application/json"}

                    # Select the most relevant website chunks for this question
                    start_time = time.time()
                    selected_context = select_top_chunks(
                        prompt,
                        st.session_state["chunks"],
                        st.session_state["idf"],
                        k=7,
                        max_chars=CONTEXT_MAX_CHARS
                    )
                    end_time = time.time()
                    processing_time = end_time - start_time

                    if debug_mode:
                        st.write(f"Total chunks: {len(st.session_state['chunks'])}")
                        st.write(f"Selected context length: {len(selected_context)} chars")
                        st.write(f"Number of selected chunks: {selected_context.count('Chunk ')}")
                        st.write(f"Processing time for chunk selection: {processing_time:.2f} seconds")
                        st.write("Selected chunks preview:")
                        st.text(selected_context[:1000] + "..." if len(selected_context) > 1000 else selected_context)

                    # Build a single focused user message
                    user_message = (
                        "You are answering strictly from the provided website snippets.\n"
                        "Snippets:\n"
                        f"{selected_context}\n\n"
                        f"Question: {prompt}\n\n"
                        "Instructions:\n"
                        "- Base the answer only on the snippets. Do not use outside knowledge.\n"
                        "- If the snippets do not contain the answer, say: "
                        "\"I don't know based on the provided website content.\"\n"
                        "- When possible, cite the chunk numbers you used.\n"
                        "- Keep the answer concise and relevant."
                    )

                    # Build contents starting with recent conversation history, then the current question
                    contents = []
                    history = st.session_state["messages"][-MAX_HISTORY_TURNS:]
                    for m in history:
                        contents.append({
                            "role": "user" if m["role"] == "user" else "model",
                            "parts": [{"text": m["content"]}]
                        })
                    contents.append({
                        "role": "user",
                        "parts": [{"text": user_message}]
                    })

                    # Add the current question last to focus the model
                    contents.append({
                        "role": "user",
                        "parts": [
                            {
                                "text": (
                                    f"Question: {prompt}\n\n"
                                    "- Base your answer strictly on the snippets above.\n"
                                    "- If information is missing, say: \"I don't know based on the provided website content.\"\n"
                                    "- When possible, cite the chunk numbers you used."
                                )
                            }
                        ]
                    })

                    payload = {
                        "contents": contents,
                        "generationConfig": {
                            "maxOutputTokens": 500,
                            "temperature": 0.2,
                            "topP": 0.9,
                            "topK": 40
                        }
                    }

                    try:
                        api_start = time.time()
                        response = post_with_retry(url_endpoint, headers, payload, timeout=GEMINI_TIMEOUT)
                        if response.status_code == 200:
                            res_json = response.json()
                            answer = (
                                res_json.get("candidates", [{}])[0]
                                .get("content", {})
                                .get("parts", [{}])[0]
                                .get("text", "")
                            ) or "No answer returned."

                            api_end = time.time()
                            api_time = api_end - api_start

                            st.session_state["messages"].append({"role": "assistant", "content": answer})
                            with st.chat_message("assistant"):
                                st.write(answer)

                            if debug_mode:
                                st.write(f"API response time: {api_time:.2f} seconds")
                        elif response.status_code == 503:
                            st.error("The Gemini model is currently overloaded. Please try again in a few minutes.")
                        else:
                            st.error(f"API Error: {response.status_code} - {response.text}")
                    except requests.exceptions.ReadTimeout:
                        st.error("The request to Gemini timed out. The website content may be large. Try asking a shorter question or reduce context.")
                    except requests.exceptions.RequestException as e:
                        st.error(f"Request failed: {e}")

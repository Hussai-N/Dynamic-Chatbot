import streamlit as st
from scraper.web_scraper import scrape_website
from utils.helpers import chunk_text
import requests
import json
from config import GEMINI_API_KEY, CONTEXT_MAX_CHARS, MAX_HISTORY_TURNS, GEMINI_TIMEOUT

st.title("Dynamic Website Chatbot (Gemini LLM)")

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

        # Prepare website context once and store
        chunks = chunk_text(content)
        context = "\n\n".join(chunks)
        if len(context) > CONTEXT_MAX_CHARS:
            context = context[:CONTEXT_MAX_CHARS]
        st.session_state["site_context"] = context

        st.caption("Chat about this website below. The assistant answers using only the scraped content.")

        # Render chat history
        if "messages" in st.session_state:
            for m in st.session_state["messages"]:
                with st.chat_message("user" if m["role"] == "user" else "assistant"):
                    st.write(m["content"])

        # Optional: clear chat
        if st.button("Clear chat"):
            st.session_state["messages"] = []
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

                # Build conversation contents including website context (as grounding)
                instruction = (
                    "You are a helpful assistant that answers questions using ONLY the provided website content. "
                    "If the answer cannot be found in the content, say you don't know."
                )
                contents = [
                    {
                        "role": "user",
                        "parts": [
                            {
                                "text": f"{instruction}\n\nWebsite content:\n\n{st.session_state['site_context']}"
                            }
                        ]
                    }
                ]

                # Append recent conversation history (to reduce latency)
                history = st.session_state["messages"][-MAX_HISTORY_TURNS:]
                for m in history:
                    contents.append({
                        "role": "user" if m["role"] == "user" else "model",
                        "parts": [{"text": m["content"]}]
                    })

                payload = {
                    "contents": contents,
                    "generationConfig": {
                        "maxOutputTokens": 500,
                        "temperature": 0.2
                    }
                }

                try:
                    response = requests.post(url_endpoint, headers=headers, data=json.dumps(payload), timeout=GEMINI_TIMEOUT)
                    if response.status_code == 200:
                        res_json = response.json()
                        answer = (
                            res_json.get("candidates", [{}])[0]
                            .get("content", {})
                            .get("parts", [{}])[0]
                            .get("text", "")
                        ) or "No answer returned."
                        st.session_state["messages"].append({"role": "assistant", "content": answer})
                        with st.chat_message("assistant"):
                            st.write(answer)
                    else:
                        st.error(f"API Error: {response.status_code} - {response.text}")
                except requests.exceptions.ReadTimeout:
                    st.error("The request to Gemini timed out. The website content may be large. Try asking a shorter question or reduce context.")
                except requests.exceptions.RequestException as e:
                    st.error(f"Request failed: {e}")

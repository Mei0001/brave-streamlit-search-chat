import os
import time
import requests
import streamlit as st
from typing import Any, Dict, List, Optional


def get_api_key() -> Optional[str]:
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv()
    except Exception:
        pass
    secret = st.secrets.get("BRAVE_API_KEY") if hasattr(st, "secrets") else None
    return secret or os.getenv("BRAVE_API_KEY")


API_KEY = get_api_key()
ENDPOINT = "https://api.search.brave.com/res/v1/web/search"

st.set_page_config(page_title="Brave Web Search Chat", page_icon="🔎", layout="wide")
st.title("Brave Search API × Chat - Web検索チャットボット")


def ensure_state():
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": "こんにちは。Web検索で情報をお探しします。キーワードを入力してください。",
            }
        ]


def brave_search(
    query: str,
    *,
    count: int = 8,
    search_lang: str = "ja",
    country: Optional[str] = None,
    safesearch: str = "moderate",
    freshness: Optional[str] = None,
    retries: int = 2,
    timeout_sec: int = 15,
) -> Optional[Dict[str, Any]]:
    if not API_KEY:
        st.error("環境変数/Secretsの BRAVE_API_KEY が未設定です。`.env` もしくは Streamlit Secrets に設定してください。")
        return None
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": API_KEY,
    }
    params: Dict[str, Any] = {
        "q": query,
        "count": count,
        "search_lang": search_lang,
        "safesearch": safesearch,
    }
    if country:
        params["country"] = country
    if freshness:
        params["freshness"] = freshness

    backoff = 1.0
    for attempt in range(retries + 1):
        resp = requests.get(ENDPOINT, headers=headers, params=params, timeout=timeout_sec)
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code in (429, 502, 503, 504) and attempt < retries:
            time.sleep(backoff)
            backoff *= 2
            continue
        st.error(f"APIエラー: status={resp.status_code} body={resp.text[:400]}")
        return None
    return None


def format_results(results: List[Dict[str, Any]]) -> str:
    if not results:
        return "検索結果は見つかりませんでした。"
    lines: List[str] = []
    for i, item in enumerate(results, start=1):
        title = item.get("title") or "(no title)"
        url = item.get("url") or ""
        desc = item.get("description") or ""
        lines.append(f"{i}. [{title}]({url})\n\n{desc}\n")
    return "\n".join(lines)


ensure_state()

with st.sidebar:
    st.header("検索設定")
    count = st.slider("件数", 1, 50, 8)
    search_lang = st.selectbox("検索言語(search_lang)", ["ja", "en"], index=0)
    country = st.selectbox("国コード(country)", ["", "jp", "us", "gb", "de", "fr", "in"], index=1)
    safesearch = st.selectbox("セーフサーチ", ["off", "moderate", "strict"], index=1)
    freshness = st.selectbox("鮮度(freshness)", ["", "pd", "pw", "pm"], index=0, help="pd=1日, pw=1週, pm=1か月 など")
    st.caption("APIキーは .env または Secrets に BRAVE_API_KEY を設定")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

user_input = st.chat_input("検索したい内容を入力...")
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("検索中..."):
            data = brave_search(
                user_input,
                count=count,
                search_lang=search_lang,
                country=country or None,
                safesearch=safesearch,
                freshness=freshness or None,
            )
        if not data:
            st.stop()
        web = (data.get("web") or {})
        results = web.get("results") or []
        md = format_results(results)
        st.markdown(md)
        st.session_state.messages.append({"role": "assistant", "content": md})



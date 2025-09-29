## Brave Search API × Streamlit Web検索アプリ 手順書・調査メモ（2025-09）

本書は、Brave Search APIの仕様調査と、同APIを用いたWeb検索機能付きStreamlitアプリの構築手順をまとめたものです。日本語環境（`search_lang=ja`）を前提にしています。

### 1. Brave Search API 概要
- **ベースURL**: `https://api.search.brave.com`
- **代表的エンドポイント（検索系）**
  - Web検索: `/res/v1/web/search`
  - 画像検索: `/res/v1/images/search`
  - 動画検索: `/res/v1/videos/search`
  - ニュース検索: `/res/v1/news/search`
  - サジェスト: `/res/v1/suggest`
- **認証**: ヘッダー `X-Subscription-Token: <API_KEY>` を付与
- **推奨ヘッダー**: `Accept: application/json`, `Accept-Encoding: gzip`

参考: Brave Search APIダッシュボード/ドキュメント（ログイン要） `https://api-dashboard.search.brave.com/app/documentation`

### 2. 料金・レート制限（要最新確認）
- 無料枠: 月あたり約2,000クエリ（公式の現行ページでご確認ください）
- 有料: 1,000クエリ単価の従量課金プランあり
- レート制限: 秒間リクエスト数（RPS）制限あり。バーストを避け、バックオフ・リトライを実装推奨

注: 料金/制限は変更されるため、利用前に公式ダッシュボードで最新情報を確認してください。

### 3. 代表的なクエリパラメータ（Web検索）
- `q` : 検索クエリ（必須）
- `count` : 取得件数（例: 10）
- `offset` : ページング用オフセット（例: 0, 10, 20 ...）
- `safesearch` : セーフサーチ（例: `off` | `moderate` | `strict`）
- `search_lang` : 検索言語（例: `ja`, `en`）
- `country` : 国コード（例: `jp`, `us`）
- `freshness` : 新しさフィルタ（例: `pd`(日), `pw`(週), `pm`(月) 等）
- `spellcheck` : スペルチェック有無（例: `1`/`0`）

レスポンス例（Web検索）では、`web.results` 配下に `title`, `url`, `description` などが含まれます。

### 4. 認証・セキュリティ
- APIキーは**機密情報**。公開リポジトリに直書きしない
- 環境変数（例: `.env` + `python-dotenv`）やStreamlitのSecrets機能を活用
- ネットワーク障害や429（Rate Limit）に備え、指数バックオフのリトライを推奨

### 5. 開発環境セットアップ
1) Python 3.9+ を推奨
2) 仮想環境を作成
3) 必要パッケージをインストール

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install streamlit requests python-dotenv
```

### 6. 最小実装の流れ（Streamlit）
1) ルート直下に `.env` を用意し、APIキーを保存

```
BRAVE_API_KEY=あなたのAPIキー
```

2) `app.py` を作成（最小版の例）

```python
import os
import time
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("BRAVE_API_KEY")
ENDPOINT = "https://api.search.brave.com/res/v1/web/search"

st.set_page_config(page_title="Brave Web Search", page_icon="🔎", layout="wide")
st.title("Brave Search API を使ったWeb検索")

if not API_KEY:
    st.error("環境変数 BRAVE_API_KEY が設定されていません。")
    st.stop()

query = st.text_input("検索ワード", placeholder="例: Streamlit Brave Search API")
col1, col2, col3 = st.columns([1,1,1])
with col1:
    count = st.number_input("件数", min_value=1, max_value=50, value=10, step=1)
with col2:
    lang = st.selectbox("検索言語(search_lang)", ["ja", "en"], index=0)
with col3:
    safesearch = st.selectbox("セーフサーチ", ["off", "moderate", "strict"], index=1)

do_search = st.button("検索")

def brave_search(q: str, *, count: int = 10, search_lang: str = "ja", safesearch: str = "moderate", retries: int = 2):
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": API_KEY,
    }
    params = {
        "q": q,
        "count": count,
        "search_lang": search_lang,
        "safesearch": safesearch,
    }
    backoff = 1.0
    for attempt in range(retries + 1):
        resp = requests.get(ENDPOINT, headers=headers, params=params, timeout=15)
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code in (429, 502, 503, 504) and attempt < retries:
            time.sleep(backoff)
            backoff *= 2
            continue
        st.error(f"APIエラー: status={resp.status_code} body={resp.text[:300]}")
        return None
    return None

if do_search and query:
    with st.spinner("検索中..."):
        data = brave_search(query, count=count, search_lang=lang, safesearch=safesearch)
    if not data:
        st.stop()
    results = (data.get("web") or {}).get("results") or []
    st.write(f"件数: {len(results)}")
    for item in results:
        title = item.get("title") or "(no title)"
        url = item.get("url") or ""
        desc = item.get("description") or ""
        st.markdown(f"### [{title}]({url})")
        if desc:
            st.write(desc)
        st.divider()
elif do_search and not query:
    st.warning("検索ワードを入力してください。")
```

3) 起動

```bash
streamlit run app.py
```

### 7. 応用トピック
- **ページング**: `offset` を使って次ページ取得（UIに「次へ」ボタンを用意）
- **言語/地域最適化**: `search_lang=ja`, `country=jp` を指定
- **鮮度フィルタ**: `freshness` を指定（ニュース性の高い用途で有効）
- **サジェスト**: `/res/v1/suggest` を用いると入力補助が可能
- **画像/動画/ニュース**: エンドポイントを切り替えて同様に取得

### 8. 運用上の注意
- **キーの秘匿**: `.env` / Streamlit Secrets / CIのシークレットを利用
- **リトライ/タイムアウト**: 一時的な失敗に備える
- **キャッシング**: 重複クエリの負荷・コスト削減（例: `st.cache_data`）
- **利用規約遵守**: API利用規約・表示要件を遵守

---
最終更新: 2025-09-29


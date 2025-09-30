import os
import streamlit as st
from dotenv import load_dotenv

from modules.brave_search import BraveSearchClient
from modules.chat_handler import ChatHandler
from modules.utils import (
    initialize_session_state, 
    add_message_to_chat, 
    clear_chat_history,
    clear_search_results,
    format_search_results_for_display,
    validate_api_keys,
    get_message_count,
    create_status_message
)

# 環境変数の読み込み
load_dotenv()

# ページ設定
st.set_page_config(
    page_title="Brave Search × AI Chat", 
    page_icon="🔍🤖", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# セッション状態の初期化
initialize_session_state()

# メインタイトル
st.title("🔍🤖 Brave Search × AI Chat")
st.markdown("Web検索とAIチャットを組み合わせた統合アプリケーション")

# API設定の確認
brave_api_key = os.getenv("BRAVE_API_KEY")
openai_api_key = os.getenv("OPENAI_API_KEY")

# APIキーの検証
if not brave_api_key or not openai_api_key:
    st.error("⚠️ APIキーが設定されていません。")
    st.markdown("""
    ### 🔧 設定方法
    1. `.env` ファイルを作成してください
    2. 以下の内容を記述してください：
    ```
    BRAVE_API_KEY=your_brave_api_key_here
    OPENAI_API_KEY=your_openai_api_key_here
    OPENAI_MODEL=gpt-3.5-turbo
    MAX_TOKENS=1000
    TEMPERATURE=0.7
    ```
    """)
    st.stop()

api_valid, error_message = validate_api_keys(brave_api_key, openai_api_key)

if not api_valid:
    st.error(f"⚠️ {error_message}")
    st.markdown("""
    ### 🔧 設定方法
    1. `.env` ファイルを作成してください
    2. 以下の内容を記述してください：
    ```
    BRAVE_API_KEY=your_brave_api_key_here
    OPENAI_API_KEY=your_openai_api_key_here
    OPENAI_MODEL=gpt-3.5-turbo
    MAX_TOKENS=1000
    TEMPERATURE=0.7
    ```
    """)
    st.stop()

# クライアントの初期化
try:
    search_client = BraveSearchClient(brave_api_key)
    chat_handler = ChatHandler(openai_api_key, os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"))
except Exception as e:
    st.error(f"⚠️ クライアントの初期化に失敗しました: {str(e)}")
    st.stop()

# サイドバー設定
with st.sidebar:
    st.header("⚙️ 設定")
    
    # アプリケーションモード
    app_mode = st.selectbox(
        "🎯 アプリケーションモード",
        ["🤖 AI Chat（検索連携）", "🔍 Web検索", "📋 両方表示"],
        help="メインの使用モードを選択してください"
    )
    
    st.divider()
    
    # 検索設定
    st.subheader("🔍 検索設定")
    search_lang = st.selectbox(
        "検索言語", 
        ["auto（自動）", "ja（日本語）", "en（英語）"], 
        index=0,
        help="検索結果の言語設定"
    )
    # 実際のパラメータ値に変換
    search_lang_map = {
        "auto（自動）": "auto",
        "ja（日本語）": "ja", 
        "en（英語）": "en"
    }
    actual_search_lang = search_lang_map[search_lang]
    
    safesearch = st.selectbox("セーフサーチ", ["moderate", "off", "strict"], index=0)
    max_results = st.slider("最大検索結果数", 3, 20, 10)
    
    # 検索結果の詳細度設定
    search_detail_level = st.selectbox(
        "検索結果の詳細度", 
        ["詳細（推奨）", "シンプル"], 
        index=0,
        help="AIに送る検索結果の詳細度を選択"
    )
    
    # 新鮮度フィルタ
    freshness = st.selectbox(
        "新鮮度フィルタ", 
        ["なし", "過去24時間", "過去週", "過去月", "過去年"],
        help="検索結果の新しさを制限します"
    )
    
    freshness_map = {
        "なし": None,
        "過去24時間": "pd",
        "過去週": "pw", 
        "過去月": "pm",
        "過去年": "py"
    }
    
    st.divider()
    
    # チャット設定
    st.subheader("🤖 チャット設定")
    auto_search = st.checkbox(
        "自動検索モード", 
        value=True, 
        help="メッセージ内容に基づいて自動的に検索を実行"
    )
    
    # モデル情報
    model_info = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
    st.info(f"使用モデル: {model_info}")
    
    st.divider()
    
    # 統計情報
    st.subheader("📊 統計")
    st.metric("チャットメッセージ数", get_message_count())
    if st.session_state.search_results:
        results_count = len(st.session_state.search_results.get("web", {}).get("results", []))
        st.metric("最新検索結果数", results_count)
    
    st.divider()
    
    # 操作ボタン
    st.subheader("🔧 操作")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗑️ チャットクリア", use_container_width=True):
            clear_chat_history()
            st.rerun()
    
    with col2:
        if st.button("🔍 検索クリア", use_container_width=True):
            clear_search_results()
            st.rerun()

# メイン画面のレイアウト
if app_mode == "📋 両方表示":
    chat_col, search_col = st.columns([1.2, 0.8])
    chat_container = chat_col
    search_container = search_col
else:
    chat_container = st.container()
    search_container = st.container()

# チャット機能
if app_mode in ["🤖 AI Chat（検索連携）", "📋 両方表示"]:
    with chat_container:
        if app_mode == "📋 両方表示":
            st.subheader("🤖 AI チャット")
        else:
            st.header("🤖 AI チャット")
        
        # チャット履歴の表示
        chat_area = st.container()
        with chat_area:
            if not st.session_state.chat_messages:
                st.info("👋 こんにちは！何でもお聞きください。必要に応じて最新情報を検索してお答えします。")
            
            for message in st.session_state.chat_messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])
        
        # ユーザー入力
        if prompt := st.chat_input("メッセージを入力してください..."):
            # ユーザーメッセージを表示・保存
            with st.chat_message("user"):
                st.markdown(prompt)
            add_message_to_chat("user", prompt)
            
            # アシスタント応答の処理
            with st.chat_message("assistant"):
                response_placeholder = st.empty()
                
                # 検索が必要かどうか判定
                search_context = None
                if auto_search and chat_handler.should_search(prompt):
                    with st.status("🔍 検索中...", expanded=False) as status:
                        search_query = chat_handler.extract_search_query(prompt)
                        st.write(f"検索クエリ: {search_query}")
                        
                        # 検索実行
                        search_kwargs = {
                            "search_lang": actual_search_lang,
                            "safesearch": safesearch
                        }
                        freshness_value = freshness_map[freshness]
                        if freshness_value:
                            search_kwargs["freshness"] = freshness_value
                        
                        search_data = search_client.search_with_retry(
                            search_query,
                            count=min(max_results, 8),  # チャット用は件数制限
                            retries=2,
                            **search_kwargs
                        )
                        
                        if search_data and "error" not in search_data:
                            # 詳細度設定に応じて検索コンテキストを生成
                            if search_detail_level == "詳細（推奨）":
                                search_context = search_client.format_results_for_llm(search_data)
                            else:
                                search_context = search_client.format_results_for_llm_simple(search_data)
                            
                            st.session_state.search_results = search_data
                            st.session_state.current_search_query = search_query
                            
                            results_count = len(search_data.get("web", {}).get("results", []))
                            st.write(f"✅ {results_count}件の検索結果を取得しました")
                            status.update(label="🔍 検索完了", state="complete")
                        else:
                            st.write("⚠️ 検索に失敗しました")
                            status.update(label="🔍 検索失敗", state="error")
                
                # AIレスポンス生成
                with st.spinner("🤖 回答を生成中..."):
                    try:
                        response = chat_handler.get_response_with_retry(
                            st.session_state.chat_messages,
                            search_context
                        )
                        response_placeholder.markdown(response)
                    except Exception as e:
                        error_msg = f"⚠️ 応答生成エラー: {str(e)}"
                        response_placeholder.markdown(error_msg)
                        response = error_msg
            
            add_message_to_chat("assistant", response)

# 検索機能
if app_mode in ["🔍 Web検索", "📋 両方表示"]:
    with search_container:
        if app_mode == "📋 両方表示":
            st.subheader("🔍 Web検索")
        else:
            st.header("🔍 Web検索")
        
        # 検索フォーム
        search_form = st.form("search_form", clear_on_submit=False)
        with search_form:
            search_query = st.text_input(
                "検索クエリ", 
                value=st.session_state.current_search_query,
                placeholder="検索したいキーワードを入力...",
                help="例: Python プログラミング, 最新ニュース, 今日の天気"
            )
            
            col_search, col_clear = st.columns([3, 1])
            with col_search:
                do_search = st.form_submit_button("🔍 検索実行", type="primary", use_container_width=True)
            with col_clear:
                if st.form_submit_button("🗑️ 結果クリア", use_container_width=True):
                    clear_search_results()
                    st.rerun()
        
        # 検索実行
        if do_search and search_query:
            with st.spinner("🔍 検索中..."):
                # 検索パラメータの設定
                search_kwargs = {
                    "search_lang": actual_search_lang,
                    "safesearch": safesearch
                }
                freshness_value = freshness_map[freshness]
                if freshness_value:
                    search_kwargs["freshness"] = freshness_value
                
                search_data = search_client.search_with_retry(
                    search_query,
                    count=max_results,
                    retries=2,
                    **search_kwargs
                )
                
                if search_data:
                    st.session_state.search_results = search_data
                    st.session_state.current_search_query = search_query
        
        # 検索結果表示
        if st.session_state.search_results:
            if "error" in st.session_state.search_results:
                st.error(f"🚫 検索エラー: {st.session_state.search_results['error']}")
            else:
                # 検索結果の表示
                results_markdown = format_search_results_for_display(st.session_state.search_results)
                st.markdown(results_markdown)
                
                # チャットに結果を送信するボタン（両方表示モードの場合）
                if app_mode == "📋 両方表示":
                    if st.button("💬 この検索結果についてAIに質問", use_container_width=True):
                        question = f"「{st.session_state.current_search_query}」について、検索結果を踏まえて説明してください。"
                        add_message_to_chat("user", question)
                        
                        # 検索コンテキストを作成
                        search_context = search_client.format_results_for_llm(st.session_state.search_results)
                        
                        # AI応答生成
                        with st.spinner("🤖 AIが回答を生成中..."):
                            response = chat_handler.get_response_with_retry(
                                st.session_state.chat_messages,
                                search_context
                            )
                            add_message_to_chat("assistant", response)
                        
                        st.success("✅ AIの回答をチャットに追加しました！")
                        st.rerun()

# フッター
st.markdown("---")

# 使い方ガイド
with st.expander("📖 使い方ガイド", expanded=False):
    st.markdown("""
    ### 🤖 AI Chat（検索連携）モード
    - チャットで質問すると、必要に応じて自動的に検索が実行されます
    - 最新情報を基にAIが回答します
    - 「最新の〜」「今日の〜」「〜について教えて」などで検索が起動します
    
    ### 🔍 Web検索モード
    - 直接キーワード検索ができます
    - 検索言語、セーフサーチ、新鮮度フィルタが設定できます
    
    ### 📋 両方表示モード  
    - チャットと検索を同時に使用できます
    - 検索結果を簡単にAIチャットに送信できます
    
    ### ⚙️ 設定のコツ
    - **自動検索**: チャット内容に応じて自動検索する機能
    - **新鮮度フィルタ**: ニュースや最新情報検索時に有効
    - **最大検索結果数**: 多くすると詳細、少なくすると高速
    """)

# バージョン情報
st.caption("Brave Search × AI Chat v1.0 | Built with Streamlit")



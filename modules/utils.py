import streamlit as st
from typing import List, Dict, Optional
from datetime import datetime
import json


def initialize_session_state():
    """セッション状態の初期化"""
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    
    if "search_results" not in st.session_state:
        st.session_state.search_results = None
    
    if "current_search_query" not in st.session_state:
        st.session_state.current_search_query = ""
    
    if "auto_search_enabled" not in st.session_state:
        st.session_state.auto_search_enabled = True


def add_message_to_chat(role: str, content: str):
    """
    チャット履歴にメッセージを追加
    
    Args:
        role: メッセージの送信者（"user" または "assistant"）
        content: メッセージ内容
    """
    message = {
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat()
    }
    st.session_state.chat_messages.append(message)


def clear_chat_history():
    """チャット履歴をクリア"""
    st.session_state.chat_messages = []


def clear_search_results():
    """検索結果をクリア"""
    st.session_state.search_results = None
    st.session_state.current_search_query = ""


def format_search_results_for_display(search_data: dict) -> str:
    """
    検索結果を表示用に整形
    
    Args:
        search_data: Brave Search APIからの検索結果
    
    Returns:
        Markdown形式で整形された検索結果
    """
    if not search_data or "web" not in search_data:
        return "🔍 検索結果が見つかりませんでした。"
    
    results = search_data.get("web", {}).get("results", [])
    if not results:
        return "🔍 検索結果が見つかりませんでした。"
    
    # 検索クエリ情報
    query_info = search_data.get("query", {})
    original_query = query_info.get("original", "")
    
    formatted = f"### 🔍 検索結果: \"{original_query}\" ({len(results)}件)\n\n"
    
    for i, result in enumerate(results, 1):
        title = result.get("title", "タイトルなし")
        url = result.get("url", "")
        description = result.get("description", "説明なし")
        
        # 長すぎる説明は切り詰める
        if len(description) > 150:
            description = description[:150] + "..."
        
        formatted += f"**{i}. [{title}]({url})**\n"
        formatted += f"{description}\n\n"
    
    return formatted


def get_search_summary(search_data: dict) -> str:
    """
    検索結果の要約情報を取得
    
    Args:
        search_data: Brave Search APIからの検索結果
    
    Returns:
        検索結果の要約テキスト
    """
    if not search_data or "web" not in search_data:
        return "検索結果なし"
    
    results = search_data.get("web", {}).get("results", [])
    query_info = search_data.get("query", {})
    original_query = query_info.get("original", "")
    
    return f"「{original_query}」の検索結果 {len(results)}件"


def save_chat_history(filename: Optional[str] = None) -> str:
    """
    チャット履歴をJSONファイルに保存
    
    Args:
        filename: 保存ファイル名（省略時は自動生成）
    
    Returns:
        保存されたファイル名
    """
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"chat_history_{timestamp}.json"
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(st.session_state.chat_messages, f, ensure_ascii=False, indent=2)
        return filename
    except Exception as e:
        st.error(f"チャット履歴の保存に失敗しました: {str(e)}")
        return ""


def load_chat_history(filename: str) -> bool:
    """
    チャット履歴をJSONファイルから読み込み
    
    Args:
        filename: 読み込みファイル名
    
    Returns:
        読み込み成功の可否
    """
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            st.session_state.chat_messages = json.load(f)
        return True
    except FileNotFoundError:
        st.error(f"ファイル '{filename}' が見つかりません。")
        return False
    except json.JSONDecodeError:
        st.error(f"ファイル '{filename}' の形式が正しくありません。")
        return False
    except Exception as e:
        st.error(f"チャット履歴の読み込みに失敗しました: {str(e)}")
        return False


def validate_api_keys(brave_key: str, openai_key: str) -> tuple[bool, str]:
    """
    APIキーの有効性を検証
    
    Args:
        brave_key: Brave Search APIキー
        openai_key: OpenAI APIキー
    
    Returns:
        (有効性, エラーメッセージ)
    """
    if not brave_key:
        return False, "BRAVE_API_KEY が設定されていません。"
    
    if not openai_key:
        return False, "OPENAI_API_KEY が設定されていません。"
    
    # 基本的な形式チェック
    if len(brave_key) < 10:
        return False, "BRAVE_API_KEY の形式が正しくない可能性があります。"
    
    if not openai_key.startswith(("sk-", "sk-proj-")):
        return False, "OPENAI_API_KEY の形式が正しくない可能性があります。"
    
    return True, ""


def create_status_message(status: str, message: str) -> None:
    """
    ステータスメッセージを表示
    
    Args:
        status: ステータスタイプ（"info", "success", "warning", "error"）
        message: 表示メッセージ
    """
    if status == "info":
        st.info(message)
    elif status == "success":
        st.success(message)
    elif status == "warning":
        st.warning(message)
    elif status == "error":
        st.error(message)
    else:
        st.write(message)


def get_message_count() -> int:
    """
    現在のチャットメッセージ数を取得
    
    Returns:
        メッセージ数
    """
    return len(st.session_state.chat_messages)


def get_last_user_message() -> Optional[str]:
    """
    最後のユーザーメッセージを取得
    
    Returns:
        最後のユーザーメッセージまたはNone
    """
    for message in reversed(st.session_state.chat_messages):
        if message.get("role") == "user":
            return message.get("content")
    return None


def truncate_text(text: str, max_length: int = 100) -> str:
    """
    テキストを指定長で切り詰める
    
    Args:
        text: 対象テキスト
        max_length: 最大文字数
    
    Returns:
        切り詰められたテキスト
    """
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


def format_timestamp(timestamp_str: str) -> str:
    """
    タイムスタンプを読みやすい形式に変換
    
    Args:
        timestamp_str: ISO形式のタイムスタンプ文字列
    
    Returns:
        読みやすい形式のタイムスタンプ
    """
    try:
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        return dt.strftime("%H:%M:%S")
    except (ValueError, AttributeError):
        return ""

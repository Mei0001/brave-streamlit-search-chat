import os
import time
import openai
from typing import List, Dict, Optional
import streamlit as st

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False


class ChatHandler:
    """OpenAI APIを使用したチャット処理クラス"""
    
    def __init__(self, api_key: str, model: str = "gpt-3.5-turbo"):
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model
        self.max_tokens = int(os.getenv("MAX_TOKENS", "1000"))
        self.temperature = float(os.getenv("TEMPERATURE", "0.7"))
        
    def get_response(self, messages: List[Dict], search_context: Optional[str] = None) -> str:
        """
        LLMからの応答を取得
        
        Args:
            messages: チャット履歴のメッセージリスト
            search_context: 検索結果のコンテキスト（オプション）
        
        Returns:
            LLMからの応答テキスト
        """
        try:
            # システムメッセージの作成
            system_message = {
                "role": "system",
                "content": "あなたは親切で知識豊富なAIアシスタントです。日本語で丁寧に回答してください。"
            }
            
            # 検索コンテキストがある場合、システムメッセージに追加
            if search_context:
                # 検索コンテキストのトークン数を制限
                context_token_limit = 2000  # 検索結果用のトークン制限
                if TIKTOKEN_AVAILABLE and self.count_tokens(search_context) > context_token_limit:
                    # トークン制限を超える場合は切り詰め
                    lines = search_context.split('\n')
                    truncated_context = ""
                    for line in lines:
                        test_context = truncated_context + line + '\n'
                        if self.count_tokens(test_context) > context_token_limit:
                            break
                        truncated_context = test_context
                    search_context = truncated_context + "\n[検索結果が長いため一部を省略しました]"
                
                system_message["content"] += f"\n\n以下の最新の検索結果を参考にして回答してください：\n{search_context}"
            
            # メッセージリストの先頭にシステムメッセージを追加
            full_messages = [system_message] + messages
            
            # トークン数制限のチェック
            if TIKTOKEN_AVAILABLE:
                total_tokens = sum(self.count_tokens(msg.get("content", "")) for msg in full_messages)
                if total_tokens > 4000:  # 検索情報を考慮してトークン制限を拡大
                    # 古いメッセージを削除してトークン数を調整
                    full_messages = self._trim_messages(full_messages, 4000)
            
            # gpt-5系モデルは推論モデルでtemperatureパラメータをサポートしていない
            api_params = {
                "model": self.model,
                "messages": full_messages,
                "max_completion_tokens": self.max_tokens,
                "stream": False
            }
            
            # gpt-5系以外のモデルの場合のみtemperatureを追加
            if not self.model.startswith("gpt-5"):
                api_params["temperature"] = self.temperature
            
            response = self.client.chat.completions.create(**api_params)
            
            # デバッグ情報を追加
            if not response.choices:
                return "⚠️ APIレスポンスにchoicesが含まれていません。"
            
            choice = response.choices[0]
            if not choice.message:
                return "⚠️ APIレスポンスにmessageが含まれていません。"
                
            content = choice.message.content
            if content is None:
                return f"⚠️ APIレスポンスのcontentがNoneです。finish_reason: {choice.finish_reason}"
            
            if not content.strip():
                return "⚠️ APIレスポンスが空の文字列です。"
            
            return content
            
        except openai.RateLimitError:
            return "⚠️ APIのレート制限に達しました。しばらく待ってから再試行してください。"
        except openai.AuthenticationError:
            return "⚠️ OpenAI APIキーが無効です。設定を確認してください。"
        except openai.APIError as e:
            return f"⚠️ OpenAI APIエラー: {str(e)}"
        except Exception as e:
            return f"⚠️ 予期しないエラーが発生しました: {str(e)}"
    
    def get_response_with_retry(self, messages: List[Dict], search_context: Optional[str] = None, retries: int = 3) -> str:
        """
        リトライ機能付きでLLMからの応答を取得
        
        Args:
            messages: チャット履歴のメッセージリスト
            search_context: 検索結果のコンテキスト（オプション）
            retries: リトライ回数
        
        Returns:
            LLMからの応答テキスト
        """
        for attempt in range(retries):
            try:
                return self.get_response(messages, search_context)
            except openai.RateLimitError:
                if attempt < retries - 1:
                    wait_time = 2 ** attempt  # 指数バックオフ
                    time.sleep(wait_time)
                    continue
                return "⚠️ レート制限に達しました。しばらく待ってから再試行してください。"
            except Exception as e:
                if attempt < retries - 1:
                    time.sleep(1)
                    continue
                return f"⚠️ 複数回試行しましたが、エラーが発生しました: {str(e)}"
        
        # すべてのリトライが失敗した場合のフォールバック
        return "⚠️ 応答の生成に失敗しました。時間をおいて再試行してください。"
    
    def should_search(self, user_message: str) -> bool:
        """
        ユーザーメッセージが検索を必要とするかを判定
        
        Args:
            user_message: ユーザーのメッセージ
        
        Returns:
            検索が必要かどうかのブール値
        """
        search_keywords = [
            "検索", "調べて", "探して", "最新", "ニュース", "情報", 
            "について教えて", "とは", "方法", "やり方", "どうやって",
            "いつ", "どこ", "誰", "なぜ", "何", "現在", "今", "今日",
            "2024", "2025", "最近", "今年", "今月", "今週"
        ]
        
        # キーワードマッチング
        message_lower = user_message.lower()
        for keyword in search_keywords:
            if keyword in message_lower:
                return True
        
        # 疑問文の検出
        question_patterns = ["？", "?", "教えて", "知りたい", "分からない"]
        for pattern in question_patterns:
            if pattern in user_message:
                return True
        
        return False
    
    def extract_search_query(self, user_message: str) -> str:
        """
        ユーザーメッセージから検索クエリを抽出
        
        Args:
            user_message: ユーザーのメッセージ
        
        Returns:
            検索クエリ文字列
        """
        # 不要な言葉を除去
        remove_phrases = [
            "検索して", "調べて", "探して", "について教えて", 
            "とは何ですか", "を教えて", "について知りたい",
            "どうですか", "はどう", "？", "?"
        ]
        
        query = user_message
        for phrase in remove_phrases:
            query = query.replace(phrase, "")
        
        # 余分な空白を除去
        query = " ".join(query.split())
        
        # 空の場合は元のメッセージを使用
        return query.strip() or user_message.strip()
    
    def count_tokens(self, text: str) -> int:
        """
        テキストのトークン数をカウント
        
        Args:
            text: カウント対象のテキスト
        
        Returns:
            トークン数
        """
        if not TIKTOKEN_AVAILABLE:
            # tiktokenが利用できない場合の簡易計算
            return len(text) // 4
        
        try:
            encoding = tiktoken.encoding_for_model(self.model)
            return len(encoding.encode(text))
        except Exception:
            # フォールバック
            return len(text) // 4
    
    def _trim_messages(self, messages: List[Dict], max_tokens: int) -> List[Dict]:
        """
        メッセージリストをトークン制限内に収める
        
        Args:
            messages: メッセージリスト
            max_tokens: 最大トークン数
        
        Returns:
            トークン制限内に収められたメッセージリスト
        """
        if len(messages) <= 1:  # システムメッセージのみの場合
            return messages
        
        # システムメッセージは保持
        system_message = messages[0]
        conversation_messages = messages[1:]
        
        # 最新のメッセージから逆順でトークン数を計算
        current_tokens = self.count_tokens(system_message.get("content", ""))
        trimmed_messages = [system_message]
        
        for message in reversed(conversation_messages):
            message_tokens = self.count_tokens(message.get("content", ""))
            if current_tokens + message_tokens > max_tokens:
                break
            current_tokens += message_tokens
            trimmed_messages.insert(1, message)  # システムメッセージの後に挿入
        
        return trimmed_messages

import os
import time
import requests  # type: ignore
from typing import Dict, List, Optional
import streamlit as st


class BraveSearchClient:
    """Brave Search APIのクライアントクラス"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.endpoint = "https://api.search.brave.com/res/v1/web/search"
    
    def search(self, query: str, count: int = 10, **kwargs) -> Optional[Dict]:
        """
        Web検索を実行
        
        Args:
            query: 検索クエリ
            count: 取得件数
            **kwargs: その他のパラメータ (search_lang, safesearch, etc.)
        
        Returns:
            検索結果のJSONデータまたはNone
        """
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": self.api_key,
        }
        params = {
            "q": query,
            "count": count,
            "safesearch": kwargs.get("safesearch", "moderate"),
        }
        
        # search_langパラメータは問題が報告されているため、条件付きで追加
        search_lang = kwargs.get("search_lang")
        if search_lang and search_lang not in ["auto", ""]:
            params["search_lang"] = search_lang
        
        # オプションパラメータの追加
        if "country" in kwargs:
            params["country"] = kwargs["country"]
        if "freshness" in kwargs:
            params["freshness"] = kwargs["freshness"]
        
        try:
            response = requests.get(
                self.endpoint, 
                headers=headers, 
                params=params, 
                timeout=15
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                error_msg = f"HTTP {response.status_code}: {response.text[:300]}"
                st.error(f"検索APIエラー: {error_msg}")
                return {"error": error_msg}
                
        except requests.exceptions.Timeout:
            error_msg = "検索リクエストがタイムアウトしました"
            st.error(error_msg)
            return {"error": error_msg}
        except requests.exceptions.ConnectionError:
            error_msg = "検索APIに接続できませんでした"
            st.error(error_msg)
            return {"error": error_msg}
        except Exception as e:
            error_msg = f"予期しないエラー: {str(e)}"
            st.error(error_msg)
            return {"error": error_msg}
    
    def format_results_for_llm(self, search_data: Dict) -> str:
        """
        検索結果をLLM用のテキストに詳細整形（タイトル、URL、スニペット、追加情報含む）
        
        Args:
            search_data: 検索結果のJSONデータ
        
        Returns:
            LLM用に詳細整形されたテキスト
        """
        if not search_data or "web" not in search_data:
            return "検索結果が見つかりませんでした。"
        
        web_data = search_data.get("web", {})
        results = web_data.get("results", [])
        if not results:
            return "検索結果が見つかりませんでした。"
        
        # 検索クエリ情報
        query_info = search_data.get("query", {})
        original_query = query_info.get("original", "")
        
        formatted_results = []
        formatted_results.append(f"検索クエリ: {original_query}")
        formatted_results.append(f"検索結果数: {len(results)}件")
        formatted_results.append("=" * 50)
        
        for i, result in enumerate(results[:8], 1):  # 上位8件まで詳細表示
            # 基本情報
            title = result.get("title", "タイトルなし")
            url = result.get("url", "")
            description = result.get("description", "")
            
            # メタ情報
            age = result.get("age", "")
            language = result.get("language", "")
            page_age = result.get("page_age", "")
            
            # URL詳細情報
            meta_url = result.get("meta_url", {})
            hostname = meta_url.get("hostname", "")
            favicon = meta_url.get("favicon", "")
            
            # 追加スニペット情報
            extra_snippets = result.get("extra_snippets", [])
            
            # 構造化データ情報
            schemas = result.get("schemas", [])
            content_type = result.get("content_type", "")
            
            # リッチ結果情報
            article_info = result.get("article", {})
            rating_info = result.get("rating", {})
            video_info = result.get("video", {})
            
            # 結果の整形
            result_text = f"\n【結果 {i}】"
            result_text += f"\nタイトル: {title}"
            result_text += f"\nURL: {url}"
            if hostname:
                result_text += f"\nサイト: {hostname}"
            
            # メイン説明文
            if description:
                # 長すぎる説明文は切り詰めるが、より長く保持
                if len(description) > 300:
                    description = description[:300] + "..."
                result_text += f"\n説明: {description}"
            
            # 追加スニペット
            if extra_snippets:
                snippets_text = " | ".join(extra_snippets[:3])  # 最大3つ
                if len(snippets_text) > 200:
                    snippets_text = snippets_text[:200] + "..."
                result_text += f"\n追加情報: {snippets_text}"
            
            # 時間情報
            if age:
                result_text += f"\n更新時期: {age}"
            
            # コンテンツタイプ
            if content_type:
                result_text += f"\nコンテンツタイプ: {content_type}"
            
            # 記事情報
            if article_info:
                author = article_info.get("author", [])
                date = article_info.get("date", "")
                if author and isinstance(author, list) and len(author) > 0:
                    author_name = author[0].get("name", "")
                    if author_name:
                        result_text += f"\n著者: {author_name}"
                if date:
                    result_text += f"\n公開日: {date}"
            
            # 評価情報
            if rating_info:
                rating_value = rating_info.get("ratingValue", "")
                review_count = rating_info.get("reviewCount", "")
                if rating_value:
                    result_text += f"\n評価: {rating_value}"
                    if review_count:
                        result_text += f" ({review_count}件のレビュー)"
            
            # 動画情報
            if video_info:
                duration = video_info.get("duration", "")
                views = video_info.get("views", "")
                if duration:
                    result_text += f"\n動画時間: {duration}"
                if views:
                    result_text += f"\n再生回数: {views}"
            
            # 構造化データ情報（要約）
            if schemas:
                schema_types = []
                for schema in schemas[:3]:  # 最大3つ
                    if isinstance(schema, dict) and "@type" in schema:
                        schema_types.append(schema["@type"])
                if schema_types:
                    result_text += f"\n構造化データ: {', '.join(schema_types)}"
            
            formatted_results.append(result_text)
        
        return "\n".join(formatted_results)
    
    def format_results_for_llm_simple(self, search_data: Dict) -> str:
        """
        検索結果をLLM用に簡潔整形（従来版との互換性用）
        
        Args:
            search_data: 検索結果のJSONデータ
        
        Returns:
            LLM用に簡潔整形されたテキスト
        """
        if not search_data or "web" not in search_data:
            return "検索結果が見つかりませんでした。"
        
        results = search_data.get("web", {}).get("results", [])
        if not results:
            return "検索結果が見つかりませんでした。"
        
        formatted_results = []
        for i, result in enumerate(results[:5], 1):  # 上位5件のみ
            title = result.get("title", "タイトルなし")
            url = result.get("url", "")
            description = result.get("description", "説明なし")
            
            # 長すぎる説明文は切り詰める
            if len(description) > 200:
                description = description[:200] + "..."
            
            formatted_results.append(
                f"{i}. {title}\n"
                f"URL: {url}\n"
                f"概要: {description}\n"
            )
        
        return "検索結果:\n" + "\n".join(formatted_results)
    
    def search_with_retry(self, query: str, count: int = 10, retries: int = 2, **kwargs) -> Optional[Dict]:
        """
        リトライ機能付きの検索
        
        Args:
            query: 検索クエリ
            count: 取得件数
            retries: リトライ回数
            **kwargs: その他のパラメータ
        
        Returns:
            検索結果のJSONデータまたはNone
        """
        backoff = 1.0
        
        for attempt in range(retries + 1):
            result = self.search(query, count, **kwargs)
            
            if not result or "error" not in result:
                return result
            
            # リトライ可能なエラーの場合
            error_msg = result.get("error", "")
            if "429" in error_msg or "502" in error_msg or "503" in error_msg or "504" in error_msg:
                if attempt < retries:
                    time.sleep(backoff)
                    backoff *= 2
                    continue
            
            # リトライできないエラーの場合は即座に返す
            return result
        
        return {"error": "最大リトライ回数に達しました"}

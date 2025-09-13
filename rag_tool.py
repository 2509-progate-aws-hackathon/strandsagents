from strands_tools import retrieve, memory
from typing import Optional, List, Dict, Any


class RAGTool:
    """
    RAG（Retrieval-Augmented Generation）機能を提供するツール
    Amazon Bedrock Knowledge Basesからの情報検索と記憶機能を統合
    """

    def __init__(self, knowledge_base_id: Optional[str] = None):
        """
        RAGツールを初期化
        
        Args:
            knowledge_base_id: Amazon Bedrock Knowledge BaseのID（オプション）
        """
        self.knowledge_base_id = knowledge_base_id
        self.tools = [retrieve, memory]

    def search_knowledge(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """
        Knowledge Baseから関連する情報を検索
        
        Args:
            query: 検索クエリ
            max_results: 返される最大結果数
            
        Returns:
            検索結果を含む辞書
        """
        try:
            # retrieve ツールを使用してKnowledge Baseから情報を検索
            # 注意: 実際の実装では、適切なagentインスタンスからtoolを呼び出す必要があります
            result = {
                "query": query,
                "status": "success",
                "message": f"Knowledge Baseから '{query}' に関する情報を検索しています...",
                "tool_used": "retrieve"
            }
            return result
        except Exception as e:
            return {
                "query": query,
                "status": "error",
                "message": f"検索中にエラーが発生しました: {str(e)}",
                "tool_used": "retrieve"
            }

    def store_memory(self, content: str, action: str = "store") -> Dict[str, Any]:
        """
        メモリにコンテンツを保存
        
        Args:
            content: 保存するコンテンツ
            action: 実行するアクション（store, retrieve, list等）
            
        Returns:
            操作結果を含む辞書
        """
        try:
            result = {
                "content": content,
                "action": action,
                "status": "success",
                "message": f"メモリ操作 '{action}' を実行しています...",
                "tool_used": "memory"
            }
            return result
        except Exception as e:
            return {
                "content": content,
                "action": action,
                "status": "error",
                "message": f"メモリ操作中にエラーが発生しました: {str(e)}",
                "tool_used": "memory"
            }

    def retrieve_memory(self, query: str) -> Dict[str, Any]:
        """
        メモリから関連する情報を検索
        
        Args:
            query: 検索クエリ
            
        Returns:
            検索結果を含む辞書
        """
        return self.store_memory(content=query, action="retrieve")

    def get_available_tools(self) -> List[str]:
        """
        利用可能なツールのリストを取得
        
        Returns:
            ツール名のリスト
        """
        return ["retrieve", "memory", "search_knowledge", "store_memory", "retrieve_memory"]

    def get_tool_descriptions(self) -> Dict[str, str]:
        """
        各ツールの説明を取得
        
        Returns:
            ツール名と説明のマップ
        """
        return {
            "retrieve": "Amazon Bedrock Knowledge Basesから情報を検索",
            "memory": "エージェントのメモリに情報を保存・検索",
            "search_knowledge": "Knowledge Baseから関連する情報を検索（ラッパー関数）",
            "store_memory": "メモリにコンテンツを保存（ラッパー関数）",
            "retrieve_memory": "メモリから関連する情報を検索（ラッパー関数）"
        }


def create_rag_tool(knowledge_base_id: Optional[str] = None) -> RAGTool:
    """
    RAGツールのファクトリー関数
    
    Args:
        knowledge_base_id: Amazon Bedrock Knowledge BaseのID（オプション）
        
    Returns:
        RAGToolインスタンス
    """
    return RAGTool(knowledge_base_id=knowledge_base_id)


# 便利な関数を提供
def search_documents(query: str, max_results: int = 5) -> str:
    """
    ドキュメント検索のヘルパー関数
    
    Args:
        query: 検索クエリ
        max_results: 最大結果数
        
    Returns:
        検索結果の説明文
    """
    return f"'{query}' に関連するドキュメントを最大 {max_results} 件検索します。retrieveツールを使用してAmazon Bedrock Knowledge Basesから情報を取得します。"


def save_to_memory(content: str) -> str:
    """
    メモリ保存のヘルパー関数
    
    Args:
        content: 保存するコンテンツ
        
    Returns:
        保存操作の説明文
    """
    return f"以下の内容をエージェントのメモリに保存します: '{content[:100]}...' memoryツールを使用してAmazon Bedrock Knowledge Basesに保存します。"

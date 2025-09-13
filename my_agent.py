from bedrock_agentcore.runtime import BedrockAgentCoreApp
import boto3
import json
import os
from botocore.exceptions import ClientError, NoCredentialsError
from botocore.config import Config

app = BedrockAgentCoreApp()

# 設定値
KNOWLEDGE_BASE_ID = os.environ.get("STRANDS_KNOWLEDGE_BASE_ID", "O8YQYDMUQB")
AWS_REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

# ログ出力
print(f"INFO: Knowledge Base ID = {KNOWLEDGE_BASE_ID}")
print(f"INFO: AWS Region = {AWS_REGION}")

def create_bedrock_clients():
    """BedrockAgentCore環境に最適化されたクライアント作成"""
    try:
        # AgentCore環境用の設定
        config = Config(
            retries={
                'max_attempts': 2,
                'mode': 'standard'
            },
            connect_timeout=30,
            read_timeout=120
        )
        
        # BedrockAgentCore環境では、IAMロールが自動的に使用される
        bedrock_agent = boto3.client(
            'bedrock-agent-runtime',
            region_name=AWS_REGION,
            config=config
        )
        
        bedrock_runtime = boto3.client(
            'bedrock-runtime',
            region_name=AWS_REGION,
            config=config
        )
        
        print("SUCCESS: Bedrockクライアント初期化完了")
        return bedrock_agent, bedrock_runtime
        
    except Exception as e:
        print(f"ERROR: クライアント初期化失敗: {e}")
        raise

def simple_knowledge_base_query(bedrock_agent, kb_id, query_text):
    """シンプルなナレッジベースクエリ"""
    try:
        print(f"INFO: ナレッジベースクエリ実行: '{query_text}'")
        
        response = bedrock_agent.retrieve(
            knowledgeBaseId=kb_id,
            retrievalQuery={'text': query_text},
            retrievalConfiguration={
                'vectorSearchConfiguration': {
                    'numberOfResults': 3
                }
            }
        )
        
        retrieval_results = response.get('retrievalResults', [])
        print(f"INFO: 検索結果数: {len(retrieval_results)}")
        
        if not retrieval_results:
            return "検索結果が見つかりませんでした。"
        
        # 結果を整形
        formatted_results = []
        for i, result in enumerate(retrieval_results[:10], 1):
            content = result.get('content', {}).get('text', '')
            score = result.get('score', 0)
            
            # ソース情報
            location = result.get('location', {})
            source = location.get('s3Location', {}).get('uri', 'Unknown')
            
            formatted_results.append(f"""
結果 {i} (関連度: {score:.2f}):
{content[:300]}...

ソース: {source}
""")
        
        return '\n'.join(formatted_results)
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'UnknownError')
        error_message = e.response.get('Error', {}).get('Message', str(e))
        
        print(f"ERROR: ナレッジベースクエリ失敗")
        print(f"  エラーコード: {error_code}")
        print(f"  エラーメッセージ: {error_message}")
        
        if error_code == 'ValidationException':
            if 'not able to call specified bedrock embedding model' in error_message:
                return "ナレッジベースの埋め込みモデルへのアクセス権限に問題があります。管理者にお問い合わせください。"
            else:
                return f"ナレッジベースの設定に問題があります: {error_message}"
        elif error_code == 'ResourceNotFoundException':
            return "指定されたナレッジベースまたはデータソースが見つかりません。"
        elif error_code == 'AccessDeniedException':
            return "ナレッジベースへのアクセス権限がありません。"
        else:
            return f"ナレッジベースクエリエラー: {error_message}"
            
    except Exception as e:
        print(f"ERROR: 予期しないエラー: {e}")
        return f"システムエラーが発生しました: {str(e)}"

def generate_response_with_claude(bedrock_runtime, user_query, knowledge_base_results):
    """Claude 3 Sonnetを使用して最終回答生成"""
    try:
        prompt = f"""
ユーザーの質問: {user_query}

ナレッジベースから取得した関連情報:
{knowledge_base_results}

上記の情報を基に、ユーザーの質問に対して日本語で分かりやすく回答してください。
情報が不十分な場合は、その旨を明確に伝えてください。
"""
        
        response = bedrock_runtime.invoke_model(
            modelId="anthropic.claude-3-sonnet-20240229-v1:0",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": prompt}]
            })
        )
        
        response_body = json.loads(response['body'].read())
        return response_body['content'][0]['text']
        
    except Exception as e:
        print(f"ERROR: Claude回答生成エラー: {e}")
        return knowledge_base_results  # フォールバック：検索結果をそのまま返す

@app.entrypoint
def invoke(payload):
    """メインエントリーポイント（簡素化版）"""
    try:
        user_message = payload.get("prompt", "").strip()
        
        if not user_message:
            return {"result": "質問を入力してください。"}
        
        print(f"INFO: ユーザー質問: {user_message}")
        
        # Bedrockクライアント作成
        bedrock_agent, bedrock_runtime = create_bedrock_clients()
        
        # ナレッジベース検索（シンプル版）
        search_results = simple_knowledge_base_query(
            bedrock_agent, 
            KNOWLEDGE_BASE_ID, 
            user_message
        )
        
        # エラーメッセージの場合はそのまま返す
        if "エラー" in search_results or "問題があります" in search_results:
            return {
                "result": search_results,
                "knowledge_base_id": KNOWLEDGE_BASE_ID,
                "status": "error"
            }
        
        # Claude 3を使用して最終回答生成
        final_answer = generate_response_with_claude(
            bedrock_runtime,
            user_message,
            search_results
        )
        
        return {
            "result": final_answer,
            "knowledge_base_id": KNOWLEDGE_BASE_ID,
            "status": "success"
        }
        
    except Exception as e:
        error_msg = f"アプリケーションエラー: {str(e)}"
        print(f"ERROR: {error_msg}")
        
        return {
            "result": "システム処理中にエラーが発生しました。しばらく時間をおいてから再度お試しください。",
            "error": error_msg,
            "status": "system_error"
        }

if __name__ == "__main__":
    app.run()

from bedrock_agentcore.runtime import BedrockAgentCoreApp
import boto3
import json
import os
import re
from botocore.exceptions import ClientError, NoCredentialsError
from botocore.config import Config

app = BedrockAgentCoreApp()

# 設定値
KNOWLEDGE_BASE_ID = os.environ.get("STRANDS_KNOWLEDGE_BASE_ID", "O8YQYDMUQB")
AWS_REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

print(f"INFO: Knowledge Base ID = {KNOWLEDGE_BASE_ID}")
print(f"INFO: AWS Region = {AWS_REGION}")

def create_bedrock_clients():
    """BedrockAgentCore環境に最適化されたクライアント作成"""
    try:
        config = Config(
            retries={
                'max_attempts': 2,
                'mode': 'standard'
            },
            connect_timeout=30,
            read_timeout=120
        )
        
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

def extract_structured_data_from_text(text_content):
    
    """テキストから構造化データを抽出"""
    structured_data = {
        "title": None,
        "longitude": None,
        "latitude": None,
        "other_fields": {}
    }
    
    try:
        # title の抽出（複数パターンに対応）
        title_patterns = [
            # 既存のパターン
            r'title[:\s]+([^\n\r,]+)',
            r'タイトル[:\s]+([^\n\r,]+)',
            r'件名[:\s]+([^\n\r,]+)',
            r'事故名[:\s]+([^\n\r,]+)',
            # 新規追加：データの末尾のタイトルを抽出
            r'(.+?)での(交通事故|交通障害事故|夜間事故)$',
            r'^(.+?)$' # 最後の行全体をタイトルとして試す
        ]
        
        # 緯度・経度抽出（カンマ区切りのデータ形式に対応）
        # 例: 2022/12/2 4:00,晴れ,西東京市柳沢１−１０,35.726,139.55391,...
        # このパターンは、文字列の最初の3つのカンマ区切りを探します
        lat_lon_match = re.search(r'[^,]+,[^,]+,[^,]+,([-]?\d+\.?\d*),([-]?\d+\.?\d*)', text_content)
        if lat_lon_match:
            try:
                structured_data["latitude"] = float(lat_lon_match.group(1))
                structured_data["longitude"] = float(lat_lon_match.group(2))
            except (ValueError, IndexError):
                pass
        
        # タイトル抽出
        lines = text_content.strip().split('\n')
        # 最後の行をタイトルとして試す
        if lines:
            last_line = lines[-1]
            for pattern in title_patterns:
                match = re.search(pattern, last_line, re.IGNORECASE)
                if match:
                    # 最初のグループが抽出対象
                    extracted_title = match.group(1).strip()
                    # 緯度経度データが抽出済みか確認
                    if structured_data["latitude"] and structured_data["longitude"]:
                        structured_data["title"] = extracted_title
                        break
                    else:
                        # 緯度経度がない場合は、titleに位置情報がないことを示す
                        structured_data["other_fields"]["note"] = f"タイトルが抽出されましたが、位置情報がありません: {extracted_title}"
                        break
        
    except Exception as e:
        print(f"WARNING: データ抽出中にエラー: {e}")
    
    return structured_data
def enhanced_knowledge_base_query(bedrock_agent, kb_id, query_text):
    """構造化データ対応のナレッジベースクエリ"""
    try:
        print(f"INFO: ナレッジベースクエリ実行: '{query_text}'")
        
        # ユーザーの質問に地理的な制約を明示的に追加
        # これにより、検索の精度が向上する可能性がある
        enhanced_query = f"{query_text} 東京都 事故 位置情報"

        response = bedrock_agent.retrieve(
            knowledgeBaseId=kb_id,
            retrievalQuery={'text': enhanced_query},  # 修正箇所
            retrievalConfiguration={
                'vectorSearchConfiguration': {
                    'numberOfResults': 20,
                    'overrideSearchType': 'HYBRID'
                }
            }
        )
        
        retrieval_results = response.get('retrievalResults', [])
        print(f"INFO: 検索結果数: {len(retrieval_results)}")
        
        if not retrieval_results:
            return {
                "message": "検索結果が見つかりませんでした。",
                "structured_data": [],
                "raw_results": []
            }
        
        # 構造化データと生の結果を両方保存
        structured_results = []
        raw_results = []
        
        for i, result in enumerate(retrieval_results, 1):
            content = result.get('content', {}).get('text', '')
            score = result.get('score', 0)
            location = result.get('location', {})
            source = location.get('s3Location', {}).get('uri', 'Unknown')
            
            # 構造化データ抽出
            structured_data = extract_structured_data_from_text(content)
            structured_data["score"] = score
            structured_data["source"] = source
            structured_data["result_index"] = i
            
            structured_results.append(structured_data)
            
            # 生の結果も保存
            raw_results.append({
                "index": i,
                "score": score,
                "content": content[:500] + "..." if len(content) > 500 else content,
                "source": source
            })
        
        return {
            "message": f"{len(retrieval_results)}件の事故データが見つかりました。",
            "structured_data": structured_results,
            "raw_results": raw_results
        }
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'UnknownError')
        error_message = e.response.get('Error', {}).get('Message', str(e))
        
        print(f"ERROR: ナレッジベースクエリ失敗")
        print(f"  エラーコード: {error_code}")
        print(f"  エラーメッセージ: {error_message}")
        
        error_responses = {
            'ValidationException': "ナレッジベースの設定に問題があります。",
            'ResourceNotFoundException': "指定されたナレッジベースまたはデータソースが見つかりません。",
            'AccessDeniedException': "ナレッジベースへのアクセス権限がありません。"
        }
        
        return {
            "message": error_responses.get(error_code, f"ナレッジベースクエリエラー: {error_message}"),
            "structured_data": [],
            "raw_results": [],
            "error": error_code
        }
            
    except Exception as e:
        print(f"ERROR: 予期しないエラー: {e}")
        return {
            "message": f"システムエラーが発生しました: {str(e)}",
            "structured_data": [],
            "raw_results": [],
            "error": "SystemError"
        }

def generate_enhanced_response(bedrock_runtime, user_query, query_results):
    """構造化データを含む高度な回答生成"""
    try:
        # 構造化データの有無を確認
        has_structured_data = any(
            result.get("title") or result.get("longitude") or result.get("latitude") 
            for result in query_results["structured_data"]
        )
        
        # 位置情報がある場合の処理
        location_data = []
        for result in query_results["structured_data"]:
            if result.get("longitude") and result.get("latitude"):
                location_data.append({
                    "title": result.get("title", "不明"),
                    "longitude": result["longitude"],
                    "latitude": result["latitude"],
                    "score": result.get("score", 0)
                })
        
        # プロンプト作成
        structured_info = ""
        if has_structured_data:
            structured_info = f"\n\n構造化されたデータ情報:\n{json.dumps(query_results['structured_data'], ensure_ascii=False, indent=2)}"
        
        location_info = ""
        if location_data:
            location_info = f"\n\n位置情報データ:\n{json.dumps(location_data, ensure_ascii=False, indent=2)}"
        
        prompt = f"""
ユーザーの質問: {user_query}

検索結果の概要: {query_results['message']}

生の検索結果:
{json.dumps(query_results['raw_results'], ensure_ascii=False, indent=2)}
{structured_info}
{location_info}

上記の情報を基に、以下の要件に従って回答してください：

1. ユーザーの質問に対して日本語で分かりやすく回答
2. 構造化データ（title、longitude、latitude）が含まれる場合は、それらを明確に提示
3. 位置情報がある場合は、地理的な情報として整理して表示
4. 事故データの重要な詳細（日時、場所、事故種別、死傷者数など）があれば含める
5. 情報が不十分な場合は、その旨を明確に伝える

回答は読みやすく構造化して提供してください。
"""
        
        response = bedrock_runtime.invoke_model(
            modelId="anthropic.claude-3-sonnet-20240229-v1:0",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1500,
                "messages": [{"role": "user", "content": prompt}]
            })
        )
        
        response_body = json.loads(response['body'].read())
        return response_body['content'][0]['text']
        
    except Exception as e:
        print(f"ERROR: 高度な回答生成エラー: {e}")
        # フォールバック：基本的な情報を返す
        fallback_response = f"{query_results['message']}\n\n"
        
        # 構造化データがある場合は表示
        if query_results['structured_data']:
            fallback_response += "検出された構造化データ:\n"
            for i, data in enumerate(query_results['structured_data'][:3], 1):
                if data.get("title"):
                    fallback_response += f"{i}. タイトル: {data['title']}\n"
                if data.get("longitude") and data.get("latitude"):
                    fallback_response += f"   位置: 経度 {data['longitude']}, 緯度 {data['latitude']}\n"
                fallback_response += f"   関連度: {data.get('score', 0):.2f}\n\n"
        
        return fallback_response

@app.entrypoint
def invoke(payload):
    """メインエントリーポイント（構造化データ対応版）"""
    try:
        user_message = payload.get("prompt", "").strip()
        return_format = payload.get("format", "enhanced")  # "simple" or "enhanced"
        
        if not user_message:
            return {
                "result": "質問を入力してください。",
                "status": "error"
            }
        
        print(f"INFO: ユーザー質問: {user_message}")
        print(f"INFO: 回答形式: {return_format}")
        
        # Bedrockクライアント作成
        bedrock_agent, bedrock_runtime = create_bedrock_clients()
        
        # 構造化データ対応のナレッジベース検索
        query_results = enhanced_knowledge_base_query(
            bedrock_agent, 
            KNOWLEDGE_BASE_ID, 
            user_message
        )
        
        # エラーの場合
        if query_results.get("error"):
            return {
                "result": query_results["message"],
                "knowledge_base_id": KNOWLEDGE_BASE_ID,
                "status": "error",
                "error": query_results["error"]
            }
        
        # 回答生成
        if return_format == "simple":
            # シンプル形式：構造化データのみ
            response = {
                "result": query_results["message"],
                "structured_data": query_results["structured_data"],
                "count": len(query_results["structured_data"]),
                "knowledge_base_id": KNOWLEDGE_BASE_ID,
                "status": "success"
            }
        else:
            # 高度な形式：Claude生成の自然言語回答
            enhanced_answer = generate_enhanced_response(
                bedrock_runtime,
                user_message,
                query_results
            )
            
            response = {
                "result": enhanced_answer,
                "structured_data": query_results["structured_data"],
                "raw_results": query_results["raw_results"],
                "count": len(query_results["structured_data"]),
                "knowledge_base_id": KNOWLEDGE_BASE_ID,
                "status": "success"
            }
        
        return response
        
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

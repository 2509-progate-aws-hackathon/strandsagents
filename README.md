```
# 仮想環境を作成
python3 -m venv agentcore-env

# 仮想環境を有効化（Linux/Mac）
source agentcore-env/bin/activate

# 仮想環境を有効化（Windows）
# agentcore-env\Scripts\activate

# パッケージをインストール
pip3 install strands-agents bedrock-agentcore bedrock-agentcore-starter-toolkit

# 作業が終わったら無効化
deactivate
```


## デプロイ

```
agentcore launch
```


情報
```
 agentcore configure list                                                                                                               
Configured Agents:
  ✅ my_agent (default) - Ready
     Entrypoint: my_agent.py
     Region: us-east-1
```

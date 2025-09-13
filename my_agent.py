from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent

app = BedrockAgentCoreApp()
agent = Agent()

@app.entrypoint
def invoke(payload):
    user_message = payload.get("prompt")
    result = agent(user_message)
    return {"result": result.message}

if __name__ == "__main__":
    app.run()

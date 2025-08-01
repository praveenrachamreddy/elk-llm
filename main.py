import os
import json
from typing import Optional, Type
import requests
from fastapi import FastAPI, Request
from pydantic import BaseModel
from langchain.tools import BaseTool
from langchain.agents import initialize_agent, AgentType
from langchain.chat_models import ChatOpenAI
from langchain.agents.agent_toolkits import Tool
from langchain.schema import SystemMessage

# Load ENV
MODEL_ENDPOINT = os.getenv("MODEL_ENDPOINT")
ES_URL = os.getenv("ES_URL")
ES_USERNAME = os.getenv("ES_USERNAME")
ES_PASSWORD = os.getenv("ES_PASSWORD")
ES_INDEX = os.getenv("ES_INDEX", "praveen-*")

# ============ Elasticsearch Tool ============
class SearchLogsInput(BaseModel):
    query: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None

class ElasticsearchTool(BaseTool):
    name = "search_logs"
    description = "Search logs in Elasticsearch with a query string and optional date range"
    args_schema: Type[BaseModel] = SearchLogsInput

    def _run(self, query: str, start_date: Optional[str] = None, end_date: Optional[str] = None):
        headers = {"Content-Type": "application/json"}
        must_clauses = [{"match": {"message": query}}]
        if start_date and end_date:
            must_clauses.append({
                "range": {
                    "@timestamp": {
                        "gte": start_date,
                        "lte": end_date
                    }
                }
            })

        body = {
            "query": {
                "bool": {
                    "must": must_clauses
                }
            },
            "size": 5
        }

        try:
            res = requests.get(
                f"{ES_URL}/{ES_INDEX}/_search",
                auth=(ES_USERNAME, ES_PASSWORD),
                headers=headers,
                data=json.dumps(body),
                verify=False
            )
            data = res.json()
            hits = data.get("hits", {}).get("hits", [])
            results = []
            for hit in hits:
                src = hit.get("_source", {})
                msg = src.get("message", "No message")
                timestamp = src.get("@timestamp", "No timestamp")
                results.append(f"{timestamp}: {msg}")
            return "\n".join(results) if results else "No logs found."
        except Exception as e:
            return f"Error: {str(e)}"

    def _arun(self, *args, **kwargs):
        raise NotImplementedError("Async not supported.")

# ============ Model Wrapper ============
class GemmaChatModel(ChatOpenAI):
    def __init__(self, **kwargs):
        super().__init__(
            model="gemma-tool-agent",
            temperature=0,
            openai_api_key="not-needed",
            openai_api_base=MODEL_ENDPOINT.replace("/v1/chat/completions", ""),
            openai_api_type="open_ai",
            openai_api_version="v1",
            **kwargs
        )

# ============ Agent Setup ============
tools = [ElasticsearchTool()]
llm = GemmaChatModel()
agent = initialize_agent(tools, llm, agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION, verbose=True)

# ============ FastAPI Server ============
app = FastAPI()

@app.get("/")
def home():
    return {"message": "LangChain Elasticsearch Tool Agent is running."}

@app.post("/query")
async def query(req: Request):
    body = await req.json()
    question = body.get("question")
    if not question:
        return {"error": "Missing 'question' in body"}

    result = agent.run(question)
    return {"response": result}

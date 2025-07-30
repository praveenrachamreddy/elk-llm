import requests
from langchain.llms.base import LLM
from typing import Optional, List

# -------- CONFIG --------
MCP_SERVER_URL = "http://elasticsearch-mcp-server:3000"
MISTRAL_API_URL = "http://mistral-endpoint:8080/v1/completions"
MISTRAL_MODEL_ID = "mistral-7b"

# -------- Step 1: Call MCP Server --------
def query_elastic_mcp(question: str) -> str:
    payload = {
        "question": question,
        "index": "tataesb*"
    }
    response = requests.post(f"{MCP_SERVER_URL}/search", json=payload)
    response.raise_for_status()
    results = response.json()
    return results.get("answer", str(results))  # `answer` is usually present

# -------- Step 2: Define custom LLM wrapper for Mistral --------
class MistralLLM(LLM):
    def _call(self, prompt: str, stop: Optional[List[str]] = None) -> str:
        payload = {
            "model": MISTRAL_MODEL_ID,
            "prompt": prompt,
            "stream": False,
            "temperature": 0.7,
            "max_tokens": 512
        }
        response = requests.post(MISTRAL_API_URL, json=payload)
        response.raise_for_status()
        return response.json()["choices"][0]["text"]

    @property
    def _identifying_params(self):
        return {}

    @property
    def _llm_type(self):
        return "mistral-custom"

# -------- Step 3: Chain everything --------
def ask_question(question: str):
    print(f"❓ User question: {question}")
    mcp_result = query_elastic_mcp(question)
    print(f"📦 Retrieved from MCP:\n{mcp_result}")

    llm = MistralLLM()
    prompt = f"Based on this Elasticsearch data, answer clearly:\n\n{mcp_result}"
    answer = llm(prompt)

    print(f"\n🤖 Final LLM Answer:\n{answer}")

# -------- Main entry --------
if __name__ == "__main__":
    user_input = input("Ask something about ELK logs: ")
    ask_question(user_input)

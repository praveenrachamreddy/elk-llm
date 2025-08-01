import requests
import json
import urllib3

# Suppress only the single InsecureRequestWarning from urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

url = "https://elastic-mcp-route-praveen.apps.ocp4.imss.work/mcp"
headers = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream"
}

payload = {
    "jsonrpc": "2.0",
    "id": "1",
    "method": "invoke",
    "params": {
        "messages": [
            {"role": "user", "content": "Show me recent error logs"}
        ]
    }
}

response = requests.post(url, headers=headers, json=payload, verify=False)

print("Status:", response.status_code)
print("Response:")
print(response.text)

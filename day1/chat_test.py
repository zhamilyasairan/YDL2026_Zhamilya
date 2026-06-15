import os
import requests
from dotenv import load_dotenv

load_dotenv()

url = os.getenv("LLM_URL")
model = os.getenv("LLM_MODEL")
api_key = os.getenv("LLM_API_KEY")

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
}

payload = {
    "model": model,
    "messages": [
        {"role": "user", "content": "Hello! Ответь коротко на русском."}
    ],
}

response = requests.post(url, headers=headers, json=payload, timeout=60)

print("Status:", response.status_code)

data = response.json()
answer = data["choices"][0]["message"]["content"]

print("Ответ модели:")
print(answer)
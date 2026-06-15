import os
import base64
import requests
from dotenv import load_dotenv

load_dotenv()

url = os.getenv("IMAGE_URL")
model = os.getenv("IMAGE_MODEL")
api_key = os.getenv("IMAGE_API_KEY")

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
}

payload = {
    "model": model,
    "prompt": "A detailed realistic landscape of a futuristic city in the mountains at sunrise, with tall modern buildings, snowy mountain peaks in the background, warm golden sunlight, clear sky, cinematic view, highly detailed",
    "size": "512x512",
}

response = requests.post(url, headers=headers, json=payload, timeout=120)

print("Status:", response.status_code)
print(response.text)

response.raise_for_status()

data = response.json()
item = data["data"][0]

if "b64_json" in item:
    image_bytes = base64.b64decode(item["b64_json"])
    with open("almaty_mountains.png", "wb") as f:
        f.write(image_bytes)
    print("Картинка сохранена: almaty_mountains.png")

elif "url" in item:
    print("Ссылка на картинку:")
    print(item["url"])

else:
    print("Неожиданный формат ответа")
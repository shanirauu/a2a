import requests

url = "https://api.openai.com/v1/chat/completions"
headers = {
    "Authorization": "Bearer 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",  # use your full key here
    "Content-Type": "application/json"
}
data = {
    "model": "gpt-3.5-turbo",
    "messages": [{"role": "user", "content": "Hello!"}]
}

response = requests.post(url, headers=headers, json=data)
print(response.json())

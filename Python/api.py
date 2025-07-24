import requests
import os
from dotenv import load_dotenv

load_dotenv()

base_url = os.getenv('BASE_URL')
url = f"{base_url}/post"
payload = {
    "name": "Vikas",
    "age": 22
}
headers = {
    "User-Agent": "my-app/1.0",
    "Accept": "application/json"
}

try:
    response = requests.post(url, json=payload, headers=headers, timeout=5)
    print("Status Code:", response.status_code)
    try:
        print(response.json())
    except requests.exceptions.JSONDecodeError:
        print("Response is not in JSON format:")
        print(response.text)
except requests.exceptions.RequestException as e:
    print("Request failed:", e)


# requests.get(url) – Read/fetch data
# requests.post(url, data/json) – Submit data
# requests.put() / patch() – Update data
# requests.delete() – Delete resource
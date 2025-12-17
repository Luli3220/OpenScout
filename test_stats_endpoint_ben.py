import requests
import json

URL = "http://localhost:8001/api/radar/benjamingr"

print(f"Testing URL: {URL}")
try:
    response = requests.get(URL)
    if response.status_code == 200:
        data = response.json()
        print(json.dumps(data, indent=2))
    else:
        print(f"Error: {response.status_code} - {response.text}")
except Exception as e:
    print(f"Exception: {e}")

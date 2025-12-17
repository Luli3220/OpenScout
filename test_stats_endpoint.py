import requests
import json

URL = "http://localhost:8001/api/radar/abruzzi"

print(f"Testing URL: {URL}")
try:
    response = requests.get(URL)
    if response.status_code == 200:
        data = response.json()
        print(json.dumps(data, indent=2))
        if "activity_sum" in data and "openrank_sum" in data:
            print("SUCCESS: Stats fields found.")
        else:
            print("FAILURE: Stats fields missing.")
    else:
        print(f"Error: {response.status_code} - {response.text}")
except Exception as e:
    print(f"Exception: {e}")

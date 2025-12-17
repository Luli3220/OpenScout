import json
import os
import requests
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
import uvicorn

app = FastAPI()

# Paths
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT_DIR, "data")
HTML_FILE = os.path.join(ROOT_DIR, "OpenScout.htm")
RADAR_FILE = os.path.join(DATA_DIR, "radar_scores.json")
MACRO_DATA_FILE = os.path.join(DATA_DIR, "macro_data", "macro_data_results.json")
USERS_LIST_FILE = os.path.join(DATA_DIR, "users_list.json")
RAW_USERS_DIR = os.path.join(DATA_DIR, "raw_users")
CONFIG_FILE = os.path.join(ROOT_DIR, "config.json")

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

config = load_config()
MAXKB_API_URL = config.get("maxkb_api_url", "")
MAXKB_API_KEY = config.get("maxkb_api_key", "")

# Load data
def load_radar_scores():
    if os.path.exists(RADAR_FILE):
        with open(RADAR_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def load_macro_data():
    if os.path.exists(MACRO_DATA_FILE):
        with open(MACRO_DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def calculate_recent_sum(data_dict):
    """
    Sum the values of the last 12 months (keys matching YYYY-MM).
    """
    if not data_dict:
        return 0.0
    
    # Filter for monthly keys (YYYY-MM)
    monthly_keys = [k for k in data_dict.keys() if len(k) == 7 and k[4] == '-']
    monthly_keys.sort(reverse=True) # Newest first
    
    # Take top 12
    recent_keys = monthly_keys[:12]
    
    total = 0.0
    for k in recent_keys:
        val = data_dict.get(k, 0)
        # Ensure value is float/int
        if isinstance(val, (int, float)):
            total += val
    
    return round(total, 2)

def load_users_list():
    if os.path.exists(USERS_LIST_FILE):
        with open(USERS_LIST_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def load_tech_stack(username):
    path = os.path.join(RAW_USERS_DIR, username, "tech_stack.json")
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            # Convert JSON object to a string representation for the LLM
            data = json.load(f)
            return json.dumps(data, ensure_ascii=False, indent=2)
    return "No tech stack data found."

def load_agent_b_context(username):
    path = os.path.join(RAW_USERS_DIR, username, "agent_b_context.json")
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get("agent_b_context") or "No code audit data found."
    return "No code audit data found."

@app.get("/")
async def get_index():
    return FileResponse(HTML_FILE)

@app.get("/api/analyze/{username}")
async def analyze_user(username: str):
    # 1. Gather Context Data
    tech_stack = load_tech_stack(username)
    code_audit = load_agent_b_context(username)
    
    radar_scores = load_radar_scores().get(username, [])
    radar_str = str(radar_scores) if radar_scores else "No radar data"

    print(f"--- Analyzing User: {username} ---")
    print(f"Tech Stack Data Length: {len(tech_stack)}")
    print(f"Code Audit Data Length: {len(code_audit)}")
    print(f"Radar Data: {radar_str}")

    # 2. Prepare MaxKB Payload (OpenAI Format with Parameters)
    # User instructions: Pass data via parameters (inputs), input message is NULL.
    payload = {
        "model": "OpenScout",
        "messages": [
            {
                "role": "user",
                "content": "Start Analysis"  # Use a neutral start string or empty if supported. 
                                           # Using "Start Analysis" to ensure trigger.
            }
        ],
        "stream": True,
        "form_data": {
            "TechHunter":   tech_stack,       # 对应截图里的 TechHunter
            "CodeAuditor": code_audit,      # 对应截图里的 CodeAuditor
            "Six_Dimension": radar_str      # 对应截图里的 Six_Dimension
        }
    }
    
    headers = {
        "Authorization": f"Bearer {MAXKB_API_KEY}",
        "Content-Type": "application/json"
    }

    # 3. Stream from MaxKB
    def event_stream():
        try:
            with requests.post(MAXKB_API_URL, json=payload, headers=headers, stream=True) as r:
                if r.status_code != 200:
                    yield f"Error from MaxKB: {r.status_code} - {r.text}"
                    return

                for line in r.iter_lines():
                    if line:
                        decoded_line = line.decode('utf-8')
                        if decoded_line.startswith("data:"):
                             try:
                                 json_str = decoded_line[5:].strip()
                                 if json_str == "[DONE]":
                                     break
                                 data = json.loads(json_str)
                                 
                                 # OpenAI format: choices[0].delta.content
                                 choices = data.get("choices", [])
                                 if choices:
                                     delta = choices[0].get("delta", {})
                                     content = delta.get("content", "")
                                     # Also check reasoning_content if content is empty
                                     reasoning = delta.get("reasoning_content", "")
                                     
                                     if content:
                                         yield content
                                     elif reasoning:
                                         # Optional: yield reasoning content? 
                                         # Maybe just ignore it or yield it with a marker?
                                         # For now, let's yield it so user sees something happening.
                                         yield reasoning
                             except:
                                 pass
        except Exception as e:
            yield f"Internal Server Error: {str(e)}"

    return StreamingResponse(event_stream(), media_type="text/plain")

@app.get("/api/radar/{username}")
async def get_radar_score(username: str):
    scores = load_radar_scores()
    macro_data = load_macro_data()
    
    # Base response structure
    response = {
        "username": username,
        "radar": [50, 50, 50, 50, 50, 50], # Default
        "found": False,
        "activity_sum": 0.0,
        "openrank_sum": 0.0,
        "message": "User data not calculated yet"
    }

    if username in scores:
        response["radar"] = scores[username]
        response["found"] = True
        response["message"] = "Success"
    
    # Add Macro Data if available
    if username in macro_data:
        user_macro = macro_data[username]
        response["activity_sum"] = calculate_recent_sum(user_macro.get("activity", {}))
        response["openrank_sum"] = calculate_recent_sum(user_macro.get("openrank", {}))
        # If user found in macro data but not radar, still consider partial success?
        # But UI depends on "found" for radar rendering. We'll keep "found" tied to radar for now, 
        # or update logic if needed. The current frontend checks `data.found`.
    
    return response

@app.get("/api/users")
async def get_users():
    return load_users_list()

if __name__ == "__main__":
    print("Starting OpenScout Server at http://localhost:8001")
    uvicorn.run(app, host="0.0.0.0", port=8001)

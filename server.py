import json
import os
import re
import time
import requests
from fastapi import BackgroundTasks, FastAPI, HTTPException
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
GITHUB_TOKEN = config.get("github_token") or ((config.get("github_tokens") or [None])[0])

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
    
    month_key_re = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
    monthly_keys = [k for k in data_dict.keys() if isinstance(k, str) and month_key_re.match(k)]
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

def extract_monthly_series(data_dict, max_points=48):
    if not data_dict:
        return [], []
    month_key_re = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
    monthly_keys = [k for k in data_dict.keys() if isinstance(k, str) and month_key_re.match(k)]
    monthly_keys.sort()
    labels = []
    values = []
    for k in monthly_keys:
        val = data_dict.get(k)
        if isinstance(val, (int, float)):
            labels.append(k)
            values.append(val)
    if max_points and len(labels) > max_points:
        labels = labels[-max_points:]
        values = values[-max_points:]
    return labels, values

def load_users_list():
    if os.path.exists(USERS_LIST_FILE):
        with open(USERS_LIST_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def ensure_user_dir(username: str):
    user_dir = os.path.join(RAW_USERS_DIR, username)
    os.makedirs(user_dir, exist_ok=True)
    return user_dir

def load_cached_github_profile(username: str):
    path = os.path.join(RAW_USERS_DIR, username, "github_profile.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return None

def cache_github_profile(username: str, data: dict):
    user_dir = ensure_user_dir(username)
    profile_path = os.path.join(user_dir, "github_profile.json")
    cached = {
        "login": data.get("login"),
        "name": data.get("name"),
        "avatar_remote_url": data.get("avatar_url"),
        "html_url": data.get("html_url"),
        "cached_at": int(time.time())
    }
    avatar_url = cached.get("avatar_remote_url")
    avatar_file = None
    if avatar_url:
        try:
            r = requests.get(avatar_url, stream=True, timeout=20)
            if r.status_code == 200:
                content_type = (r.headers.get("content-type") or "").split(";")[0].strip().lower()
                ext = ".jpg"
                if content_type == "image/png":
                    ext = ".png"
                elif content_type in ("image/jpeg", "image/jpg"):
                    ext = ".jpg"
                elif content_type == "image/gif":
                    ext = ".gif"
                avatar_file = f"github_avatar{ext}"
                avatar_path = os.path.join(user_dir, avatar_file)
                with open(avatar_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 64):
                        if chunk:
                            f.write(chunk)
        except:
            avatar_file = None
    if avatar_file:
        cached["avatar_file"] = avatar_file
    with open(profile_path, "w", encoding="utf-8") as f:
        json.dump(cached, f, ensure_ascii=False, indent=2)

def format_tech_stack(tech_stack_json):
    """
    Parses the raw JSON tech stack and formats it into a concise, LLM-readable string.
    """
    try:
        repos = json.loads(tech_stack_json)
    except:
        return tech_stack_json

    if not isinstance(repos, list):
        return tech_stack_json

    output = []
    for repo in repos:
        name = repo.get("name", "Unknown")
        stars = repo.get("stars", 0)
        desc = repo.get("description", "No description")
        langs = repo.get("languages_breakdown", {})
        
        # Format languages
        total_bytes = sum(langs.values())
        if total_bytes > 0:
            # Sort by percentage
            sorted_langs = sorted(langs.items(), key=lambda x: x[1], reverse=True)
            # Take top 5 languages to save space
            lang_str = ", ".join([f"{k}: {v/total_bytes:.1%}" for k,v in sorted_langs[:5]])
        else:
            lang_str = "Unknown"
            
        repo_str = f"### Project: {name} (Stars: {stars})\n"
        repo_str += f"- Description: {desc}\n"
        repo_str += f"- Languages: {lang_str}\n"
        repo_str += "- Key Files:\n"
        
        files = repo.get("files", {})
        for fname, content in files.items():
            if not content: continue
            
            # Truncate content
            clean_content = content.strip()
            # Limit file size for LLM context (e.g., 1500 chars)
            if len(clean_content) > 1500:
                clean_content = clean_content[:1500] + "\n...[Truncated]..."
            
            # Indent content for readability
            indented_content = "\n".join(["  " + line for line in clean_content.split('\n')])
            repo_str += f"  [{fname}]\n{indented_content}\n\n"
            
        output.append(repo_str)
        
    return "\n".join(output)

def load_tech_stack(username):
    path = os.path.join(RAW_USERS_DIR, username, "tech_stack.json")
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            # Read raw content
            content = f.read()
            # Return optimized string
            return format_tech_stack(content)
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
        "inputs": {
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
        "openrank_labels": [],
        "openrank_series": [],
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
        labels, series = extract_monthly_series(user_macro.get("openrank", {}), max_points=48)
        response["openrank_labels"] = labels
        response["openrank_series"] = series
        # If user found in macro data but not radar, still consider partial success?
        # But UI depends on "found" for radar rendering. We'll keep "found" tied to radar for now, 
        # or update logic if needed. The current frontend checks `data.found`.
    
    return response

@app.get("/api/users")
async def get_users():
    return load_users_list()

@app.get("/api/github/{username}")
async def get_github_user(username: str, background_tasks: BackgroundTasks):
    cached = load_cached_github_profile(username)
    if cached:
        avatar_file = cached.get("avatar_file")
        avatar_url = None
        if avatar_file:
            avatar_path = os.path.join(RAW_USERS_DIR, username, avatar_file)
            if os.path.exists(avatar_path):
                avatar_url = f"/api/avatar/{username}"
        return {
            "login": cached.get("login"),
            "name": cached.get("name"),
            "avatar_url": avatar_url or cached.get("avatar_remote_url"),
            "html_url": cached.get("html_url")
        }

    url = f"https://api.github.com/users/{username}"
    headers = {
        "Accept": "application/vnd.github+json"
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    r = requests.get(url, headers=headers, timeout=15)
    if r.status_code == 404:
        raise HTTPException(status_code=404, detail="GitHub user not found")
    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    data = r.json()
    background_tasks.add_task(cache_github_profile, username, data)
    return {
        "login": data.get("login"),
        "name": data.get("name"),
        "avatar_url": data.get("avatar_url"),
        "html_url": data.get("html_url")
    }

@app.get("/api/avatar/{username}")
async def get_cached_avatar(username: str):
    cached = load_cached_github_profile(username)
    if cached and cached.get("avatar_file"):
        avatar_path = os.path.join(RAW_USERS_DIR, username, cached["avatar_file"])
        if os.path.exists(avatar_path):
            return FileResponse(avatar_path)
    raise HTTPException(status_code=404, detail="Avatar not cached")

if __name__ == "__main__":
    print("Starting OpenScout Server at http://localhost:8001")
    uvicorn.run(app, host="0.0.0.0", port=8001)

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

def load_json(path):
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def generate_payload(username):
    # 1. Load Data
    github_profile = load_json(os.path.join(RAW_USERS_DIR, username, "github_profile.json"))
    radar_scores = load_json(RADAR_FILE)
    macro_data = load_json(MACRO_DATA_FILE)
    tech_stack = load_json(os.path.join(RAW_USERS_DIR, username, "tech_stack.json"))
    diversity = load_json(os.path.join(RAW_USERS_DIR, username, f"{username}_diversity.json"))

    # --- Agent A: Six_Dimension ---
    # Github Profile
    profile_info = {
        "login": github_profile.get("login", username),
        "name": github_profile.get("name", username)
    }
    
    # Radar Scores
    user_radar = radar_scores.get(username, [])

    # OpenRank (Monthly)
    user_macro = macro_data.get(username, {}).get("openrank", {})
    # Filter for YYYY-MM
    month_key_re = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
    monthly_openrank = {k: v for k, v in user_macro.items() if month_key_re.match(k)}
    
    # Get last 12 months (or all if less)
    sorted_months = sorted(monthly_openrank.keys(), reverse=True)[:12]
    # Sort back to chronological for readability if needed, but dict order doesn't matter much for JSON
    recent_openrank = {k: monthly_openrank[k] for k in sorted(sorted_months)}

    six_dimension_payload = {
        "profile": profile_info,
        "radar_scores": user_radar,
        "openrank_history": recent_openrank
    }

    # --- Agent B: TechHunter ---
    raw_diversity = diversity.get("raw_metrics", {})
    tech_hunter_payload = {
        "distinct_languages": raw_diversity.get("distinct_languages", []),
        "distinct_topics": raw_diversity.get("distinct_topics", [])
    }

    # --- Agent C: CodeAuditor ---
    top_repos = []
    if isinstance(tech_stack, list):
        # Take top 3
        for repo in tech_stack[:3]:
            files = repo.get("files", {})
            readme_content = files.get("README.md", "")
            
            # Truncate
            if len(readme_content) > 1500:
                readme_content = readme_content[:1500] + "...(truncated)"
            
            top_repos.append({
                "name": repo.get("name"),
                "description": repo.get("description"),
                "readme": readme_content
            })
    
    code_auditor_payload = {
        "top_repositories": top_repos
    }

    return {
        "tech_hunter_payload": json.dumps(tech_hunter_payload, ensure_ascii=False),
        "code_auditor_payload": json.dumps(code_auditor_payload, ensure_ascii=False),
        "six_dimension_payload": json.dumps(six_dimension_payload, ensure_ascii=False)
    }

@app.get("/")
async def get_index():
    return FileResponse(HTML_FILE)

@app.get("/api/analyze/{username}")
async def analyze_user(username: str):
    print(f"--- Analyzing User: {username} ---")

    # 1. Generate New Payload Structure
    inputs_data = generate_payload(username)
    
    # 2. Prepare MaxKB Payload (Official Form Data Format)
    message = "请根据传入的表单数据生成深度分析报告。"
    payload = {
        "message": message,
        "messages": [{"role": "user", "content": message}],
        "stream": True,
        "re_chat": True,
        "form_data": inputs_data
    }
    
    headers = {
        "Authorization": f"Bearer {MAXKB_API_KEY}",
        "Content-Type": "application/json"
    }

    # 3. Request from MaxKB (Non-streaming for structured output)
    try:
        # Change stream=True to stream=False to get the full JSON with multiple agent outputs
        payload["stream"] = False
        r = requests.post(MAXKB_API_URL, json=payload, headers=headers, timeout=(10, 300))
        
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail=f"Error from MaxKB: {r.text}")
            
        return r.json()
        
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

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


@app.get("/api/tech_stack/{username}")
async def get_tech_stack(username: str):
    path = os.path.join(RAW_USERS_DIR, username, "tech_stack.json")
    if not os.path.exists(path):
        # Return empty list for consistency
        return []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/representative/{username}")
async def get_representative_repos(username: str):
    path = os.path.join(RAW_USERS_DIR, username, "representative_repos.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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

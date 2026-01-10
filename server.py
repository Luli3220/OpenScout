import json
import os
import re
import time
import sys
import requests
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from pydantic import BaseModel
import uvicorn
import subprocess

app = FastAPI()

# Paths
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

# Mount static images
IMAGE_DIR = os.path.join(ROOT_DIR, "image")
if os.path.exists(IMAGE_DIR):
    app.mount("/images", StaticFiles(directory=IMAGE_DIR), name="images")

DATA_DIR = os.path.join(ROOT_DIR, "data")
SEARCH_HTML_FILE = os.path.join(ROOT_DIR, "search.htm")
PROFILE_HTML_FILE = os.path.join(ROOT_DIR, "profile.htm")
RADAR_FILE = os.path.join(DATA_DIR, "radar_scores.json")
MACRO_DATA_FILE = os.path.join(DATA_DIR, "macro_data", "macro_data_results.json")
USERS_LIST_FILE = os.path.join(DATA_DIR, "users_list.json")
RAW_USERS_DIR = os.path.join(DATA_DIR, "raw_users")
CONFIG_FILE = os.path.join(ROOT_DIR, "config.json")
SRC_DIR = os.path.join(ROOT_DIR, "src")
PIPELINE_SCRIPT = os.path.join(SRC_DIR, "run_pipeline.py")
DEVELOPER_VECTORS_FILE = os.path.join(DATA_DIR, "developer_vectors.json")

# In-memory status for mining jobs
mining_status = {} # username -> status ("processing", "done", "failed")

def run_pipeline_for_user(username: str):
    """Background task to run pipeline for a user"""
    print(f"Starting background mining for {username}")
    mining_status[username] = "processing"
    try:
        # Run the pipeline script via subprocess
        result = subprocess.run(
            [sys.executable, PIPELINE_SCRIPT, "--username", username],
            check=True,
            capture_output=True,
            text=True
        )
        print(f"Mining for {username} completed.")
        mining_status[username] = "done"
    except subprocess.CalledProcessError as e:
        print(f"Mining for {username} failed: {e.stderr}")
        mining_status[username] = "failed"
    except Exception as e:
        print(f"Mining for {username} error: {str(e)}")
        mining_status[username] = "failed"

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

config = load_config()
MAXKB_API_URL = os.environ.get("MAXKB_API_URL") or config.get("maxkb_api_url", "")
if MAXKB_API_URL:
    MAXKB_API_URL = f"{MAXKB_API_URL.rstrip('/')}/chat/completions"

MAXKB_API_KEY = os.environ.get("MAXKB_API_KEY") or config.get("maxkb_api_key", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN") or config.get("github_token") or ((config.get("github_tokens") or [None])[0])
LLM_API_URL = os.environ.get("LLM_API_URL") or config.get("LLM_api_url") or config.get("llm_api_url")
LLM_API_KEY = os.environ.get("LLM_API_KEY") or config.get("LLM_api_key") or config.get("llm_api_key", "")
LLM_MODEL = os.environ.get("LLM_MODEL") or config.get("LLM_model") or config.get("llm_model")
LLM_EMBEDDING_MODEL = os.environ.get("LLM_EMBEDDING_MODEL") or config.get("LLM_embedding_model") or config.get("llm_embedding_model")

DEEPSEEK_API_URL = os.environ.get("DEEPSEEK_API_URL") or LLM_API_URL or config.get("deepseek_api_url") or config.get("qwen_api_url")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY") or LLM_API_KEY or config.get("deepseek_api_key", "")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL") or LLM_MODEL or config.get("deepseek_model", "deepseek-chat")

# Qwen / Embedding Config
QWEN_API_URL = os.environ.get("QWEN_API_URL") or LLM_API_URL or config.get("qwen_api_url", "https://api.deepseek.com")
QWEN_API_KEY = os.environ.get("QWEN_API_KEY") or LLM_API_KEY or config.get("qwen_api_key", "")
QWEN_EMBEDDING_MODEL = os.environ.get("QWEN_EMBEDDING_MODEL") or LLM_EMBEDDING_MODEL or config.get("qwen_embedding_model", "text-embedding-v4")

USER_EMBEDDINGS_CACHE_FILE = os.path.join(DATA_DIR, "vector_store.json")

class SimpleVectorStore:
    def __init__(self, storage_file=USER_EMBEDDINGS_CACHE_FILE):
        self.storage_file = storage_file
        self.vectors = {}
        self.load()

    def load(self):
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, 'r', encoding='utf-8') as f:
                    self.vectors = json.load(f)
            except Exception as e:
                print(f"Failed to load vector store: {e}")
                self.vectors = {}
        # Migration from old filename if exists and new one doesn't
        elif os.path.exists(os.path.join(DATA_DIR, "user_embeddings_cache.json")):
             try:
                with open(os.path.join(DATA_DIR, "user_embeddings_cache.json"), 'r', encoding='utf-8') as f:
                    self.vectors = json.load(f)
                self.save() # Save to new location
             except:
                 pass

    def save(self):
        try:
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(self.vectors, f)
        except Exception as e:
            print(f"Failed to save vector store: {e}")

    def add(self, key, vector):
        self.vectors[key] = vector

    def get(self, key):
        return self.vectors.get(key)
    
    def has(self, key):
        return key in self.vectors

    def search(self, query_vector, limit=10):
        results = []
        for key, vector in self.vectors.items():
            score = cosine_similarity(query_vector, vector)
            results.append((key, score))
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

# Initialize global vector store
vector_store = SimpleVectorStore()

def generate_qwen_embedding(text: str):
    """Generate embedding using Qwen/DeepSeek API"""
    if not QWEN_API_KEY:
        print("Warning: QWEN_API_KEY not found")
        return []
    
    # Normalize URL
    api_url = QWEN_API_URL.rstrip("/")
    if not api_url.endswith("/embeddings"):
         if "v1" not in api_url:
             api_url = f"{api_url}/v1/embeddings"
         else:
             api_url = f"{api_url}/embeddings"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {QWEN_API_KEY}"
    }
    
    payload = {
        "model": QWEN_EMBEDDING_MODEL,
        "input": text
    }
    
    try:
        resp = requests.post(api_url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if "data" in data and len(data["data"]) > 0:
            return data["data"][0]["embedding"]
        return []
    except Exception as e:
        print(f"Embedding generation failed: {e}")
        return []

def get_user_search_text(username: str):
    """Aggregate user data for search"""
    text_parts = []
    
    # 1. Diversity Data (Languages & Topics)
    diversity_path = os.path.join(RAW_USERS_DIR, username, f"{username}_diversity.json")
    if os.path.exists(diversity_path):
        try:
            div_data = load_json(diversity_path)
            raw = div_data.get("raw_metrics", {})
            langs = raw.get("distinct_languages", [])
            topics = raw.get("distinct_topics", [])
            if langs:
                text_parts.append(f"Languages: {', '.join(langs)}")
            if topics:
                text_parts.append(f"Topics: {', '.join(topics)}")
        except Exception as e:
            print(f"Error reading diversity for {username}: {e}")

    # 2. Tech Stack (Repo descriptions & READMEs)
    tech_stack_path = os.path.join(RAW_USERS_DIR, username, "tech_stack.json")
    if os.path.exists(tech_stack_path):
        try:
            stack_data = load_json(tech_stack_path)
            if isinstance(stack_data, list):
                for repo in stack_data:
                    name = repo.get("name", "")
                    desc = repo.get("description", "")
                    if name:
                        text_parts.append(f"Project: {name}")
                    if desc:
                        text_parts.append(f"Description: {desc}")
                    
                    files = repo.get("files", {})
                    readme = files.get("README.md", "")
                    if readme:
                        # Truncate readme to avoid token limits (approx 500 chars)
                        text_parts.append(f"Readme: {readme[:500]}")
        except Exception as e:
            print(f"Error reading tech stack for {username}: {e}")
            
    return "\n".join(text_parts)



class RepoAnalysisRequest(BaseModel):
    repo_url: str


def _parse_github_repo_url(repo_url: str):
    match = re.search(r"github\.com/([^/]+)/([^/#?]+)", repo_url or "")
    if not match:
        raise HTTPException(status_code=400, detail="Invalid GitHub URL")
    owner, repo = match.groups()
    if repo.endswith(".git"):
        repo = repo[:-4]
    return owner, repo


def _normalize_deepseek_api_url(raw_url: str):
    url = (raw_url or "").strip().strip('"').strip("'").strip()
    if not url:
        return ""
    url = url.rstrip("/")
    if url.endswith("/chat/completions") or url.endswith("/v1/chat/completions"):
        return url
    return f"{url}/chat/completions"


def fetch_github_repo_content(repo_url: str):
    owner, repo = _parse_github_repo_url(repo_url)

    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"

    repo_api_url = f"https://api.github.com/repos/{owner}/{repo}"
    repo_resp = requests.get(repo_api_url, headers=headers, timeout=15)
    if repo_resp.status_code != 200:
        raise HTTPException(status_code=repo_resp.status_code, detail=f"Repository fetch failed: {repo_resp.text}")
    repo_data = repo_resp.json()

    description = repo_data.get("description") or ""
    topics = repo_data.get("topics") or []

    readme_url = f"https://api.github.com/repos/{owner}/{repo}/readme"
    readme_headers = dict(headers)
    readme_headers["Accept"] = "application/vnd.github.raw"
    readme_resp = requests.get(readme_url, headers=readme_headers, timeout=20)
    readme_content = readme_resp.text if readme_resp.status_code == 200 else ""

    return {
        "name": f"{owner}/{repo}",
        "description": description,
        "topics": topics if isinstance(topics, list) else [],
        "readme": (readme_content or "")[:12000],
        "html_url": f"https://github.com/{owner}/{repo}",
    }


def stream_deepseek_repo_summary(repo_data: dict, api_url: str, api_key: str, model: str):
    if not api_key:
        yield "DeepSeek API Key 未配置，无法进行仓库分析。".encode("utf-8")
        return

    topics_text = ", ".join([t for t in repo_data.get("topics", []) if isinstance(t, str)])
    prompt = (
        "请根据以下 GitHub 仓库信息，用中文输出一段话（约 120-200 字）的仓库介绍，"
        "重点说明：它解决什么问题、核心功能/特性、典型使用场景。避免空话，尽量具体。\n\n"
        f"仓库：{repo_data.get('name','')}\n"
        f"URL：{repo_data.get('html_url','')}\n"
        f"Description：{repo_data.get('description','')}\n"
        f"Topics：{topics_text}\n\n"
        "README（节选）：\n"
        f"{repo_data.get('readme','')}\n"
    )

    api_url = _normalize_deepseek_api_url(api_url)
    if not api_url:
        yield "DeepSeek API URL 未配置，无法进行仓库分析。".encode("utf-8")
        return

    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是一个严谨的技术写作者，擅长总结开源项目。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "stream": True,
    }

    try:
        resp = requests.post(api_url, json=payload, headers=headers, stream=True, timeout=120)
        if resp.status_code == 401:
            yield "DeepSeek 鉴权失败(401)。请检查 config.json 中的 deepseek_api_key 是否正确、是否有权限使用该模型。".encode("utf-8")
            return
        if resp.status_code == 404:
            yield f"DeepSeek 接口地址不存在(404)：{api_url}。请检查 deepseek_api_url 配置。".encode("utf-8")
            return
        resp.raise_for_status()

        for raw_line in resp.iter_lines(decode_unicode=True):
            if not raw_line:
                continue
            line = raw_line.strip()
            if line.startswith("data:"):
                line = line[len("data:") :].strip()
            if line == "[DONE]":
                break
            try:
                data = json.loads(line)
            except Exception:
                continue
            try:
                delta = data.get("choices", [{}])[0].get("delta", {}).get("content")
                if delta:
                    yield delta.encode("utf-8")
            except Exception:
                continue
    except Exception as e:
        yield f"\n\n[分析失败] DeepSeek 连接异常：{str(e)}".encode("utf-8")
        return

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

def load_developer_vectors():
    """Load developer vectors from file"""
    return load_json(DEVELOPER_VECTORS_FILE)

def cosine_similarity(vec1, vec2):
    """Calculate cosine similarity between two vectors"""
    if len(vec1) != len(vec2):
        return 0.0
    
    dot_product = sum(v1 * v2 for v1, v2 in zip(vec1, vec2))
    norm1 = sum(v1 ** 2 for v1 in vec1) ** 0.5
    norm2 = sum(v2 ** 2 for v2 in vec2) ** 0.5
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    return dot_product / (norm1 * norm2)

def generate_vector_chatecnu(query_text: str):
    """Generate vector from text using ChatECNU API"""
    if not CHATECNU_API_URL or not CHATECNU_API_KEY:
        raise HTTPException(status_code=500, detail="ChatECNU API not configured")
    
    # Prepare the prompt to generate a 10-dimensional vector
    prompt = f"请将以下文本转换为一个10维的浮点数向量，仅返回向量数据，格式为JSON数组，不要包含其他任何内容：\n{query_text}"
    
    payload = {
        "messages": [
            {
                "role": "system",
                "content": "你是华东师范大学大模型ChatECNU，擅长将文本转换为向量表示。"
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "stream": False,
        "model": "ecnu-plus"
    }
    
    headers = {
        "Authorization": f"Bearer {CHATECNU_API_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(CHATECNU_API_URL, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Parse the response
        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        # Extract vector from content
        import ast
        vector = ast.literal_eval(content.strip())
        
        # Validate vector format
        if not isinstance(vector, list):
            raise ValueError("Vector is not a list")
        
        # Ensure vector has exactly 10 dimensions
        if len(vector) != 10:
            # If not 10 dimensions, pad or truncate
            if len(vector) < 10:
                # Pad with zeros
                vector += [0.0] * (10 - len(vector))
            else:
                # Truncate to 10 dimensions
                vector = vector[:10]
        
        # Convert all elements to float
        vector = [float(x) for x in vector]
        
        return vector
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"ChatECNU API request failed: {str(e)}")
    except (ValueError, SyntaxError) as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse ChatECNU vector response: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Vector generation failed: {str(e)}")

def search_developers(query_vector, vectors, limit=10):
    """Search developers by vector similarity"""
    results = []
    
    for username, vector in vectors.items():
        similarity = cosine_similarity(query_vector, vector)
        results.append((username, similarity))
    
    # Sort by similarity in descending order
    results.sort(key=lambda x: x[1], reverse=True)
    
    # Return top N results
    return results[:limit]

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

@app.post("/api/analyze-repo")
async def analyze_repo(request: RepoAnalysisRequest):
    repo_data = fetch_github_repo_content(request.repo_url)
    runtime_config = load_config()
    api_url = runtime_config.get("deepseek_api_url") or DEEPSEEK_API_URL
    api_key = runtime_config.get("deepseek_api_key") or DEEPSEEK_API_KEY
    model = runtime_config.get("deepseek_model") or DEEPSEEK_MODEL
    return StreamingResponse(stream_deepseek_repo_summary(repo_data, api_url, api_key, model), media_type="text/plain; charset=utf-8")

@app.get("/")
async def get_index():
    return FileResponse(SEARCH_HTML_FILE)

@app.get("/search")
async def get_search():
    return FileResponse(SEARCH_HTML_FILE)

@app.get("/profile/{username}")
async def get_profile(username: str):
    return FileResponse(PROFILE_HTML_FILE)

@app.get("/api/analyze/{username}")
def analyze_user(username: str):
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
def get_radar_score(username: str, background_tasks: BackgroundTasks):
    scores = load_radar_scores()
    macro_data = load_macro_data()
    
    # Base response structure
    response = {
        "username": username,
        "radar": [50, 50, 50, 50, 50, 50], # Default
        "found": False,
        "mining": False,
        "mining_status": "none",
        "activity_sum": 0.0,
        "openrank_sum": 0.0,
        "openrank_labels": [],
        "openrank_series": [],
        "message": "User data not calculated yet"
    }

    # Check mining status first
    if username in mining_status:
        status = mining_status[username]
        response["mining_status"] = status
        if status == "processing":
            response["mining"] = True
            response["message"] = "Mining in progress..."
            return response
        elif status == "failed":
            response["message"] = "Mining failed."
            # Don't return yet, maybe we have old data? Or just failed state.
        elif status == "done":
            # If done, reload scores to get fresh data
            scores = load_radar_scores()
            macro_data = load_macro_data()
            # Clean up status so we don't return "done" forever, or keep it?
            # Let's keep it "done" until next restart or clear.
            # But "found" will become True below if data is there.

    if username in scores:
        response["radar"] = scores[username]
        response["found"] = True
        response["message"] = "Success"
    else:
        # Not found and not mining -> Start Mining
        if response["mining_status"] == "none":
             print(f"User {username} not found. Triggering auto-mining.")
             background_tasks.add_task(run_pipeline_for_user, username)
             response["mining"] = True
             response["mining_status"] = "processing"
             response["message"] = "User not found locally. Auto-mining started."
    
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
def get_users():
    return load_users_list()

@app.get("/api/github/{username}")
def get_github_user(username: str, background_tasks: BackgroundTasks):
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
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    r = requests.get(url, headers=headers, timeout=15)
    if r.status_code == 401 and GITHUB_TOKEN:
        r = requests.get(url, headers={"Accept": "application/vnd.github+json"}, timeout=15)
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
def get_cached_avatar(username: str):
    cached = load_cached_github_profile(username)
    if cached and cached.get("avatar_file"):
        avatar_path = os.path.join(RAW_USERS_DIR, username, cached["avatar_file"])
        if os.path.exists(avatar_path):
            return FileResponse(avatar_path)
    raise HTTPException(status_code=404, detail="Avatar not cached")

@app.post("/api/search")
def search_users(query: dict):
    """Search users based on natural language query using Qwen embeddings"""
    print(f"--- Searching Users: {query} ---")
    
    query_text = query.get("query", "")
    limit = query.get("limit", 5)
    
    if not query_text:
        return []

    # 1. Generate Query Embedding
    query_vector = generate_qwen_embedding(query_text)
    if not query_vector:
        # Fallback or error?
        # If Qwen fails, we can't search.
        print("Failed to generate query embedding")
        return []

    # 2. Use Vector Store
    users_list = load_users_list()
    
    cache_updated = False
    
    # 3. Ensure all users have embeddings
    # Only process users that have raw data locally
    available_users = []
    for user in users_list:
        if os.path.exists(os.path.join(RAW_USERS_DIR, user)):
             available_users.append(user)
    
    # Check if we need to generate new embeddings
    for username in available_users:
        if not vector_store.has(username):
            print(f"Generating embedding for {username}...")
            user_text = get_user_search_text(username)
            if user_text:
                vec = generate_qwen_embedding(user_text)
                if vec:
                    vector_store.add(username, vec)
                    cache_updated = True
            else:
                print(f"No search text for {username}")
    
    if cache_updated:
        vector_store.save()

    # 4. Perform Search via Vector Store
    top_results = vector_store.search(query_vector, limit)
    
    # 5. Format Response (skip step 6 label since logic is same)
    formatted_results = []
    for username, score in top_results:
        try:
            profile = load_cached_github_profile(username) or {}
            github_info = {
                "login": profile.get("login", username),
                "name": profile.get("name", username),
                "avatar_url": profile.get("avatar_file") and f"/api/avatar/{username}" or profile.get("avatar_remote_url")
            }
            
            # Scale score to 0-100
            scaled_score = max(0, min(100, score * 100))
            
            # Fetch representative repos
            repos = []
            repo_path = os.path.join(RAW_USERS_DIR, username, "representative_repos.json")
            if os.path.exists(repo_path):
                try:
                    all_repos = load_json(repo_path)
                    # Take top 3, just name and description and primary language
                    for r in all_repos[:3]:
                        langs = r.get("languages", {})
                        primary_lang = list(langs.keys())[0] if langs else "Code"
                        repos.append({
                            "name": r.get("name"),
                            "description": r.get("description"),
                            "language": primary_lang,
                            "html_url": r.get("html_url")
                        })
                except:
                    pass

            formatted_results.append({
                "username": username,
                "similarity": scaled_score,
                "profile": github_info,
                "repos": repos
            })
        except Exception as e:
            print(f"Error formatting result for {username}: {e}")
            continue
        
    return formatted_results

if __name__ == "__main__":
    print("Starting OpenScout Server at http://localhost:8001")
    uvicorn.run(app, host="0.0.0.0", port=8001)

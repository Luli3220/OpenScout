#!/usr/bin/env python3
import os
import json
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 保持路径逻辑一致
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, 'data')
RAW_USERS = os.path.join(DATA_DIR, 'raw_users')
CONFIG_FILE = os.path.join(ROOT, 'config.json')
USERS_LIST = os.path.join(DATA_DIR, 'users_list.json')

# 保持权重一致
W_CODE = 0.5
W_SOCIAL = 2.0
W_MAINT = 10.0

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

config = load_config()
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN') or config.get('github_token') or ((config.get('github_tokens') or [None])[0])

HEADERS = {'Accept': 'application/vnd.github.v3+json'}
if GITHUB_TOKEN:
    HEADERS['Authorization'] = f'token {GITHUB_TOKEN}'

# --- 增强：配置自动重试机制 ---
SESSION = requests.Session()
# 定义重试策略：针对 500/502/503/504 等错误重试 5 次
retries = Retry(total=5, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
SESSION.mount('https://', HTTPAdapter(max_retries=retries))
SESSION.headers.update(HEADERS)

def ensure_user_dir(username):
    d = os.path.join(RAW_USERS, username)
    os.makedirs(d, exist_ok=True)
    return d

def list_users():
    if not os.path.exists(USERS_LIST):
        return []
    with open(USERS_LIST, 'r', encoding='utf-8') as f:
        return json.load(f)

# --- 增强：安全的 Get 请求，带超时和异常处理 ---
def safe_get(url):
    try:
        # 将超时时间延长至 60 秒，减少 Read timeout
        r = SESSION.get(url, timeout=60)
        if r.status_code == 200:
            return r
        elif r.status_code == 403:
            print("   [!] 触发频率限制，建议检查 TOKEN 或休眠...")
    except Exception as e:
        print(f"   [!] 网络请求异常: {e}")
    return None

def fetch_user_repos(username):
    repos = []
    page = 1
    while True:
        url = f'https://api.github.com/users/{username}/repos?per_page=100&page={page}&type=owner&sort=pushed'
        r = safe_get(url)
        if not r: break
        batch = r.json()
        if not batch: break
        repos.extend(batch)
        if len(batch) < 100: break
        page += 1
    return repos

def fetch_repo_languages(owner, repo):
    url = f'https://api.github.com/repos/{owner}/{repo}/languages'
    r = safe_get(url)
    return r.json() if r else {}

def fetch_repo_contributions(owner, repo, username):
    url = f'https://api.github.com/repos/{owner}/{repo}/contributors'
    r = safe_get(url)
    if not r: return 0
    try:
        for c in r.json():
            if c.get('login', '').lower() == username.lower():
                return c.get('contributions', 0)
    except: pass
    return 0

def compute_contribution_score(languages_bytes, stars, forks, maint_count):
    total_bytes = sum(languages_bytes.values()) if isinstance(languages_bytes, dict) else 0
    S_code = total_bytes / 1024.0
    S_social = (stars or 0) + (forks or 0) * 2
    S_maint = maint_count or 0
    score = (W_CODE * S_code) + (W_SOCIAL * S_social) + (W_MAINT * S_maint)
    return round(score, 2), S_code, S_social, S_maint

def process_user(username):
    user_dir = ensure_user_dir(username)
    # --- 核心修改：检测文件是否存在，存在则跳过 ---
    out_path = os.path.join(user_dir, 'representative_repos.json')
    if os.path.exists(out_path) and not globals().get('REFRESH', False):
        print(f'---> Skip: {username} (File already exists)')
        return

    print(f'---> Processing: {username}')
    repos = fetch_user_repos(username)
    if not repos: return

    result = []
    for r in repos:
        owner = r['owner']['login']
        repo_name = r['name']
        lang_data = fetch_repo_languages(owner, repo_name)
        maint_count = fetch_repo_contributions(owner, repo_name, username)
        
        score, S_code, S_social, S_maint = compute_contribution_score(
            lang_data, r['stargazers_count'], r['forks_count'], maint_count
        )

        result.append({
            'name': repo_name,
            'full_name': r['full_name'],
            'html_url': r['html_url'],
            'description': r['description'],
            'stars': r['stargazers_count'],
            'forks': r['forks_count'],
            'languages': lang_data,
            'contributions_by_user': maint_count,
            'contribution_score': score,
            'S_code': round(S_code, 2),
            'S_social': S_social,
            'S_maint': S_maint
        })
        # 适当休眠，降低 SSL 报错概率
        time.sleep(0.3)

    result.sort(key=lambda x: x['stars'], reverse=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f'DONE: Saved {username}')

def main():
    # parse refresh flag
    import argparse
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--refresh', action='store_true')
    parser.add_argument('--username', type=str, help='Fetch data for a single user')
    args, _ = parser.parse_known_args()
    global REFRESH
    REFRESH = args.refresh or os.environ.get('REFRESH_DATA') in ('1', 'true', 'True')

    if args.username:
        users = [args.username]
    else:
        users = list_users()

    print(f"Fetching representative repos for {len(users)} users...")
    for u in users:
        username = u.get('login') if isinstance(u, dict) else u
        if not username: continue
        try:
            process_user(username)
        except Exception as e:
            print(f'Error on {username}: {e}')
        time.sleep(1)

if __name__ == '__main__':
    main()
# ./user_data/get_tech_stack_data.py

import requests
import json
import os
import time
from typing import Dict, Any, List, Counter

# -- 1. 配置与常量 --
GITHUB_API_BASE = "https://api.github.com"
USER_LIST_FILE = "./data/users_list.json" 
BASE_USER_DATA_DIR = "./data/raw_users" # 更改为您的目标子目录

TOKENS = os.getenv("GITHUB_TOKENS", "").split(',')

class GitHubAPIClient:
    """管理 GitHub API 请求和 Token 轮询"""
    def __init__(self, tokens: List[str]):
        self.tokens = [t for t in tokens if t]
        self.token_index = 0

    def _get_next_token(self) -> str:
        if not self.tokens: return ""
        token = self.tokens[self.token_index]
        self.token_index = (self.token_index + 1) % len(self.tokens)
        return token
    
    def get(self, endpoint: str, params: Dict[str, Any] = None) -> requests.Response:
        url = f"{GITHUB_API_BASE}{endpoint}"
        while True:
            token = self._get_next_token()
            headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
            try:
                response = requests.get(url, headers=headers, params=params, timeout=15)
                if response.status_code == 403 and 'rate limit exceeded' in response.text:
                    time.sleep(60)
                    continue 
                return response
            except Exception:
                time.sleep(5)
                continue

# -- 2. 核心提取逻辑 --

def get_tech_stack_metrics(client: GitHubAPIClient, username: str) -> Dict[str, Any]:
    """提取语言字节数分布和 Topics 标签"""
    language_counter = Counter()
    topics_list = []
    
    page = 1
    while True:
        # 获取用户仓库列表
        resp = client.get(f"/users/{username}/repos", params={'type': 'owner', 'per_page': 100, 'page': page})
        if resp.status_code != 200: break
        repos = resp.json()
        if not repos: break
        
        for repo in repos:
            if repo.get('fork'): continue # 过滤 Fork 仓库
            
            # 提取 Topics
            topics_list.extend(repo.get('topics', []))
            
            # 获取该仓库的详细语言分布 (字节数)
            lang_endpoint = f"/repos/{username}/{repo['name']}/languages"
            lang_resp = client.get(lang_endpoint)
            if lang_resp.status_code == 200:
                repo_langs = lang_resp.json()
                for lang, bytes_count in repo_langs.items():
                    language_counter[lang] += bytes_count
                    
        page += 1
        if 'next' not in resp.links: break

    # 格式化语言数据为前端百分比
    total_bytes = sum(language_counter.values())
    tech_languages = []
    for lang, count in language_counter.most_common(10): # 取前10名
        percentage = round((count / total_bytes) * 100, 2) if total_bytes > 0 else 0
        tech_languages.append({"name": lang, "value": percentage, "bytes": count})

    # 统计 Topic 出现频次
    topic_counts = Counter(topics_list)
    tech_topics = [{"name": t, "value": c} for t, c in topic_counts.most_common(15)]

    return {
        "languages": tech_languages,
        "topics": tech_topics
    }

# -- 3. 执行与保存 --

def collect_tech_stack_data(username: str):
    # 确保目录存在
    user_path = os.path.join(BASE_USER_DATA_DIR, username)
    os.makedirs(user_path, exist_ok=True)
    
    output_file = os.path.join(user_path, f"{username}_tech_stack.json")
    print(f"正在提取 {username} 的技术栈图谱数据...")
    
    client = GitHubAPIClient(TOKENS)
    tech_data = get_tech_stack_metrics(client, username)
    
    # 最终保存格式：方便前端直接调用渲染条形图或雷达图
    final_output = {
        "username": username,
        "update_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "tech_stack": tech_data
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(final_output, f, indent=2, ensure_ascii=False)
    print(f"✅ 数据已保存至: {output_file}")

def main():
    if os.path.exists(USER_LIST_FILE):
        with open(USER_LIST_FILE, 'r') as f:
            users = json.load(f)
    else:
        users = ["torvalds"]

    for user in users:
        collect_tech_stack_data(user)

if __name__ == "__main__":
    main()
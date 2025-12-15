# ./user_data/get_diversity_data.py

import requests
import json
import os
import time
from typing import Dict, Any, List

# -- 1. 配置与常量 --
GITHUB_API_BASE = "https://api.github.com"
USER_LIST_FILE = "./user_data/users_list.json" 
BASE_USER_DATA_DIR = "./user_data" 

# 从环境变量读取 GitHub Tokens
TOKENS = os.getenv("GITHUB_TOKENS", "").split(',')
if not TOKENS or not TOKENS[0]:
    print("WARNING: GITHUB_TOKENS not set in environment. Rate limit may be reached quickly.")

# -- 2. GitHub API 客户端类 (重用) --

class GitHubAPIClient:
    """管理 GitHub API 请求和 Token 轮询"""
    def __init__(self, tokens: List[str]):
        self.tokens = [t for t in tokens if t]
        self.token_index = 0

    def _get_next_token(self) -> str:
        if not self.tokens:
             return ""
        token = self.tokens[self.token_index]
        self.token_index = (self.token_index + 1) % len(self.tokens)
        return token
    
    def get(self, endpoint: str, params: Dict[str, Any] = None, headers: Dict[str, str] = None) -> requests.Response:
        url = f"{GITHUB_API_BASE}{endpoint}"
        
        while True:
            token = self._get_next_token()
            current_headers = {
                "Authorization": f"token {token}",
                # 使用 preview 接受头来获取 topics/tags
                "Accept": "application/vnd.github.v3+json, application/vnd.github.mercy-preview+json" 
            }
            if headers:
                current_headers.update(headers) 
            
            try:
                if not token and "Authorization" in current_headers:
                    del current_headers["Authorization"]
                    
                response = requests.get(url, headers=current_headers, params=params, timeout=15)
                
                if response.status_code == 403 and 'rate limit exceeded' in response.text:
                    reset_time = int(response.headers.get('X-RateLimit-Reset', time.time() + 60))
                    sleep_duration = reset_time - time.time()
                    print(f"Token {token[:4]}... 速率限制，等待 {sleep_duration:.2f} 秒...")
                    time.sleep(sleep_duration + 5) 
                    continue 
                
                return response
            except requests.exceptions.RequestException as e:
                print(f"Request error: {e}. Retrying...")
                time.sleep(5)
                continue

# -- 3. 数据收集函数 --

def get_diversity_metrics(client: GitHubAPIClient, username: str) -> Dict[str, Any]:
    """
    遍历用户拥有的所有仓库，收集语言和主题多样性指标。
    """
    
    # 统计指标初始化
    distinct_languages = set() 
    distinct_topics = set()
    total_repos = 0
    
    page = 1
    while True:
        # API: GET /users/{username}/repos
        response = client.get(f"/users/{username}/repos", params={'type': 'owner', 'per_page': 100, 'page': page})
        if response.status_code != 200:
            print(f"Error fetching repos for {username}: {response.status_code}")
            break
        
        try:
            repos = response.json()
        except requests.exceptions.JSONDecodeError:
            print(f"Error decoding JSON for repos list of {username}. Status: {response.status_code}")
            break

        if not repos:
            break
        
        for repo in repos:
            if repo.get('fork') == False: # 只计算原创项目
                total_repos += 1
                
                # 1. 语言多样性：从主语言字段获取
                if repo.get('language'):
                    distinct_languages.add(repo['language'])
                
                # 2. 主题多样性：从 topics 字段获取 (需要 "mercy-preview" Accept header)
                topics = repo.get('topics', [])
                for topic in topics:
                    distinct_topics.add(topic)
                
        page += 1
        
        # 检查是否还有下一页
        if 'next' not in response.links:
             break
             
    return {
        "distinct_languages": list(distinct_languages),
        "distinct_topics": list(distinct_topics),
        "language_count": len(distinct_languages),
        "topic_count": len(distinct_topics),
        "total_owned_repos": total_repos
    }


# -- 4. 核心计算函数 --

def calculate_diversity_score(metrics: Dict[str, Any]) -> float:
    """
    计算百分制的开源广度分数。
    
    假设权重:
    - 语言数量: 60%
    - 主题数量: 40%
    """
    
    lang_count = metrics.get('language_count', 0)
    topic_count = metrics.get('topic_count', 0)
    
    # 假设最大值 (需要根据全部用户数据计算)
    MAX_LANG = 10         # 假设最高广度用户使用 10 种语言
    MAX_TOPICS = 50       # 假设最高广度用户涉及 50 个主题
    
    # 归一化 (Normalization)
    norm_lang = min(1.0, lang_count / MAX_LANG)
    norm_topic = min(1.0, topic_count / MAX_TOPICS)
    
    # 加权求和 (Weighted Sum)
    score = (norm_lang * 0.60) + (norm_topic * 0.40)
    
    # 转换为百分制
    diversity_score = round(score * 100, 2)
    
    return diversity_score

# -- 5. 主执行逻辑 --

def collect_diversity_data(username: str):
    """
    收集单个用户的开源广度数据，并计算分数。
    """
    
    # 1. 创建用户数据目录
    user_data_dir = os.path.join(BASE_USER_DATA_DIR, username)
    if not os.path.exists(user_data_dir):
        os.makedirs(user_data_dir)
        
    output_file = os.path.join(user_data_dir, f"{username}_diversity.json")
    
    if os.path.exists(output_file):
        print(f"Diversity data for {username} already exists. Skipping.")
        return

    print(f"Collecting Diversity data for {username}...")
    
    # 2. 初始化 API 客户端
    client = GitHubAPIClient(TOKENS)
    
    # 3. 收集原始指标
    raw_metrics = get_diversity_metrics(client, username)
    
    # 4. 计算最终得分
    diversity_score = calculate_diversity_score(raw_metrics)
    
    # 5. 整理最终数据结构
    final_data = {
        "username": username,
        "raw_metrics": raw_metrics,
        "diversity_score_100": diversity_score
    }
    
    # 6. 保存到文件
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(final_data, f, indent=2, ensure_ascii=False)
        print(f"SUCCESS: {username} 的开源广度数据已保存到 {output_file}，得分: {diversity_score}")
    except Exception as e:
        print(f"ERROR: 写入文件失败 {output_file}: {e}")

def main():
    # 从用户列表文件加载所有目标用户
    try:
        with open(USER_LIST_FILE, 'r', encoding='utf-8') as f:
            target_users = json.load(f)
    except Exception:
        print(f"Error: Could not load users from {USER_LIST_FILE}. Using sample.")
        target_users = ["torvalds", "yyx990803", "gaearon"] 

    # 循环处理所有目标用户
    for username in target_users:
        collect_diversity_data(username)

if __name__ == "__main__":
    main()
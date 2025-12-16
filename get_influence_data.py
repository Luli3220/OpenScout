# ./user_data/get_influence_data.py

import requests
import json
import os
import time
from typing import Dict, Any, List

# -- 1. 配置与常量 --
GITHUB_API_BASE = "https://api.github.com"
OPENDIGGER_API_BASE = "https://oss.x-lab.info/open_digger/github" # OpenDigger API 地址
USER_LIST_FILE = "./user_data/users_list.json" # 从 get_user_name.py 获取的用户列表
# 输出目录结构：./user_data/{username}/{username}_influence.json
BASE_USER_DATA_DIR = "./user_data" 

# 从环境变量或配置文件读取所有可用的 GitHub Token
TOKENS = os.getenv("GITHUB_TOKENS").split(',')
# 请务必替换为您的真实 Token 列表

# -- 2. GitHub API 客户端类 (重用自 get_user_micro_data.py) --

class GitHubAPIClient:
    """管理 GitHub API 请求和 Token 轮询"""
    def __init__(self, tokens: List[str]):
        self.tokens = tokens
        self.token_index = 0

    def _get_next_token(self) -> str:
        """获取下一个 Token 并循环"""
        token = self.tokens[self.token_index]
        self.token_index = (self.token_index + 1) % len(self.tokens)
        return token
    
    def get(self, endpoint: str, params: Dict[str, Any] = None, headers: Dict[str, str] = None) -> requests.Response:
        """执行 API GET 请求，并处理速率限制和 Token 轮询"""
        url = f"{GITHUB_API_BASE}{endpoint}"
        
        while True:
            token = self._get_next_token()
            current_headers = {
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json"
            }
            if headers:
                current_headers.update(headers) 
            
            try:
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

def get_opendigger_data(username: str) -> Dict[str, Any]:
    """从 OpenDigger API 获取 OpenRank 和活跃度相关数据"""
    # OpenRank 是核心指标 
    endpoint = f"/user/{username}/openrank"
    url = f"{OPENDIGGER_API_BASE}{endpoint}"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # 提取 OpenRank 最新值 (假设数据结构为 {..., "data": [{"openrank": 0.1, ...}, ...] } )
        # OpenDigger 的 /openrank 接口返回的是时间序列，我们取最新的值
        latest_rank = data.get('data', [])[-1].get('openrank', 0) if data.get('data') else 0
        
        return {"openrank_value": latest_rank}
    except requests.exceptions.RequestException as e:
        print(f"Error fetching OpenRank for {username}: {e}")
        return {"openrank_value": 0}

def get_github_influence_metrics(client: GitHubAPIClient, username: str) -> Dict[str, Any]:
    """从 GitHub API 获取 Stars, Forks, Watchers 等宏观影响力指标"""
    
    # 获取用户所有项目，计算总 Stars, Forks, Watchers
    total_stars = 0
    total_forks = 0
    
    # 讨论和 Issues 的热度，需要遍历项目，计算 Issues 和 Discussions 数量，这里先简化为 Issues
    total_issues = 0
    
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
            if repo.get('fork') == False: # 只计算原创项目的影响力
                total_stars += repo.get('stargazers_count', 0)
                total_forks += repo.get('forks_count', 0)
                
                # Issues热度：我们使用 open_issues_count 作为近似值
                total_issues += repo.get('open_issues_count', 0)
                
                
        page += 1
        
        # 检查是否还有下一页
        if 'next' not in response.links:
             break

    return {
        "total_stars": total_stars,
        "total_forks": total_forks,
        "total_open_issues": total_issues,
        # TODO: 实际的 Discussions 数量需要单独的 API 调用或更复杂的逻辑
    }


# -- 4. 核心计算函数 --

def calculate_influence_score(metrics: Dict[str, Any]) -> float:
    """
    基于 OpenRank、Stars、Forks、Issues 等指标，计算百分制的影响力分数。
    
    !!! 这是一个示例公式，您需要根据抓取到的全部用户数据进行归一化和权重调整 !!!
    
    初始假设权重:
    - OpenRank: 50%
    - Stars: 30%
    - Forks/Issues 热度: 20%
    """
    
    openrank = metrics.get('openrank_value', 0)
    stars = metrics.get('total_stars', 0)
    forks = metrics.get('total_forks', 0)
    issues = metrics.get('total_open_issues', 0)
    
    # 假设最大值（需要根据全部用户数据计算）
    MAX_OPENRANK = 0.5   # 假设 OpenRank 榜首约为 0.5
    MAX_STARS = 10000    # 假设明星项目总 Star 10000
    MAX_FORK_ISSUE = 2000 # 假设明星项目总 Fork + Issue 2000
    
    # 归一化 (Normalization)
    norm_rank = min(1.0, openrank / MAX_OPENRANK)
    norm_stars = min(1.0, stars / MAX_STARS)
    norm_fork_issue = min(1.0, (forks + issues) / MAX_FORK_ISSUE)
    
    # 加权求和 (Weighted Sum)暂时移除openrank的权重
    score = (norm_stars * 0.60) + (norm_fork_issue * 0.40)
    
    # 转换为百分制
    influence_score = round(score * 100, 2)
    
    return influence_score

# -- 5. 主执行逻辑 --

def collect_influence_data(username: str):
    """
    收集单个用户的项目影响力数据，并计算分数。
    """
    
    # 1. 创建用户数据目录
    user_data_dir = os.path.join(BASE_USER_DATA_DIR, username)
    if not os.path.exists(user_data_dir):
        os.makedirs(user_data_dir)
        
    output_file = os.path.join(user_data_dir, f"{username}_influence.json")
    
    # 检查是否已存在 (避免重复抓取)
    if os.path.exists(output_file):
        print(f"Influence data for {username} already exists. Skipping.")
        return

    print(f"Collecting Influence data for {username}...")
    
    # 2. 初始化 API 客户端
    client = GitHubAPIClient(TOKENS)
    
    # 3. 收集原始指标
    opendigger_metrics = get_opendigger_data(username)
    github_metrics = get_github_influence_metrics(client, username)
    
    # 4. 合并所有指标
    all_metrics = {**opendigger_metrics, **github_metrics}
    
    # 5. 计算最终得分
    influence_score = calculate_influence_score(all_metrics)
    
    # 6. 整理最终数据结构
    final_data = {
        "username": username,
        "raw_metrics": all_metrics,
        "influence_score_100": influence_score
    }
    
    # 7. 保存到文件
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(final_data, f, indent=2, ensure_ascii=False)
        print(f"SUCCESS: {username} 的影响力数据已保存到 {output_file}，得分: {influence_score}")
    except Exception as e:
        print(f"ERROR: 写入文件失败 {output_file}: {e}")

def main():
    # 从用户列表文件加载所有目标用户
    try:
        with open(USER_LIST_FILE, 'r', encoding='utf-8') as f:
            target_users = json.load(f)
    except Exception:
        print(f"Error: Could not load users from {USER_LIST_FILE}. Please run get_user_name.py first.")
        # 使用一个示例用户进行演示
        target_users = ["torvalds"] 

    # 循环处理所有目标用户
    for username in target_users:
        collect_influence_data(username)

if __name__ == "__main__":
    main()
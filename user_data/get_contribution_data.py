# ./user_data/get_contribution_data.py

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
        self.tokens = [t for t in tokens if t] # 过滤空token
        self.token_index = 0

    def _get_next_token(self) -> str:
        """获取下一个 Token 并循环"""
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
                "Accept": "application/vnd.github.v3+json"
            }
            if headers:
                current_headers.update(headers) 
            
            try:
                # 确保在没有 token 的情况下也能发起请求（但会迅速达到低速率限制）
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

def get_external_contributions(client: GitHubAPIClient, username: str) -> Dict[str, int]:
    """
    通过 GitHub Events API 统计用户在**过去一年**的外部贡献。
    注意：Events API 限制最多只能返回过去 90 天的 300 条记录。
    为了获取更准确的年度数据，需要更复杂的GraphQL查询或依赖其他数据源。
    这里我们使用 Events API 作为**活跃度近似值**。
    """
    
    # 统计指标初始化
    accepted_pr_count = 0 
    issue_creation_count = 0
    
    # 获取用户拥有的仓库列表，用于判断项目是否为“外部”
    user_repos = set()
    try:
        repos_resp = client.get(f"/users/{username}/repos", params={'type': 'owner', 'per_page': 100})
        repos_resp.raise_for_status()
        user_repos = set(repo['full_name'] for repo in repos_resp.json())
    except Exception as e:
        print(f"Warning: Could not fetch repo list for {username}. Error: {e}")

    # 获取用户活动事件流 (Events API)
    page = 1
    # 警告：此 API 只能抓取最多 300 条或 90 天的数据，不适合精确年度统计
    # 但在没有 OpenDigger 活跃度数据时，是一个可行的近似方案。
    while page <= 10: # 限制页数，防止过度请求
        endpoint = f"/users/{username}/events/public"
        response = client.get(endpoint, params={'per_page': 100, 'page': page})
        
        if response.status_code != 200:
            print(f"Error fetching events for {username} (Page {page}): {response.status_code}")
            break
            
        try:
            events = response.json()
        except requests.exceptions.JSONDecodeError:
            print(f"Error decoding JSON for events of {username}. Skipping page {page}.")
            break

        if not events:
            break
            
        for event in events:
            repo_full_name = event.get('repo', {}).get('name', '')
            
            # 判断是否为外部项目：项目名称不在用户的仓库列表中
            is_external_repo = repo_full_name and repo_full_name not in user_repos and not repo_full_name.startswith(f"{username}/")

            if event['type'] == 'PullRequestEvent' and is_external_repo:
                payload = event.get('payload', {})
                # 统计被接受/合并的外部 PR
                if payload.get('action') == 'closed' and payload.get('pull_request', {}).get('merged') == True:
                    accepted_pr_count += 1
            
            elif event['type'] == 'IssuesEvent' and event.get('payload', {}).get('action') == 'opened':
                 # 统计创建的 Issue 数量
                 issue_creation_count += 1
            
        page += 1
        
        # 如果当前页返回少于 100 条，可能已达历史尽头
        if len(events) < 100:
            break

    return {
        "accepted_external_prs": accepted_pr_count,
        "created_issues": issue_creation_count,
        # 实际抓取到的事件总数，供参考
        "events_fetched": (page - 1) * 100 + len(events)
    }


# -- 4. 核心计算函数 --

def calculate_contribution_score(metrics: Dict[str, int]) -> float:
    """
    计算百分制的社区贡献分数。
    
    假设权重:
    - 外部 PR 数量: 70%
    - Issue 数量: 30%
    """
    
    prs = metrics.get('accepted_external_prs', 0)
    issues = metrics.get('created_issues', 0)
    
    # 假设最大值 (需要根据全部用户数据计算)
    MAX_PRS = 50       # 假设最高贡献用户有 50 个外部 PR
    MAX_ISSUES = 100   # 假设最高贡献用户有 100 个创建 Issue
    
    # 归一化 (Normalization)
    norm_prs = min(1.0, prs / MAX_PRS)
    norm_issues = min(1.0, issues / MAX_ISSUES)
    
    # 加权求和 (Weighted Sum)
    score = (norm_prs * 0.70) + (norm_issues * 0.30)
    
    # 转换为百分制
    contribution_score = round(score * 100, 2)
    
    return contribution_score

# -- 5. 主执行逻辑 --

def collect_contribution_data(username: str):
    """
    收集单个用户的社区贡献数据，并计算分数。
    """
    
    # 1. 创建用户数据目录
    user_data_dir = os.path.join(BASE_USER_DATA_DIR, username)
    if not os.path.exists(user_data_dir):
        os.makedirs(user_data_dir)
        
    output_file = os.path.join(user_data_dir, f"{username}_contribution.json")
    
    if os.path.exists(output_file):
        print(f"Contribution data for {username} already exists. Skipping.")
        return

    print(f"Collecting Contribution data for {username}...")
    
    # 2. 初始化 API 客户端
    client = GitHubAPIClient(TOKENS)
    
    # 3. 收集原始指标
    raw_metrics = get_external_contributions(client, username)
    
    # 4. 计算最终得分
    contribution_score = calculate_contribution_score(raw_metrics)
    
    # 5. 整理最终数据结构
    final_data = {
        "username": username,
        "raw_metrics": raw_metrics,
        "contribution_score_100": contribution_score
    }
    
    # 6. 保存到文件
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(final_data, f, indent=2, ensure_ascii=False)
        print(f"SUCCESS: {username} 的社区贡献数据已保存到 {output_file}，得分: {contribution_score}")
    except Exception as e:
        print(f"ERROR: 写入文件失败 {output_file}: {e}")

def main():
    # 从用户列表文件加载所有目标用户
    try:
        with open(USER_LIST_FILE, 'r', encoding='utf-8') as f:
            target_users = json.load(f)
    except Exception:
        print(f"Error: Could not load users from {USER_LIST_FILE}. Using sample.")
        target_users = ["torvalds"] 

    # 循环处理所有目标用户
    for username in target_users:
        collect_contribution_data(username)

if __name__ == "__main__":
    main()
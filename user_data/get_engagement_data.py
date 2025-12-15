# ./user_data/get_engagement_data.py

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
                "Accept": "application/vnd.github.v3+json"
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

def get_engagement_metrics(client: GitHubAPIClient, username: str) -> Dict[str, int]:
    """
    通过 GitHub Events API 统计用户在 Issues/PR 上的评论互动数量。
    """
    
    # 统计指标初始化
    issue_comment_count = 0 
    pr_review_comment_count = 0 # 这是代码审查提供的评论，同时可作为代码能力（Code Quality）的辅助指标
    
    # 获取用户活动事件流 (Events API)
    page = 1
    # 警告：Events API 最多只能抓取最多 300 条或 90 天的数据
    while page <= 10: 
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
            if event['type'] == 'IssueCommentEvent':
                # 统计对 Issue 的评论
                issue_comment_count += 1
            
            elif event['type'] == 'PullRequestReviewCommentEvent':
                 # 统计对 PR 的审查评论
                 pr_review_comment_count += 1
            
        page += 1
        
        if len(events) < 100:
            break

    return {
        "issue_comment_count": issue_comment_count,
        "pr_review_comment_count": pr_review_comment_count,
        "events_fetched": (page - 1) * 100 + len(events)
    }


# -- 4. 核心计算函数 --

def calculate_engagement_score(metrics: Dict[str, int]) -> float:
    """
    计算百分制的社区互动分数。
    
    假设权重:
    - Issue 评论数量 (问题解决/讨论): 60%
    - PR 审查评论数量 (代码质量交流): 40%
    """
    
    issue_comments = metrics.get('issue_comment_count', 0)
    pr_comments = metrics.get('pr_review_comment_count', 0)
    
    # 假设最大值 (需要根据全部用户数据计算)
    MAX_ISSUE_COMMENTS = 500       # 假设最高互动用户有 500 条 Issue 评论
    MAX_PR_COMMENTS = 200          # 假设最高互动用户有 200 条 PR 审查评论
    
    # 归一化 (Normalization)
    norm_issue = min(1.0, issue_comments / MAX_ISSUE_COMMENTS)
    norm_pr = min(1.0, pr_comments / MAX_PR_COMMENTS)
    
    # 加权求和 (Weighted Sum)
    score = (norm_issue * 0.60) + (norm_pr * 0.40)
    
    # 转换为百分制
    engagement_score = round(score * 100, 2)
    
    return engagement_score

# -- 5. 主执行逻辑 --

def collect_engagement_data(username: str):
    """
    收集单个用户的社区互动数据，并计算分数。
    """
    
    # 1. 创建用户数据目录
    user_data_dir = os.path.join(BASE_USER_DATA_DIR, username)
    if not os.path.exists(user_data_dir):
        os.makedirs(user_data_dir)
        
    output_file = os.path.join(user_data_dir, f"{username}_engagement.json")
    
    if os.path.exists(output_file):
        print(f"Engagement data for {username} already exists. Skipping.")
        return

    print(f"Collecting Engagement data for {username}...")
    
    # 2. 初始化 API 客户端
    client = GitHubAPIClient(TOKENS)
    
    # 3. 收集原始指标
    raw_metrics = get_engagement_metrics(client, username)
    
    # 4. 计算最终得分
    engagement_score = calculate_engagement_score(raw_metrics)
    
    # 5. 整理最终数据结构
    final_data = {
        "username": username,
        "raw_metrics": raw_metrics,
        "engagement_score_100": engagement_score
    }
    
    # 6. 保存到文件
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(final_data, f, indent=2, ensure_ascii=False)
        print(f"SUCCESS: {username} 的社区互动数据已保存到 {output_file}，得分: {engagement_score}")
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
        collect_engagement_data(username)

if __name__ == "__main__":
    main()
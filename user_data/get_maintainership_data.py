# ./user_data/get_maintainership_data.py

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

def get_maintainership_metrics(client: GitHubAPIClient, username: str) -> Dict[str, int]:
    """
    通过 GitHub Events API 统计用户作为维护者合并他人 PR 的数量。
    """
    
    # 统计指标初始化
    merged_external_pr_count = 0 
    
    # 获取用户活动事件流 (Events API)
    page = 1
    # 警告：Events API 只能抓取最多 300 条或 90 天的数据
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
            if event['type'] == 'PullRequestEvent':
                payload = event.get('payload', {})
                pr = payload.get('pull_request', {})
                
                # 核心逻辑：判断用户是否是合并者 (Merger)
                if payload.get('action') == 'closed' and pr.get('merged') == True:
                    # 检查 PR 的作者是否不是当前用户
                    pr_author = pr.get('user', {}).get('login')
                    
                    if pr_author != username:
                        # 这是一个用户合并了别人 PR 的事件
                        # 注意：Events API 的 PR Event 并不直接显示是谁合并的，它只显示 PR 被关闭/合并了
                        # 更好的方法是使用 Search API (Search API速率限制更高，先使用 Events 提供的近似值)
                        
                        # 优化：对于 Events API，我们假定 'PullRequestEvent' 的 actor 是事件的触发者。
                        # 如果用户合并了别人的 PR，events stream 中不会直接显示 'Merged by {user}'
                        # 而是显示 'PullRequestEvent'，且 payload 中 merged_by 字段可能存在。
                        
                        # **更准确的判断方法 (Search API - 简化):**
                        # 我们依赖于一个事实：如果用户在 Event Stream 中有大量的 'PullRequestReviewEvent' 或 'IssueCommentEvent' 
                        # 但没有自己的 PR，却拥有大量代码提交，他很可能是一个维护者。
                        
                        # **我们使用一个更稳健的代理指标：用户合并的PR数量 (通过其作为PR的合并者)
                        # 我们假设 PR 合并事件是由用户触发的。
                        
                        # 在缺乏 'merged_by' 字段的 Events API 中，我们不得不使用近似：
                        # 在大型项目中，只有核心维护者才能关闭/合并 PR。
                        
                        # **替代方案：使用 Issue/PR 数量来代替，这在我们的 get_contribution_data.py 中已经完成。**
                        
                        # 鉴于 Events API 的局限性，我们只能计算用户作为 actor 参与的 PR 合并事件。
                        # 这是一个极大的简化，但对于 Torvalds 这样的用户，能反映他所管理的项目的活动。
                        
                        merged_external_pr_count += 1
            
        page += 1
        
        if len(events) < 100:
            break

    return {
        "merged_external_pr_count_approx": merged_external_pr_count,
        "events_fetched": (page - 1) * 100 + len(events)
    }


# -- 4. 核心计算函数 --

def calculate_maintainership_score(metrics: Dict[str, int]) -> float:
    """
    计算百分制的维护者职责分数。
    
    假设权重:
    - 合并他人 PR 数量: 100% (核心衡量指标)
    """
    
    merged_count = metrics.get('merged_external_pr_count_approx', 0)
    
    # 假设最大值 (需要根据全部用户数据计算)
    MAX_MERGED_PRS = 500       # 假设最高维护者用户在 90 天内合并 500 个 PR
    
    # 归一化 (Normalization)
    norm_merged = min(1.0, merged_count / MAX_MERGED_PRS)
    
    # 转换为百分制
    maintainership_score = round(norm_merged * 100, 2)
    
    return maintainership_score

# -- 5. 主执行逻辑 (不变) --

def collect_maintainership_data(username: str):
    
    user_data_dir = os.path.join(BASE_USER_DATA_DIR, username)
    if not os.path.exists(user_data_dir):
        os.makedirs(user_data_dir)
        
    output_file = os.path.join(user_data_dir, f"{username}_maintainership.json")
    
    if os.path.exists(output_file):
        print(f"Maintainership data for {username} already exists. Skipping.")
        return

    print(f"Collecting Maintainership data for {username}...")
    
    client = GitHubAPIClient(TOKENS)
    raw_metrics = get_maintainership_metrics(client, username)
    maintainership_score = calculate_maintainership_score(raw_metrics)
    
    final_data = {
        "username": username,
        "raw_metrics": raw_metrics,
        "maintainership_score_100": maintainership_score
    }
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(final_data, f, indent=2, ensure_ascii=False)
        print(f"SUCCESS: {username} 的维护者职责数据已保存到 {output_file}，得分: {maintainership_score}")
    except Exception as e:
        print(f"ERROR: 写入文件失败 {output_file}: {e}")

def main():
    try:
        with open(USER_LIST_FILE, 'r', encoding='utf-8') as f:
            target_users = json.load(f)
    except Exception:
        print(f"Error: Could not load users from {USER_LIST_FILE}. Using sample.")
        target_users = ["torvalds", "yyx990803", "gaearon"] 

    for username in target_users:
        collect_maintainership_data(username)

if __name__ == "__main__":
    main()
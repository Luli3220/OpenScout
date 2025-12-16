# get_user_micro_data.py

import requests
import json
import time
import os
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor

# -- 1. 配置与常量 --
GITHUB_API_BASE = "https://api.github.com"

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SRC_DIR)
DATA_DIR = os.path.join(ROOT_DIR, "data")
CONFIG_FILE = os.path.join(ROOT_DIR, "config.json")

OUTPUT_DIR = os.path.join(DATA_DIR, "micro_data")
USER_LIST_FILE = os.path.join(DATA_DIR, "users_list.json")

# Load tokens from config.json
TOKENS = []
if os.path.exists(CONFIG_FILE):
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
            TOKENS = config.get("github_tokens", [])
    except Exception as e:
        print(f"Error loading config.json: {e}")

if not TOKENS:
    # Fallback to env var or empty list
    TOKENS = os.getenv("GITHUB_TOKENS", "").split(',')
    TOKENS = [t for t in TOKENS if t] # Filter empty strings

if not TOKENS:
    print("Warning: No GitHub tokens found in config.json or environment variables.")


# -- 2. GitHub API 客户端类（关键：Token 轮询） --
class GitHubAPIClient:
    """管理 GitHub API 请求和 Token 轮询"""
    def __init__(self, tokens: List[str]):
        # 线程安全地管理 Token 索引
        self.tokens = tokens
        self.token_index = 0

    def _get_next_token(self) -> str:
        """获取下一个 Token 并循环"""
        token = self.tokens[self.token_index]
        self.token_index = (self.token_index + 1) % len(self.tokens)
        return token
    
    # 修正后的 get 方法：现在正确接受 headers 参数
    def get(self, endpoint: str, params: Dict[str, Any] = None, headers: Dict[str, str] = None) -> requests.Response:
        """执行 API GET 请求，并处理速率限制和 Token 轮询"""
        url = f"{GITHUB_API_BASE}{endpoint}"
        
        while True:
            token = self._get_next_token()
            
            # 1. 初始化基础头部
            current_headers = {
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json" # 默认请求 JSON 格式
            }
            
            # 2. 合并自定义头部 (在本次修复中，这个 headers 参数不再用于获取 Commit Patch)
            if headers:
                current_headers.update(headers) 
            
            # 使用合并后的头部发起请求
            response = requests.get(url, headers=current_headers, params=params, timeout=15)
            
            # 检查速率限制
            if response.status_code == 403 and 'rate limit exceeded' in response.text:
                reset_time = int(response.headers.get('X-RateLimit-Reset', time.time() + 60))
                sleep_duration = reset_time - time.time()
                print(f"Token {token[:4]}... 速率限制，等待 {sleep_duration:.2f} 秒...")
                
                # 阻塞等待，然后继续循环尝试下一个 Token
                time.sleep(sleep_duration + 5) 
                continue 
            
            return response

# -- 3. 数据抓取逻辑函数 --

def get_user_repos(client: GitHubAPIClient, username: str) -> List[Dict[str, Any]]:
    """
    1. 抓取用户的所有仓库。
    2. 过滤掉 Fork 仓库，只保留有效的、有贡献的仓库。
    """
    all_repos = []
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
        
        # 过滤有效仓库: 只收集非 Fork 的仓库
        effective_repos = [repo for repo in repos if repo.get('fork') == False]
        all_repos.extend(effective_repos)
        page += 1
        
        # 检查是否还有下一页
        if 'next' not in response.links:
             break
             
    print(f"找到 {username} 的有效仓库 {len(all_repos)} 个。")
    return all_repos

def get_repo_commits(client: GitHubAPIClient, owner: str, repo_name: str) -> List[Dict[str, Any]]:
    """
    抓取单个仓库的所有 Commit Message 和 Diff/Patch 数据。
    Commit Message 用于语义分析，Diff/Patch 用于精炼技能。
    """
    commits = []
    page = 1
    while True:
        # API: GET /repos/{owner}/{repo}/commits
        response = client.get(f"/repos/{owner}/{repo_name}/commits", params={'per_page': 100, 'page': page})
        if response.status_code != 200:
            # 捕获 409 Conflict 错误 (空仓库/归档仓库)
            if response.status_code == 409:
                print(f"Error fetching commits for {owner}/{repo_name}: 409 (Conflict - likely empty or archived repo). Skipping.")
            else:
                print(f"Error fetching commits for {owner}/{repo_name}: {response.status_code}")
            break
            
        try:
            page_commits = response.json()
        except requests.exceptions.JSONDecodeError:
            print(f"Error decoding JSON for commit list of {owner}/{repo_name}. Status: {response.status_code}")
            break
            
        if not page_commits:
            break
        
        # 必须抓取完整的 Commit 详情（包含 Patch/Diff）
        for commit_summary in page_commits:
            if 'sha' not in commit_summary:
                 print("Warning: Commit summary missing SHA. Skipping.")
                 continue
                 
            sha = commit_summary['sha']
            
            # API: GET /repos/{owner}/{repo}/commits/{ref} - 获取完整的 Commit 详情
            # =================================================================
            # 核心修正：移除 headers={"Accept": "application/vnd.github.v3.patch"}
            # 确保返回 JSON，JSON中包含所需的 files[].patch 字段
            # =================================================================
            commit_detail_resp = client.get(
                f"/repos/{owner}/{repo_name}/commits/{sha}" 
            ) 
            
            if commit_detail_resp.status_code == 200:
                try:
                    # 现在应该能成功解析 JSON
                    commit_data = commit_detail_resp.json()
                except requests.exceptions.JSONDecodeError:
                    # 只有在 API 结构发生变化或请求异常时才会出现，打印错误并跳过
                    print(f"Warning: Failed to decode JSON for commit {sha}. Skipping detail fields.")
                    continue
                    
                # 存储原始的 Commit Message 和 关键的 files/patch 信息
                commits.append({
                    "sha": sha,
                    "message": commit_data['commit']['message'] if commit_data.get('commit') else 'N/A',
                    "author": commit_data['commit']['author']['name'] if commit_data.get('commit') and commit_data['commit'].get('author') else 'N/A',
                    # 从 JSON 结构中提取 files 数组，其中每个文件对象都应包含 patch 字段
                    "files": [{"filename": f['filename'], "patch": f.get('patch', 'No diff')} for f in commit_data.get('files', [])] 
                })
            else:
                 print(f"Warning: Failed to get full commit detail for {sha} ({commit_detail_resp.status_code})")

        page += 1
        
        if len(page_commits) < 100: # 快速退出条件
             break
        if page > 10: # **重要：设置最大 Commit 抓取限制**
            print(f"Warning: Reached max commit page limit for {owner}/{repo_name}")
            break

    return commits

# -- 4. 主执行函数 --
def collect_micro_data_for_user(client: GitHubAPIClient, username: str) -> Dict[str, Any]:
    """收集单个用户的完整微观数据"""
    
    user_data = {"username": username, "repos": []}
    
    # 1. 抓取用户的有效仓库列表
    repos = get_user_repos(client, username)
    
    for repo in repos:
        repo_name = repo['name']
        print(f"-> Collecting commits for {username}/{repo_name}...")
        
        # 2. 抓取每个有效仓库的 Commit 数据
        commits = get_repo_commits(client, username, repo_name)
        
        user_data["repos"].append({
            "name": repo_name,
            "description": repo.get('description'),
            "language": repo.get('language'),
            "commits": commits
        })
        
    return user_data

def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        
    # 初始化 API 客户端（包含 Token 轮询逻辑）
    client = GitHubAPIClient(TOKENS)
    
    # 从 get_user_name.py 的输出文件中加载用户列表
    try:
        with open(USER_LIST_FILE, 'r', encoding='utf-8') as f:
            target_users = json.load(f)
    except Exception:
        print(f"Error: Could not load users from {USER_LIST_FILE}. Using sample.")
        target_users = ["torvalds", "yyx990803"]

    # 只取前 100 个用户进行测试
    target_users = target_users[:100]

    print(f"Targeting {len(target_users)} users for micro data collection...")

    # 使用多线程/多进程进一步加速整个用户列表的抓取
    # 限制并发数以保护网络和 API 
    MAX_WORKERS = len(TOKENS) * 2 # 例如，并发数设置为 Token 数量的两倍
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_user = {
            executor.submit(collect_micro_data_for_user, client, user): user 
            for user in target_users
        }
        
        for future in future_to_user:
            username = future_to_user[future]
            try:
                result = future.result()
                output_file = os.path.join(OUTPUT_DIR, f"{username}_micro_data.json")
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)
                print(f"SUCCESS: {username} 数据已保存到 {output_file}")
            except Exception as exc:
                print(f"ERROR: {username} 抓取失败: {exc}")

if __name__ == "__main__":
    main()
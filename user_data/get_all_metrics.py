import requests
import json
import os
import time
from typing import Dict, Any, List, Set
from tqdm import tqdm

# -- 1. 配置与常量 --
GITHUB_API_BASE = "https://api.github.com"
OPENDIGGER_API_BASE = "https://oss.x-lab.info/open_digger/github" 
USER_LIST_FILE = "./users_list.json" 
BASE_USER_DATA_DIR = "./user_data" 
FORCE_UPDATE = True # Force re-fetch even if data exists

# 从环境变量读取 GitHub Tokens
TOKENS = "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"

# -- 2. GitHub API 客户端类 --
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
                "Accept": "application/vnd.github.v3+json"
            }
            if token:
                current_headers["Authorization"] = f"token {token}"
                
            if headers:
                current_headers.update(headers) 
            
            try:
                response = requests.get(url, headers=current_headers, params=params, timeout=15)
                
                if response.status_code == 403 and 'rate limit exceeded' in response.text:
                    reset_time = int(response.headers.get('X-RateLimit-Reset', time.time() + 60))
                    sleep_duration = reset_time - time.time()
                    if sleep_duration < 0: sleep_duration = 60
                    print(f"Token {token[:4]}... 速率限制，等待 {sleep_duration:.2f} 秒...")
                    time.sleep(sleep_duration + 5) 
                    continue 
                
                return response
            except requests.exceptions.RequestException as e:
                print(f"Request error: {e}. Retrying...")
                time.sleep(5)
                continue

# -- 3. 各维度数据获取函数 --

# --- 3.1 影响力 (Influence) ---
def get_opendigger_data(username: str) -> Dict[str, Any]:
    endpoint = f"/user/{username}/openrank"
    url = f"{OPENDIGGER_API_BASE}{endpoint}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            latest_rank = data.get('data', [])[-1].get('openrank', 0) if data.get('data') else 0
            return {"openrank_value": latest_rank}
    except:
        pass
    return {"openrank_value": 0}

def get_influence_metrics(client: GitHubAPIClient, username: str) -> Dict[str, Any]:
    total_stars = 0
    total_forks = 0
    total_issues = 0
    page = 1
    while True:
        response = client.get(f"/users/{username}/repos", params={'type': 'owner', 'per_page': 100, 'page': page})
        if response.status_code != 200: break
        repos = response.json()
        if not repos: break
        for repo in repos:
            if repo.get('fork') == False:
                total_stars += repo.get('stargazers_count', 0)
                total_forks += repo.get('forks_count', 0)
                total_issues += repo.get('open_issues_count', 0)
        page += 1
        if 'next' not in response.links: break
    
    return {
        "total_stars": total_stars,
        "total_forks": total_forks,
        "total_open_issues": total_issues
    }

def calculate_influence_score(metrics: Dict[str, Any]) -> float:
    stars = metrics.get('total_stars', 0)
    forks = metrics.get('total_forks', 0)
    issues = metrics.get('total_open_issues', 0)
    
    MAX_STARS = 10000
    MAX_FORK_ISSUE = 2000
    
    norm_stars = min(1.0, stars / MAX_STARS)
    norm_fork_issue = min(1.0, (forks + issues) / MAX_FORK_ISSUE)
    
    score = (norm_stars * 0.60) + (norm_fork_issue * 0.40)
    return round(score * 100, 2)

# --- 3.2 贡献度 (Contribution) & 3.3 维护力 (Maintainership) & 3.4 活跃度 (Engagement) ---
# 这三个维度都依赖 Events API，为了节省请求，我们合并获取
def get_events_metrics(client: GitHubAPIClient, username: str, user_repos: Set[str]) -> Dict[str, Any]:
    metrics = {
        "accepted_external_prs": 0,
        "created_issues": 0,
        "merged_external_pr_count_approx": 0,
        "issue_comment_count": 0,
        "pr_review_comment_count": 0,
        "events_fetched": 0
    }
    
    page = 1
    total_events = 0
    while page <= 10: # 最多抓取 10 页 (1000条或90天)
        response = client.get(f"/users/{username}/events/public", params={'per_page': 100, 'page': page})
        if response.status_code != 200: break
        events = response.json()
        if not events: break
        
        total_events += len(events)
        
        for event in events:
            evt_type = event['type']
            payload = event.get('payload', {})
            repo_name = event.get('repo', {}).get('name', '')
            
            # Contribution: External PRs & Issues
            if evt_type == 'PullRequestEvent':
                # Check for External PR
                is_external = repo_name and repo_name not in user_repos and not repo_name.startswith(f"{username}/")
                if is_external and payload.get('action') == 'closed' and payload.get('pull_request', {}).get('merged') == True:
                    metrics["accepted_external_prs"] += 1
                
                # Maintainership: Merging others' PRs
                # 简化逻辑：如果在自己的仓库关闭并合并了别人的PR
                # 注意：Events API 不直接显示 'who merged'，但如果用户有 PullRequestEvent 且 action=closed, merged=true
                # 且 PR 作者不是自己，通常意味着该用户进行了合并操作（或者是维护者之一）
                if payload.get('action') == 'closed' and payload.get('pull_request', {}).get('merged') == True:
                    pr_author = payload.get('pull_request', {}).get('user', {}).get('login')
                    if pr_author != username:
                        metrics["merged_external_pr_count_approx"] += 1

            elif evt_type == 'IssuesEvent' and payload.get('action') == 'opened':
                 metrics["created_issues"] += 1
            
            # Engagement: Comments
            elif evt_type == 'IssueCommentEvent':
                metrics["issue_comment_count"] += 1
            elif evt_type == 'PullRequestReviewCommentEvent':
                metrics["pr_review_comment_count"] += 1
                
        page += 1
        if len(events) < 100: break
        
    metrics["events_fetched"] = total_events
    return metrics

def calculate_contribution_score(metrics: Dict[str, Any]) -> float:
    prs = metrics.get('accepted_external_prs', 0)
    issues = metrics.get('created_issues', 0)
    MAX_PRS = 50
    MAX_ISSUES = 100
    norm_prs = min(1.0, prs / MAX_PRS)
    norm_issues = min(1.0, issues / MAX_ISSUES)
    return round(((norm_prs * 0.70) + (norm_issues * 0.30)) * 100, 2)

def calculate_maintainership_score(metrics: Dict[str, Any]) -> float:
    merged = metrics.get('merged_external_pr_count_approx', 0)
    MAX_MERGED = 500
    norm_merged = min(1.0, merged / MAX_MERGED)
    return round(norm_merged * 100, 2)

def calculate_engagement_score(metrics: Dict[str, Any]) -> float:
    issue_comments = metrics.get('issue_comment_count', 0)
    pr_comments = metrics.get('pr_review_comment_count', 0)
    MAX_ISSUE_COMMENTS = 500
    MAX_PR_COMMENTS = 200
    norm_issue = min(1.0, issue_comments / MAX_ISSUE_COMMENTS)
    norm_pr = min(1.0, pr_comments / MAX_PR_COMMENTS)
    return round(((norm_issue * 0.60) + (norm_pr * 0.40)) * 100, 2)

# --- 3.5 多样性 (Diversity) ---
def get_diversity_metrics(client: GitHubAPIClient, username: str) -> Dict[str, Any]:
    distinct_languages = set() 
    distinct_topics = set()
    total_repos = 0
    
    page = 1
    while True:
        headers = {"Accept": "application/vnd.github.mercy-preview+json"} # For topics
        response = client.get(f"/users/{username}/repos", params={'type': 'owner', 'per_page': 100, 'page': page}, headers=headers)
        if response.status_code != 200: break
        repos = response.json()
        if not repos: break
        
        for repo in repos:
            if repo.get('fork') == False:
                total_repos += 1
                if repo.get('language'):
                    distinct_languages.add(repo['language'])
                for topic in repo.get('topics', []):
                    distinct_topics.add(topic)
        page += 1
        if 'next' not in response.links: break
        
    return {
        "distinct_languages": list(distinct_languages),
        "distinct_topics": list(distinct_topics),
        "language_count": len(distinct_languages),
        "topic_count": len(distinct_topics),
        "total_owned_repos": total_repos
    }

def calculate_diversity_score(metrics: Dict[str, Any]) -> float:
    lang_count = metrics.get('language_count', 0)
    topic_count = metrics.get('topic_count', 0)
    MAX_LANG = 10
    MAX_TOPICS = 50
    norm_lang = min(1.0, lang_count / MAX_LANG)
    norm_topic = min(1.0, topic_count / MAX_TOPICS)
    return round(((norm_lang * 0.60) + (norm_topic * 0.40)) * 100, 2)

# -- 4. 主流程 --
def process_user(username: str, client: GitHubAPIClient):
    user_dir = os.path.join(BASE_USER_DATA_DIR, username)
    if not os.path.exists(user_dir):
        os.makedirs(user_dir)
    
    # Check if all files exist
    files = [
        f"{username}_influence.json",
        f"{username}_contribution.json",
        f"{username}_maintainership.json",
        f"{username}_engagement.json",
        f"{username}_diversity.json"
    ]
    
    if not FORCE_UPDATE and all(os.path.exists(os.path.join(user_dir, f)) for f in files):
        return # Skip if all data exists

    # 1. Fetch Repos List (Required for multiple metrics)
    user_repos = set()
    try:
        # Quick fetch for repo names to assist event filtering
        page = 1
        while True:
            r = client.get(f"/users/{username}/repos", params={'type': 'owner', 'per_page': 100, 'page': page})
            if r.status_code != 200: break
            repos = r.json()
            if not repos: break
            for repo in repos: user_repos.add(repo['full_name'])
            if 'next' not in r.links: break
            page += 1
    except:
        pass

    # 2. Collect Data
    # Influence
    od_metrics = get_opendigger_data(username)
    inf_metrics = get_influence_metrics(client, username)
    inf_metrics.update(od_metrics)
    inf_score = calculate_influence_score(inf_metrics)
    
    # Events based (Contribution, Maintainership, Engagement)
    evt_metrics = get_events_metrics(client, username, user_repos)
    cont_score = calculate_contribution_score(evt_metrics)
    maint_score = calculate_maintainership_score(evt_metrics)
    eng_score = calculate_engagement_score(evt_metrics)
    
    # Diversity
    div_metrics = get_diversity_metrics(client, username)
    div_score = calculate_diversity_score(div_metrics)
    
    # 3. Save Files
    save_data(username, "influence", inf_metrics, inf_score)
    save_data(username, "contribution", evt_metrics, cont_score) # Reuse event metrics subset
    save_data(username, "maintainership", evt_metrics, maint_score) # Reuse event metrics subset
    save_data(username, "engagement", evt_metrics, eng_score) # Reuse event metrics subset
    save_data(username, "diversity", div_metrics, div_score)

def save_data(username, dimension, metrics, score):
    data = {
        "username": username,
        "raw_metrics": metrics,
        f"{dimension}_score_100": score
    }
    path = os.path.join(BASE_USER_DATA_DIR, username, f"{username}_{dimension}.json")
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def main():
    if not os.path.exists(USER_LIST_FILE):
        print(f"User list file {USER_LIST_FILE} not found.")
        return

    with open(USER_LIST_FILE, 'r', encoding='utf-8') as f:
        users = json.load(f)
    
    client = GitHubAPIClient(TOKENS)
    
    print(f"Starting comprehensive 5-dimension scan for {len(users)} users...")
    for user in tqdm(users, desc="Processing Users"):
        try:
            process_user(user, client)
        except Exception as e:
            # print(f"Error processing {user}: {e}")
            pass

if __name__ =
import requests
import json
import os
import time
from typing import List, Dict, Any, Optional, Set
from tqdm import tqdm

# --- Constants ---
GITHUB_API_BASE = "https://api.github.com"
ALLOWED_EXTENSIONS = {'.py', '.js', '.ts', '.go', '.rs', '.java', '.cpp', '.c', '.rb'}
IGNORED_EXTENSIONS = {'.md', '.json', '.lock', '.txt', 'config.yaml'}
IGNORED_DIRS = {'dist/', 'vendor/'}

MAX_PATCH_LENGTH = 1000
MAX_TOTAL_LENGTH = 6000

# --- GitHub API Client ---
class GitHubAPIClient:
    """Manages GitHub API requests with token rotation and rate limiting."""
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
        url = f"{GITHUB_API_BASE}{endpoint}" if not endpoint.startswith("http") else endpoint
        
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
                    print(f"Token {token[:4]}... rate limit exceeded, waiting {sleep_duration:.2f} seconds...")
                    time.sleep(sleep_duration + 5) 
                    continue 
                
                return response
            except requests.exceptions.RequestException as e:
                print(f"Request error: {e}. Retrying...")
                time.sleep(5)
                continue

# --- Helper Functions ---
def is_valid_file(filename: str) -> bool:
    """Checks if file is allowed based on extension and directory."""
    if any(filename.startswith(d) for d in IGNORED_DIRS):
        return False
    
    ext = os.path.splitext(filename)[1].lower()
    if ext in IGNORED_EXTENSIONS:
        return False
    
    return ext in ALLOWED_EXTENSIONS

def fetch_agent_b_context(client: GitHubAPIClient, username: str) -> Optional[str]:
    """
    Fetches code quality audit context (patches) for a user.
    Returns a formatted string or None if no valid data found.
    """
    prs_to_check = []
    
    # Strategy 1: External PRs (repo.owner.login != username)
    page = 1
    found_external = False
    
    # We use search API for better filtering of PRs
    # q=author:username type:pr is:merged -user:username
    search_query = f"author:{username} type:pr is:merged -user:{username} sort:updated-desc"
    
    try:
        response = client.get("/search/issues", params={'q': search_query, 'per_page': 10})
        if response.status_code == 200:
            items = response.json().get('items', [])
            if items:
                # Get repo details for sorting by stars (search API doesn't give repo stars directly in items mostly)
                # But to save API calls, we can trust 'sort:updated' or just take the first few
                # The requirement says "Sort by Stars descending". 
                # To do this accurately, we need to fetch repo info for each PR, which is expensive.
                # Optimization: Fetch top 10, group by repo, fetch repo info, then sort.
                
                repo_stars_cache = {}
                candidates = []
                
                for item in items:
                    repo_url = item.get('repository_url') # https://api.github.com/repos/owner/repo
                    if not repo_url: continue
                    
                    if repo_url not in repo_stars_cache:
                        r_resp = client.get(repo_url)
                        if r_resp.status_code == 200:
                            repo_stars_cache[repo_url] = r_resp.json().get('stargazers_count', 0)
                        else:
                            repo_stars_cache[repo_url] = 0
                    
                    candidates.append({
                        'pr': item,
                        'stars': repo_stars_cache[repo_url],
                        'repo_url': repo_url
                    })
                
                # Sort by stars desc
                candidates.sort(key=lambda x: x['stars'], reverse=True)
                prs_to_check = [c['pr'] for c in candidates[:3]]
                found_external = True
    except Exception as e:
        print(f"Error searching external PRs: {e}")

    # Strategy 2: Internal PRs (Fallback)
    if not prs_to_check:
        # Find user's own highest starred repo
        try:
            r_resp = client.get(f"/users/{username}/repos", params={'type': 'owner', 'sort': 'stars', 'direction': 'desc', 'per_page': 1})
            if r_resp.status_code == 200:
                repos = r_resp.json()
                if repos:
                    best_repo = repos[0]
                    repo_name = best_repo['name']
                    # Get recent merged PRs from this repo
                    p_resp = client.get(f"/repos/{username}/{repo_name}/pulls", params={'state': 'closed', 'sort': 'updated', 'direction': 'desc', 'per_page': 10})
                    if p_resp.status_code == 200:
                        all_prs = p_resp.json()
                        # Filter for merged
                        merged_prs = [p for p in all_prs if p.get('merged_at')]
                        prs_to_check = merged_prs[:3]
        except Exception as e:
             print(f"Error fetching internal PRs: {e}")

    if not prs_to_check:
        return None

    # Fetch Patches
    final_output = ""
    total_length = 0
    
    for pr in prs_to_check:
        if total_length >= MAX_TOTAL_LENGTH:
            break
            
        # Parse PR info
        # Search API structure vs Repos API structure might differ slightly, but 'pull_request' key usually exists in search
        # or we use the 'pull_request' url.
        # Actually 'item' from search IS an issue object, but has 'pull_request' key.
        # We need to call the pull request endpoint to get files url or just construct it.
        
        # Standardize repo name and pr number
        # item['repository_url'] -> .../repos/owner/repo
        # item['number'] -> 123
        
        repo_url = pr.get('repository_url') # For search results
        if not repo_url:
            # Try 'base' for standard PR objects
            repo_url = pr.get('base', {}).get('repo', {}).get('url')
            
        if not repo_url: continue
        
        # Extract owner/repo string for display
        repo_full_name = repo_url.replace(GITHUB_API_BASE + "/repos/", "")
        pr_number = pr.get('number')
        
        # Get Repo Stars (if not cached)
        stars = 0
        try:
            s_resp = client.get(repo_url)
            if s_resp.status_code == 200:
                stars = s_resp.json().get('stargazers_count', 0)
        except:
            pass
            
        header = f"\n=== PR #{pr_number} in {repo_full_name} (Stars: {stars}) ===\n"
        if total_length + len(header) > MAX_TOTAL_LENGTH:
            break
        final_output += header
        total_length += len(header)
        
        # Get Files
        try:
            # endpoint: /repos/{owner}/{repo}/pulls/{number}/files
            files_url = f"/repos/{repo_full_name}/pulls/{pr_number}/files"
            f_resp = client.get(files_url)
            if f_resp.status_code == 200:
                files = f_resp.json()
                
                for f in files:
                    if total_length >= MAX_TOTAL_LENGTH: break
                    
                    filename = f.get('filename', '')
                    patch = f.get('patch', '')
                    
                    if not is_valid_file(filename) or not patch:
                        continue
                        
                    # Truncate Patch
                    if len(patch) > MAX_PATCH_LENGTH:
                        patch = patch[:MAX_PATCH_LENGTH] + "\n... (truncated)"
                        
                    file_block = f"File: {filename}\nPatch:\n{patch}\n\n"
                    
                    if total_length + len(file_block) > MAX_TOTAL_LENGTH:
                        break
                        
                    final_output += file_block
                    total_length += len(file_block)
                    
        except Exception as e:
            print(f"Error fetching files for PR {pr_number}: {e}")
            
    return final_output if final_output else None

# --- Main Execution ---
def main():
    # Setup Paths
    current_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(current_dir)
    config_file = os.path.join(root_dir, "config.json")
    user_list_file = os.path.join(root_dir, "data", "users_list.json")
    
    # Load Tokens
    tokens = []
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                tokens = config.get("github_tokens", [])
                if not tokens and config.get("github_token"):
                    tokens = [config.get("github_token")]
        except Exception as e:
            print(f"Error loading config.json: {e}")
    
    if not tokens:
        print("No tokens found. Exiting.")
        return

    # Load Users
    if not os.path.exists(user_list_file):
        print(f"User list file not found: {user_list_file}")
        return
        
    with open(user_list_file, 'r', encoding='utf-8') as f:
        users = json.load(f)
        
    # Init Client
    client = GitHubAPIClient(tokens)
    
    # Process First 5 Users
    print(f"--- Starting Agent B Context Fetch for Top 5 Users ---\n")
    test_users = users
    
    raw_users_dir = os.path.join(root_dir, "data", "raw_users")
    if not os.path.exists(raw_users_dir):
        os.makedirs(raw_users_dir)

    for user in tqdm(test_users, desc="Fetching Agent B Context"):
        try:
            user_dir = os.path.join(raw_users_dir, user)
            if not os.path.exists(user_dir):
                os.makedirs(user_dir)
                
            output_file = os.path.join(user_dir, "agent_b_context.json")
            
            context_str = fetch_agent_b_context(client, user)
            
            # Save as JSON object
            data_to_save = {
                "username": user,
                "agent_b_context": context_str # Can be None
            }
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"Error processing {user}: {e}")

if __name__ == "__main__":
    main()

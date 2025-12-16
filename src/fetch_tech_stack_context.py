import requests
import base64
import json
import os
import time
from typing import List, Dict, Any, Optional
from tqdm import tqdm

# --- Constants ---
GITHUB_API_BASE = "https://api.github.com"
TARGET_FILES = [
    # Dependency Management
    "package.json", "go.mod", "pom.xml", "requirements.txt", "Cargo.toml", "Gemfile",
    # Engineering Configuration
    "Dockerfile", "docker-compose.yml", ".github/workflows/ci.yml",
    # Cloud Native Configuration
    "k8s.yaml", "helm/Chart.yaml"
]

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
def get_file_content(client: GitHubAPIClient, owner: str, repo: str, file_path: str) -> Optional[str]:
    """
    Fetches file content from GitHub, handles Base64 decoding, and truncates.
    Returns the processed content string or None if not found/error.
    """
    endpoint = f"/repos/{owner}/{repo}/contents/{file_path}"
    response = client.get(endpoint)
    
    if response.status_code == 200:
        data = response.json()
        if 'content' in data and data['encoding'] == 'base64':
            try:
                # Decode Base64
                decoded_bytes = base64.b64decode(data['content'])
                decoded_str = decoded_bytes.decode('utf-8', errors='replace')
                
                # Truncate to 200 lines or 3000 chars
                lines = decoded_str.split('\n')
                if len(lines) > 200:
                    decoded_str = '\n'.join(lines[:200]) + "\n... (truncated)"
                
                if len(decoded_str) > 3000:
                    decoded_str = decoded_str[:3000] + "\n... (truncated)"
                    
                return decoded_str
            except Exception as e:
                print(f"Error decoding/processing {file_path} in {owner}/{repo}: {e}")
                return None
        else:
            # Handle cases where content might not be base64 (unlikely for files via this API but possible)
            # or if file is too large (API returns 'size' but no 'content' if > 1MB)
             return None
    elif response.status_code == 404:
        return None
    else:
        # print(f"Failed to fetch {file_path} from {owner}/{repo}: {response.status_code}")
        return None

def fetch_top_original_repos_context(client: GitHubAPIClient, username: str) -> List[Dict[str, Any]]:
    """
    Fetches context for the top 3 original repositories of a user.
    Returns a list of dictionaries containing repo info and file contents.
    """
    # 1. Fetch User Repositories
    repos = []
    page = 1
    while True:
        response = client.get(f"/users/{username}/repos", params={'type': 'owner', 'per_page': 100, 'page': page})
        if response.status_code != 200:
            print(f"Error fetching repos for {username}: {response.status_code}")
            break
        
        page_data = response.json()
        if not page_data:
            break
            
        repos.extend(page_data)
        if 'next' not in response.links:
            break
        page += 1
    
    # 2. Filter and Sort
    original_repos = [r for r in repos if not r.get('fork', False)]
    # Sort by stars descending
    original_repos.sort(key=lambda x: x.get('stargazers_count', 0), reverse=True)
    
    # Top 3
    top_repos = original_repos[:3]
    
    result = []
    
    # 3. Process each repo
    for repo in top_repos:
        repo_pure_name = repo.get('name')
        
        repo_data = {
            "name": repo.get('full_name'),
            "stars": repo.get('stargazers_count', 0),
            "description": repo.get('description') or "无",
            "files": {}
        }
        
        for file_path in TARGET_FILES:
            content = get_file_content(client, username, repo_pure_name, file_path)
            repo_data["files"][file_path] = content # content is str or None (will be null in JSON)
            
        result.append(repo_data)
    
    return result

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
    
    # Process All Users
    print(f"--- Starting Technical Stack Analysis for {len(users)} Users ---\n")
    
    # Ensure raw_users directory exists
    raw_users_dir = os.path.join(root_dir, "data", "raw_users")
    if not os.path.exists(raw_users_dir):
        os.makedirs(raw_users_dir)

    for user in tqdm(users, desc="Fetching Tech Stacks"):
        # print(f"Processing user: {user}...")
        try:
            user_dir = os.path.join(raw_users_dir, user)
            if not os.path.exists(user_dir):
                os.makedirs(user_dir)
                
            output_file = os.path.join(user_dir, "tech_stack.json")
            
            # Skip if file already exists (optional, but good for resuming)
            # if os.path.exists(output_file):
            #     continue
                
            data = fetch_top_original_repos_context(client, user)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"Error processing {user}: {e}")

if __name__ == "__main__":
    main()

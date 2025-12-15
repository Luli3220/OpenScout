import requests
import time
import os
import json

# (其他辅助函数 load_existing_users, save_users, fetch_page 保持不变)

def load_existing_users(file_path):
    # ... (保持不变)
    if not os.path.exists(file_path):
        return set()
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return set(data)
            return set()
    except Exception as e:
        print(f"Warning: Could not load existing file {file_path}: {e}")
        return set()

def save_users(users, file_path):
    # ... (保持不变)
    sorted_users = sorted(list(users))
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(sorted_users, f, indent=2, ensure_ascii=False)

def fetch_page(query, page, token, per_page=100):
    # ... (保持不变)
    base_url = "https://api.github.com/search/users"
    headers = {
        "Accept": "application/vnd.github.v3+json"
    }
    if token:
        headers["Authorization"] = f"token {token}"
        
    params = {
        "q": query,
        "per_page": per_page,
        "page": page
    }
    
    while True:
        try:
            response = requests.get(base_url, headers=headers, params=params, timeout=10)
            
            # Rate Limit Handling
            if response.status_code == 403:
                reset_time = int(response.headers.get("X-RateLimit-Reset", 0))
                wait_seconds = max(reset_time - time.time(), 0) + 1
                print(f"Rate limit exceeded. Waiting for {wait_seconds:.0f} seconds...")
                time.sleep(wait_seconds)
                continue
                
            if response.status_code == 422:
                # 422 means we hit the >1000 results limit for this query
                return None, 422
                
            if response.status_code != 200:
                print(f"Error: {response.status_code} - {response.text}")
                return None, response.status_code
            
            data = response.json()
            return data, 200
            
        except Exception as e:
            print(f"Request error: {e}")
            time.sleep(2)
            continue


def get_github_users_adaptive(start_followers=100, target_limit=1000, token=None, output_file="users_list.json"):
    """
    Adaptive slicing strategy to bypass 1000-result limit.
    """
    existing_users = load_existing_users(output_file)
    print(f"Loaded {len(existing_users)} existing users.")
    
    total_fetched = 0
    
    # Adaptive range strategy
    current_min = start_followers
    current_step = 50 # Initial step guess
    
    while total_fetched < target_limit:
        
        # Ensure we don't end up with step=0
        current_step = max(1, current_step)
        current_max = current_min + current_step
        
        query = f"followers:{current_min}..{current_max}"
        print(f"\nProbing range: {query}")
        
        data, status = fetch_page(query, 1, token, per_page=1)
        
        if status == 422:
            print(f"Range {current_min}..{current_max} too large (hit 1000 limit). Shrinking step...")
            current_step = max(1, current_step // 2)
            continue
            
        if not data:
            print("Failed to get data, stopping.")
            break
            
        total_count = data.get("total_count", 0)
        print(f"Range total count: {total_count}")
        
        if total_count > 1000:
            
            # === START OF CRITICAL FIX ===
            if current_step == 1:
                # If step is already 1, and total_count is still > 1000, 
                # this means two consecutive follower counts (e.g., 100 and 101) 
                # combined have > 1000 users. GitHub API won't allow fetching this.
                # We must skip this small, dense region and move on, while increasing step for the next range.
                print(f"CRITICAL: Range {current_min}..{current_max} is the smallest step (1) but still exceeds 1000 users. Skipping this dense range.")
                
                # Move to the next range immediately
                current_min = current_max + 1
                
                # Try increasing step size for the next search to speed things up later
                current_step = min(current_step * 20, 5000) 
                continue # Skip the rest of the fetching logic for this bad range
            
            # If step > 1, shrink it further (original logic)
            print(f"Range {current_min}..{current_max} has {total_count} users (>1000). Shrinking step...")
            current_step = max(1, current_step // 2)
            continue
            # === END OF CRITICAL FIX ===
            
        # If we are here, total_count <= 1000, so we can fetch all pages safely
        print(f"Valid range found! Fetching {total_count} users...")
        
        pages = (total_count // 100) + 1
        range_users_found = 0
        
        for page in range(1, pages + 1):
            data, status = fetch_page(query, page, token, per_page=100)
            if status != 200 or not data:
                break
                
            items = data.get("items", [])
            if not items:
                break
                
            for item in items:
                username = item["login"]
                if username not in existing_users:
                    existing_users.add(username)
                    total_fetched += 1
                    range_users_found += 1
                    
                    if total_fetched % 500 == 0:
                        print(f"Reached {total_fetched} new users. Saving progress...")
                        save_users(existing_users, output_file)
            
            if total_fetched >= target_limit:
                break
            
            time.sleep(0.5) 
            
        print(f"Finished range {current_min}..{current_max}. Found {range_users_found} new users.")
        
        # Move to next range
        current_min = current_max + 1
        
        # If the last range was very sparse (or we didn't find many), we can try increasing step size
        if total_count < 500 and current_step < 5000:
            current_step = min(current_step * 2, 5000) 
            
        save_users(existing_users, output_file)
        
        if total_fetched >= target_limit:
            print("Target limit reached.")
            break

    return list(existing_users)

def main():
    # Configuration: WARNING - This token is publicly visible, change it immediately!
    START_FOLLOWERS = 100
    LIMIT = 100 
    TOKEN = "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" # <<< EXPOSED TOKEN, CHANGE THIS!
    OUTPUT_FILE = "./user_data/users_list.json"
    
    get_github_users_adaptive(
        start_followers=START_FOLLOWERS, 
        target_limit=LIMIT, 
        token=TOKEN, 
        output_file=OUTPUT_FILE
    )

if __name__ == "__main__":
    main()
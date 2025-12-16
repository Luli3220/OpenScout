import argparse
import requests
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Optional
from tqdm import tqdm

# Constants
BASE_URL = "https://oss.open-digger.cn/github"
METRICS = [
    "openrank.json",
    "activity.json"
]

def fetch_metric(username: str, metric: str) -> Optional[Dict[str, Any]]:
    """
    Fetch a specific metric for a user.
    """
    url = f"{BASE_URL}/{username}/{metric}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            return None  # Metric not available for this user
        else:
            print(f"Warning: Failed to fetch {metric} for {username}. Status: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error fetching {metric} for {username}: {e}")
        return None

def fetch_user_data(username: str) -> Optional[Dict[str, Any]]:
    """
    Fetch all defined metrics for a single user.
    """
    # Removed print statement for cleaner output with tqdm
    user_data = {"username": username}
    
    # We can fetch metrics in parallel for a single user too, but let's keep it simple 
    # and parallelize at the user level to avoid too many connections if list is huge.
    # However, since we have few metrics, fetching them sequentially is fine.
    
    found_any = False
    for metric in METRICS:
        key = metric.replace(".json", "")
        data = fetch_metric(username, metric)
        if data:
            user_data[key] = data
            found_any = True
            
    if not found_any:
        # User has no data in OpenDigger, return None to indicate failure/empty
        return None
    
    # We found at least some data
    user_data["status"] = "success"
        
    return user_data

def batch_fetch(users: List[str], max_workers: int = 5, output_file: str = "./_users_info.json") -> Dict[str, Any]:
    """
    Fetch data for multiple users concurrently with progress bar and periodic saving.
    """
    results = {}
    
    # Load existing results if any, to avoid re-fetching (optional, but good practice)
    if os.path.exists(output_file):
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                results = json.load(f)
                # Ensure results is a dict
                if not isinstance(results, dict):
                     # If it was a list or something else, reset or handle accordingly
                     # For now, let's assume we start fresh or it's a dict
                     if isinstance(results, list):
                         # convert list to dict by username if possible, or just start fresh
                         results = {} 
        except:
            pass

    # Filter out users already fetched
    users_to_fetch = [u for u in users if u not in results]
    print(f"Total users: {len(users)}. Already fetched: {len(results)}. To fetch: {len(users_to_fetch)}")
    
    if not users_to_fetch:
        return results

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_user = {executor.submit(fetch_user_data, user): user for user in users_to_fetch}
        
        # Use tqdm for progress bar
        pbar = tqdm(total=len(users_to_fetch), desc="Fetching users", unit="user")
        
        count = 0
        for future in as_completed(future_to_user):
            user = future_to_user[future]
            try:
                data = future.result()
                if data: # Only add if data was successfully fetched (not None)
                    results[user] = data
            except Exception as e:
                # Log error silently or to a file, don't clutter console
                # For failed users, we simply don't add them to results
                pass
            
            pbar.update(1)
            count += 1
            
            # Save every 50 users
            if count % 50 == 0:
                try:
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(results, f, indent=2, ensure_ascii=False)
                except Exception as e:
                    pbar.write(f"Error saving checkpoint: {e}")
                    
        pbar.close()
                
    return results

def main():
    # Configuration - Hardcoded parameters
    SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    ROOT_DIR = os.path.dirname(SRC_DIR)
    DATA_DIR = os.path.join(ROOT_DIR, "data")
    
    USERS_FILE = os.path.join(DATA_DIR, "users_list.json")
    MACRO_DATA_DIR = os.path.join(DATA_DIR, "macro_data")
    if not os.path.exists(MACRO_DATA_DIR):
        os.makedirs(MACRO_DATA_DIR)
    OUTPUT_FILE = os.path.join(MACRO_DATA_DIR, "macro_data_results.json")
    
    MAX_WORKERS = 5
    
    # You can also manually add users here
    MANUAL_USERS = [] 

    user_list = []
    
    # Add manual users
    if MANUAL_USERS:
        user_list.extend(MANUAL_USERS)
    
    # Load from file if exists
    if USERS_FILE and os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                if USERS_FILE.endswith('.json'):
                    loaded_data = json.load(f)
                    if isinstance(loaded_data, list):
                        user_list.extend(loaded_data)
                    else:
                        print("Warning: JSON file does not contain a list.")
                else:
                    user_list.extend([line.strip() for line in f if line.strip()])
            print(f"Loaded users from {USERS_FILE}")
        except Exception as e:
            print(f"Error reading file {USERS_FILE}: {e}")
    elif USERS_FILE:
        print(f"Warning: File {USERS_FILE} not found.")

    # Remove duplicates
    user_list = list(set(user_list))

    if not user_list:
        print("No users provided. Using default sample list.")
        user_list = ["torvalds", "frank-zsy", "X-lab2017", "yyx990803"]

    print(f"Starting batch fetch for {len(user_list)} users...")
    print(f"Metrics to fetch: {', '.join(METRICS)}")
    
    start_time = time.time()
    data = batch_fetch(user_list, MAX_WORKERS, OUTPUT_FILE)
    duration = time.time() - start_time
    
    print(f"\nCompleted in {duration:.2f} seconds.")
    
    # Save to file
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        
    print(f"Data saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()

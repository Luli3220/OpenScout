import subprocess
import os
import sys
import time
import argparse
import json

def run_step(script_name, description, username=None):
    """Run a python script located in the same directory as this runner."""
    print(f"\n{'='*60}")
    print(f"STEP: {description}")
    print(f"Running: {script_name}")
    print(f"{'='*60}\n")
    
    # Get absolute path of the script to run
    current_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(current_dir, script_name)
    
    if not os.path.exists(script_path):
        print(f"Error: Script {script_name} not found at {script_path}")
        return False
        
    start_time = time.time()
    try:
        # Use the same python interpreter as the current process
        cmd = [sys.executable, script_path]
        if username and script_name != "calculate_radar.py" and script_name != "get_user_name.py":
            cmd.extend(["--username", username])
            
        result = subprocess.run(cmd, check=True)
        duration = time.time() - start_time
        print(f"\n>>> Step '{description}' completed in {duration:.1f}s.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n!!! Step '{description}' failed with exit code {e.returncode}.")
        return False
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        return False

def add_user_to_list(username):
    """Add user to users_list.json if not present"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(current_dir)
    data_dir = os.path.join(root_dir, "data")
    users_file = os.path.join(data_dir, "users_list.json")
    
    users = []
    if os.path.exists(users_file):
        with open(users_file, 'r', encoding='utf-8') as f:
            try:
                users = json.load(f)
            except:
                users = []
    
    if username not in users:
        print(f"Adding {username} to {users_file}")
        users.append(username)
        with open(users_file, 'w', encoding='utf-8') as f:
            json.dump(users, f, indent=2)

def run_pipeline(username=None):
    print("Starting OpenScout Data Pipeline...")
    if username:
        print(f"Target User: {username}")
        add_user_to_list(username)
    else:
        print("Target: All users in users_list.json")
    
    # Define steps: (script_name, description)
    steps = [
        ("get_user_info.py", "2. Metric Agent: Fetching OpenDigger Data (OpenRank & Activity)"),
        ("get_all_metrics.py", "3. Metric Agent: Fetching 6-Dimension Raw Metrics"),
        ("calculate_radar.py", "4. Analysis Agent: Calculating Radar Scores"),
        ("fetch_tech_stack_context.py", "5. Context Agent: Fetching Tech Stack Context (Optional)"),
        ("fetch_representative_repos.py", "6. Context Agent: Fetching Representative Repos (Optional)")
    ]
    
    # If not running for specific user, include discovery
    if not username:
        steps.insert(0, ("get_user_name.py", "1. Scout Agent: Discovering Users"))

    for script, desc in steps:
        success = run_step(script, desc, username)
        if not success:
            print("\nPipeline stopped due to error or interruption.")
            # If we are running as a subprocess (imported), we might not want to exit the whole process
            # But here we are a script or subprocess, so exit code matters
            if __name__ == "__main__":
                sys.exit(1)
            else:
                return False
            
    print(f"\n{'='*60}")
    print("PIPELINE COMPLETED SUCCESSFULLY")
    print(f"{'='*60}")
    return True

def main():
    parser = argparse.ArgumentParser(description="OpenScout Data Pipeline")
    parser.add_argument("--username", help="Run pipeline for a specific user only")
    args = parser.parse_args()
    
    run_pipeline(args.username)

if __name__ == "__main__":
    main()

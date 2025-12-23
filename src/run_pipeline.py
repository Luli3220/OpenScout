import subprocess
import os
import sys
import time

def run_step(script_name, description):
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
        result = subprocess.run([sys.executable, script_path], check=True)
        duration = time.time() - start_time
        print(f"\n>>> Step '{description}' completed in {duration:.1f}s.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n!!! Step '{description}' failed with exit code {e.returncode}.")
        return False
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        return False

def main():
    print("Starting OpenScout Data Pipeline...")
    print("This will run all data collection and analysis agents in sequence.\n")

    steps = [
        ("get_user_name.py", "1. Scout Agent: Discovering Users"),
        ("get_user_info.py", "2. Metric Agent: Fetching OpenDigger Data (OpenRank & Activity)"),
        ("get_all_metrics.py", "3. Metric Agent: Fetching 6-Dimension Raw Metrics"),
        ("calculate_radar.py", "4. Analysis Agent: Calculating Radar Scores"),
        ("fetch_tech_stack_context.py", "5. Context Agent: Fetching Tech Stack Context (Optional)"),
        ("fetch_representative_repos.py", "6. Context Agent: Fetching Representative Repos (Optional)")
    ]

    for script, desc in steps:
        success = run_step(script, desc)
        if not success:
            print("\nPipeline stopped due to error or interruption.")
            sys.exit(1)
            
    print(f"\n{'='*60}")
    print("PIPELINE COMPLETED SUCCESSFULLY")
    print(f"{'='*60}")
    print("You can now check the results in the 'data' directory.")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Init runner for OpenScout data collection.
This script runs the various data collection scripts under `src/` in a sensible order
so that `server.py` endpoints have the files they expect in `data/`.

Usage:
    python3 init.py [--skip-tech] [--skip-repos] [--skip-agentb] [--skip-metrics] [--skip-macro] [--skip-radar]

By default it runs all steps.
"""
import os
import sys
import subprocess
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / 'src'
DATA = ROOT / 'data'
CONFIG = ROOT / 'config.json'
USERS = DATA / 'users_list.json'

# Default script order
STEPS = [
    ('tech', 'fetch_tech_stack_context.py'),
    ('repos', 'fetch_representative_repos.py'),
    ('agentb', 'fetch_agent_b_context.py'),
    ('metrics', 'get_all_metrics.py'),
    ('macro', 'get_user_info.py'),
    ('radar', 'calculate_radar.py'),
]


def run_script(script_path, python_exe=None):
    python_exe = python_exe or sys.executable
    print(f"\n--- Running: {script_path.name} ---")
    try:
        proc = subprocess.run([python_exe, str(script_path)], cwd=str(SRC), check=False)
        return proc.returncode
    except Exception as e:
        print(f"Error running {script_path}: {e}")
        return 2


def ensure_users_list():
    if not USERS.exists():
        print(f"Users list not found at {USERS}. Please create it first.")
        return False
    try:
        import json
        with open(USERS, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if not isinstance(data, list):
                print("users_list.json does not contain a list.")
                return False
    except Exception as e:
        print(f"Error reading users_list.json: {e}")
        return False
    return True


def main():
    parser = argparse.ArgumentParser(description='Initialize OpenScout data by running src scripts in order')
    parser.add_argument('--skip-tech', action='store_true')
    parser.add_argument('--skip-repos', action='store_true')
    parser.add_argument('--skip-agentb', action='store_true')
    parser.add_argument('--skip-metrics', action='store_true')
    parser.add_argument('--skip-macro', action='store_true')
    parser.add_argument('--skip-radar', action='store_true')
    parser.add_argument('--python', default=sys.executable, help='Python executable to use')
    parser.add_argument('--refresh', action='store_true', help='Force refresh (overwrite) existing data files')
    args = parser.parse_args()

    if not ensure_users_list():
        sys.exit(1)

    step_map = {k: v for k, v in STEPS}

    # Map flags
    flags = {
        'tech': args.skip_tech,
        'repos': args.skip_repos,
        'agentb': args.skip_agentb,
        'metrics': args.skip_metrics,
        'macro': args.skip_macro,
        'radar': args.skip_radar,
    }

    # Run in order
    for key, script in STEPS:
        if flags.get(key):
            print(f"Skipping step {key} ({script})")
            continue
        script_path = SRC / script
        if not script_path.exists():
            print(f"Script not found: {script_path}. Skipping.")
            continue
        cmd = [args.python, str(script_path)]
        if args.refresh:
            cmd.append('--refresh')
        print(f"\nExecuting: {' '.join(cmd)}")
        try:
            proc = subprocess.run(cmd, cwd=str(SRC), check=False)
            ret = proc.returncode
        except Exception as e:
            print(f"Error running {script_path}: {e}")
            ret = 2
        if ret != 0:
            print(f"Script {script} exited with code {ret}. You may re-run init.py to resume after fixing issues.")
            # Do not abort; continue with remaining steps so partial data can be generated

    print('\nAll requested steps finished.')
    print('Please check data/ and data/raw_users/ for generated files. You can now run server.py to serve the API.')

if __name__ == '__main__':
    main()

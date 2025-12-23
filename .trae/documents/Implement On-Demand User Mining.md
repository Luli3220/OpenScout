# Implement On-Demand User Mining Feature

## Goal
Enable the system to automatically fetch and calculate data for a user when they are searched for but not found in the local database.

## Plan

### 1. Modify Data Collection Scripts
Update the following scripts to support a `--user` argument. When provided, the script will process **only** that specific user instead of iterating through `users_list.json`.
- `src/get_user_info.py`
- `src/get_all_metrics.py`
- `src/calculate_radar.py`
- `src/fetch_tech_stack_context.py`
- `src/fetch_representative_repos.py`

### 2. Update Pipeline Runner (`src/run_pipeline.py`)
- Add support for a `--user <username>` argument.
- When running in "single user mode":
  - Skip `get_user_name.py` (user discovery).
  - Ensure the user is added to `data/users_list.json` (so they are tracked for future updates).
  - Pass the `--user` flag to all subsequent scripts.

### 3. Update Backend (`server.py`)
- Introduce a global in-memory set `mining_tasks` to track users currently being mined.
- Modify the `GET /api/radar/{username}` endpoint:
  - If user is not found in `radar_scores.json`:
    - Check if user is already in `mining_tasks`.
    - If not, start a background task to run `src/run_pipeline.py --user {username}`.
    - Return a new status `{"found": False, "mining": True, "message": "Mining data..."}`.
- Add a cleanup callback to remove user from `mining_tasks` when the pipeline finishes.

### 4. Update Frontend (`OpenScout.htm`)
- Update the search logic to handle the `mining: True` response.
- Display a "Mining in progress... (Est. 1-2 mins)" loading state.
- Implement a polling mechanism to retry fetching the user data every 3 seconds until `found: True` or mining fails.

## Execution Order
1. Modify 5 sub-scripts (`src/*.py`).
2. Modify `src/run_pipeline.py`.
3. Modify `server.py`.
4. Modify `OpenScout.htm`.

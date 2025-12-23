I will implement the automatic data mining feature for missing users as requested.

### Plan

1.  **Modify Data Collection Scripts to Support Single User Mode**
    *   **`src/get_user_info.py`**: Add `--username` argument to fetch data for a specific user only.
    *   **`src/get_all_metrics.py`**: Add `--username` argument to fetch metrics for a specific user only.
    *   **`src/fetch_tech_stack_context.py`** & **`src/fetch_representative_repos.py`**: Add `--username` argument to limit context fetching to the specific user.

2.  **Enhance `src/run_pipeline.py`**
    *   Add a new function `run_for_user(username)` that:
        *   Adds the username to `data/users_list.json` if missing.
        *   Executes the data collection scripts with the `--username` flag.
        *   Executes `calculate_radar.py` (global recalculation to ensure correct relative scoring).
    *   Expose this function to be callable from `server.py`.

3.  **Update `server.py`**
    *   Modify `GET /api/radar/{username}`:
        *   If the user is not found in `radar_scores.json`:
            *   Trigger a background task to run the pipeline for this user.
            *   Return a specific status (e.g., `{"found": False, "mining": True}`) to inform the frontend.

4.  **Update Frontend (`OpenScout.htm`)**
    *   Handle the "Mining" status.
    *   Display a "Mining in progress, please wait..." message or spinner.
    *   Implement polling to check when the data is ready.

### Execution Order
1.  Modify `src/get_user_info.py`, `src/get_all_metrics.py`, `src/fetch_tech_stack_context.py`, `src/fetch_representative_repos.py`.
2.  Modify `src/run_pipeline.py`.
3.  Modify `server.py`.
4.  Modify `OpenScout.htm`.

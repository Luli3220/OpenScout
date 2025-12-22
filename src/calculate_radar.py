import json
import os
import math
import statistics

# Configuration
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SRC_DIR)
DATA_DIR = os.path.join(ROOT_DIR, "data")

USERS_LIST_FILE = os.path.join(DATA_DIR, "users_list.json")
USER_DATA_DIR = os.path.join(DATA_DIR, "raw_users")
OUTPUT_FILE = os.path.join(DATA_DIR, "radar_scores.json")

def load_json(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"Error loading {path}: {e}")
        return None

def get_raw_metrics(username):
    user_dir = os.path.join(USER_DATA_DIR, username)
    
    # Initialize metrics with 0
    metrics = {
        # Influence
        "stars": 0, "forks": 0, "issues": 0,
        # Contribution
        "ext_prs": 0, "created_issues": 0,
        # Maintainership
        "others_prs": 0,
        # Engagement
        "issue_comments": 0, "review_comments": 0,
        # Diversity
        "languages": 0, "topics": 0,
        # Code Capability
        "merged_prs_stars": [],
        "merged_prs_count": 0,
        "closed_prs_count": 0
    }

    # Load Influence
    inf_data = load_json(os.path.join(user_dir, f"{username}_influence.json"))
    if inf_data and "raw_metrics" in inf_data:
        rm = inf_data["raw_metrics"]
        metrics["stars"] = rm.get("total_stars", 0)
        metrics["forks"] = rm.get("total_forks", 0)
        metrics["issues"] = rm.get("total_open_issues", 0)

    # Load Contribution
    con_data = load_json(os.path.join(user_dir, f"{username}_contribution.json"))
    if con_data and "raw_metrics" in con_data:
        rm = con_data["raw_metrics"]
        metrics["ext_prs"] = rm.get("accepted_external_prs", 0)
        metrics["created_issues"] = rm.get("created_issues", 0)

    # Load Maintainership
    main_data = load_json(os.path.join(user_dir, f"{username}_maintainership.json"))
    if main_data and "raw_metrics" in main_data:
        rm = main_data["raw_metrics"]
        metrics["others_prs"] = rm.get("merged_external_pr_count_approx", 0)

    # Load Engagement
    eng_data = load_json(os.path.join(user_dir, f"{username}_engagement.json"))
    if eng_data and "raw_metrics" in eng_data:
        rm = eng_data["raw_metrics"]
        metrics["issue_comments"] = rm.get("issue_comment_count", 0)
        metrics["review_comments"] = rm.get("pr_review_comment_count", 0)

    # Load Diversity
    div_data = load_json(os.path.join(user_dir, f"{username}_diversity.json"))
    if div_data and "raw_metrics" in div_data:
        rm = div_data["raw_metrics"]
        metrics["languages"] = rm.get("language_count", 0)
        metrics["topics"] = rm.get("topic_count", 0)

    # Load Code Capability
    code_data = load_json(os.path.join(user_dir, f"{username}_code_capability.json"))
    if code_data and "raw_metrics" in code_data:
        rm = code_data["raw_metrics"]
        metrics["merged_prs_stars"] = rm.get("merged_prs_with_stars", [])
        metrics["merged_prs_count"] = rm.get("accepted_external_prs", 0)
        metrics["closed_prs_count"] = rm.get("total_closed_external_prs", 0)

    return metrics

def calculate_raw_scores(metrics):
    scores = {}
    
    # Influence: (Stars * 0.6) + ((Forks + Issues) * 0.4)
    scores["influence"] = (metrics["stars"] * 0.6) + ((metrics["forks"] + metrics["issues"]) * 0.4)
    
    # Contribution: (Merged_External_PRs * 0.7) + (Created_Issues * 0.3)
    scores["contribution"] = (metrics["ext_prs"] * 0.7) + (metrics["created_issues"] * 0.3)
    
    # Maintainership: Merged_Others_PRs * 1.0 + Review_Comments * 0.3 (to avoid 0 score for reviewers)
    scores["maintainership"] = (metrics["others_prs"] * 1.0) + (metrics["review_comments"] * 0.3)
    
    # Engagement: (Issue_Comments * 0.6) + (Review_Comments * 0.4)
    scores["engagement"] = (metrics["issue_comments"] * 0.6) + (metrics["review_comments"] * 0.4)
    
    # Diversity: (Languages * 0.6) + (Topics * 0.4)
    scores["diversity"] = (metrics["languages"] * 0.6) + (metrics["topics"] * 0.4)
    
    # Code Capability: Core Contribution Value = sum(ln(stars + 1))
    # Note: We prioritize "value" over "rate" as per calculation.md
    core_value = sum(math.log1p(stars) for stars in metrics["merged_prs_stars"])
    
    # Fallback for Code Capability: If 0, check for attempts/reviews
    if core_value == 0:
        if metrics.get("closed_prs_count", 0) > 0 or metrics.get("review_comments", 0) > 0:
            core_value = 1.0 # Base value to ensure non-zero score
            
    scores["code_capability"] = core_value
    
    return scores

def normal_cdf(x, mu, sigma):
    if sigma == 0:
        return 0.5 # If no variance, everyone is average
    z = (x - mu) / sigma
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))

def main():
    import argparse
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--refresh', action='store_true')
    args, _ = parser.parse_known_args()
    refresh = args.refresh or os.environ.get('REFRESH_DATA') in ('1', 'true', 'True')

    print("Loading user list...")
    users = load_json(USERS_LIST_FILE)
    if not users:
        print("Failed to load user list.")
        return

    print(f"Processing {len(users)} users...")
    
    # Load existing final output if any and not refreshing
    existing_output = {}
    if os.path.exists(OUTPUT_FILE) and not refresh:
        try:
            with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                existing_output = json.load(f)
        except:
            existing_output = {}

    # 1. Collect Raw Scores
    user_raw_scores = {} # username -> {dim: score}
    dimension_values = {
        "influence": [],
        "contribution": [],
        "maintainership": [],
        "engagement": [],
        "diversity": [],
        "code_capability": []
    }
    
    # Compute for all users (ensures stats include full population)
    users_to_compute = users

    for user in users_to_compute:
        metrics = get_raw_metrics(user)
        raw_scores = calculate_raw_scores(metrics)
        user_raw_scores[user] = raw_scores
        for dim, val in raw_scores.items():
            dimension_values[dim].append(val)

    # 2. Calculate Stats (Mean, Std) for Log Values
    dim_stats = {}
    
    for dim, values in dimension_values.items():
        # Log transformation: ln(x + 1)
        log_values = [math.log1p(v) for v in values]
        
        if not log_values:
            dim_stats[dim] = {"mu": 0, "sigma": 1}
            continue
            
        # Outlier handling: Remove max value for stat calculation if len > 1
        calc_values = log_values[:]
        if len(calc_values) > 1:
            max_val = max(calc_values)
            calc_values.remove(max_val)
            
        mu = statistics.mean(calc_values)
        sigma = statistics.stdev(calc_values) if len(calc_values) > 1 else 0
        
        # Avoid zero sigma if all values are same
        if sigma == 0:
            sigma = 1 
            
        dim_stats[dim] = {"mu": mu, "sigma": sigma}
        print(f"Stats for {dim}: mu={mu:.4f}, sigma={sigma:.4f}")

    # 3. Calculate Final Scores
    final_output = {}
    
    dimensions_order = ["influence", "contribution", "maintainership", "engagement", "diversity", "code_capability"]
    
    for user in users:
        raw_scores = user_raw_scores[user]
        user_final_scores = []
        
        for dim in dimensions_order:
            raw_val = raw_scores[dim]
            
            # Zero handling
            if raw_val == 0:
                user_final_scores.append(50) # Tiny point for 0
                continue
                
            # Log transform
            log_val = math.log1p(raw_val)
            
            # Z-Score -> CDF -> 50-100 Mapping
            stats = dim_stats[dim]
            cdf_prob = normal_cdf(log_val, stats["mu"], stats["sigma"])
            
            # User request: Start at 50, then add based on performance
            # Mapping 0-1 probability to 50-100 range
            score = 50 + (cdf_prob * 50)
            
            # Round to 1 decimal
            user_final_scores.append(round(score, 1))
            
        # Add 6th dimension (empty/zero)
        # user_final_scores.append(0)
        
        final_output[user] = user_final_scores

    # 4. Save Output
    print(f"Saving results to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(final_output, f, indent=2)
    print("Done.")

if __name__ == "__main__":
    main()

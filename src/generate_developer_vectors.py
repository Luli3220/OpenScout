#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate developer vectors from collected data.
"""

import os
import json
import argparse
from tqdm import tqdm
import numpy as np

def load_json(file_path):
    """Load JSON file."""
    if not os.path.exists(file_path):
        return None
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return None

def normalize(value, min_val, max_val):
    """Normalize value to 0-1 range."""
    if max_val <= min_val:
        return 0.0
    return (value - min_val) / (max_val - min_val)

def generate_developer_vectors(username=None, refresh=False):
    """Generate developer vectors."""
    # Get base directories
    current_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(current_dir)
    data_dir = os.path.join(root_dir, "data")
    
    # Load users list
    users_list_file = os.path.join(data_dir, "users_list.json")
    users = load_json(users_list_file)
    if not users:
        print(f"Error: {users_list_file} not found or empty.")
        return False
    
    # If username is specified, only process that user
    if username:
        if username not in users:
            users = [username]
        else:
            users = [username]
    
    # Load radar scores
    radar_file = os.path.join(data_dir, "radar_scores.json")
    radar_scores = load_json(radar_file)
    if not radar_scores:
        print(f"Error: {radar_file} not found or empty.")
        return False
    
    # Load existing vectors if refresh is False
    vectors_file = os.path.join(data_dir, "developer_vectors.json")
    existing_vectors = load_json(vectors_file) if not refresh else {}
    
    # Process each user
    for user in tqdm(users, desc="Generating vectors"):
        # Skip if already processed and not refreshing
        if user in existing_vectors and not refresh:
            continue
        
        # Load user data
        user_dir = os.path.join(data_dir, "raw_users", user)
        if not os.path.exists(user_dir):
            continue
        
        # Load diversity data for technical tags
        diversity_file = os.path.join(user_dir, f"{user}_diversity.json")
        diversity_data = load_json(diversity_file)
        
        # Load tech stack data
        tech_stack_file = os.path.join(user_dir, "tech_stack.json")
        tech_stack_data = load_json(tech_stack_file)
        
        # Load representative repos data
        repos_file = os.path.join(user_dir, "representative_repos.json")
        repos_data = load_json(repos_file)
        
        # Load radar scores for this user
        user_radar = radar_scores.get(user, [50, 50, 50, 50, 50, 50])
        
        # Generate numerical features from radar scores (normalize to 0-1)
        # Radar scores are already in 50-100 range, so normalize to 0-1
        numerical_features = [(score - 50) / 50 for score in user_radar]
        
        # Generate technical tag features (simplified approach for now)
        # Count the number of distinct languages and topics
        technical_features = [0.0, 0.0]
        if diversity_data:
            distinct_languages = len(diversity_data.get("raw_metrics", {}).get("distinct_languages", []))
            distinct_topics = len(diversity_data.get("raw_metrics", {}).get("distinct_topics", []))
            technical_features = [distinct_languages / 20, distinct_topics / 10]  # Normalize based on typical ranges
        
        # Generate project features (simplified approach for now)
        # Count the number of representative repos and average stars
        project_features = [0.0, 0.0]
        if repos_data and isinstance(repos_data, list):
            project_count = len(repos_data)
            avg_stars = sum(repo.get("stars", 0) for repo in repos_data) / max(1, project_count)
            project_features = [project_count / 10, min(avg_stars / 1000, 1.0)]  # Normalize
        
        # Combine all features into a single vector
        vector = numerical_features + technical_features + project_features
        
        # Store the vector
        existing_vectors[user] = vector
    
    # Save vectors to file
    with open(vectors_file, 'w', encoding='utf-8') as f:
        json.dump(existing_vectors, f, ensure_ascii=False, indent=2)
    
    print(f"Generated vectors for {len(existing_vectors)} users.")
    print(f"Results saved to {vectors_file}.")
    return True

def main():
    parser = argparse.ArgumentParser(description="Generate developer vectors.")
    parser.add_argument("--username", help="Process only this username")
    parser.add_argument("--refresh", action="store_true", help="Refresh all vectors")
    args = parser.parse_args()
    
    success = generate_developer_vectors(args.username, args.refresh)
    if not success:
        exit(1)

if __name__ == "__main__":
    main()
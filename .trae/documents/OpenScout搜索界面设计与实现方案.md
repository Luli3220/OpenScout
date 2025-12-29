# 智能搜索功能数据采集方案

## 一、需求分析

智能搜索功能需要以下核心数据：
1. **开发者向量数据**：用于与搜索查询向量进行相似度计算
2. **项目特征提取能力**：能够从项目档案中提取技术栈、规模等特征
3. **向量生成和相似度计算能力**：将自然语言查询或项目档案转换为向量，并计算与开发者向量的相似度

## 二、现有数据采集脚本分析

现有数据采集脚本已经收集了大量开发者数据，包括：
- 开发者的 6 维能力指标（影响力、贡献度、维护力、参与度、多样性、代码能力）
- 开发者的技术栈信息
- 开发者的代表仓库信息
- 开发者的 OpenRank 和 Activity 数据

这些数据为智能搜索提供了良好的基础，但还需要将其转换为向量形式，以便进行相似度计算。

## 三、新数据采集脚本设计

### 1. 脚本名称
`generate_developer_vectors.py`

### 2. 功能描述
读取现有开发者数据，生成开发者向量，并保存到文件中。

### 3. 输入数据
- `data/users_list.json`：开发者名单
- `data/radar_scores.json`：开发者 6 维雷达分数
- `data/raw_users/<username>/diversity.json`：开发者技术多样性数据
- `data/raw_users/<username>/tech_stack.json`：开发者技术栈数据
- `data/raw_users/<username>/representative_repos.json`：开发者代表仓库数据

### 4. 输出数据
- `data/developer_vectors.json`：JSON 对象，键为用户名，值为开发者向量
- 向量格式：包含数值特征和技术标签特征的复合向量

### 5. 向量生成方法

#### 5.1 数值特征
- 6 维能力指标（影响力、贡献度、维护力、参与度、多样性、代码能力）
- 归一化处理：将所有数值特征归一化到 0-1 区间

#### 5.2 技术标签特征
- 从 `diversity.json` 和 `tech_stack.json` 中提取技术标签
- 使用独热编码或词嵌入技术将技术标签转换为向量
- 考虑技术标签的权重：根据使用频率或重要性赋予不同权重

#### 5.3 项目特征
- 从代表仓库数据中提取项目规模、活跃度等特征
- 项目规模：代码行数、文件数量等
- 项目活跃度：提交频率、Issue 处理速度等

### 6. 脚本实现

```python
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
```

## 四、集成到现有数据采集流程

1. 将新脚本 `generate_developer_vectors.py` 添加到 `src` 目录
2. 修改 `run_pipeline.py`，将新脚本添加到数据采集流程中

修改后的 `run_pipeline.py` 步骤列表：

```python
steps = [
    ("get_user_info.py", "2. Metric Agent: Fetching OpenDigger Data (OpenRank & Activity)"),
    ("get_all_metrics.py", "3. Metric Agent: Fetching 6-Dimension Raw Metrics"),
    ("calculate_radar.py", "4. Analysis Agent: Calculating Radar Scores"),
    ("fetch_tech_stack_context.py", "5. Context Agent: Fetching Tech Stack Context (Optional)"),
    ("fetch_representative_repos.py", "6. Context Agent: Fetching Representative Repos (Optional)"),
    ("generate_developer_vectors.py", "7. Vector Agent: Generating Developer Vectors")  # New step
]
```

## 五、智能搜索功能的实现

有了开发者向量数据后，我们可以实现智能搜索功能：

1. **前端**：设计搜索界面，支持自然语言输入和项目档案上传
2. **后端**：
   - 创建 Search Agent，用于处理搜索请求
   - 实现向量生成功能，将自然语言查询或项目档案转换为向量
   - 实现相似度计算功能，计算搜索查询向量与开发者向量的相似度
   - 返回匹配度排行榜
3. **API 设计**：
   - `POST /api/ai-search`：处理智能搜索请求
   - 请求参数：`query`（自然语言查询）或 `project_file`（项目档案）
   - 返回结果：匹配度排行榜

## 六、后续优化方向

1. **改进向量生成方法**：使用更先进的方法，如词嵌入、深度学习模型等，提高向量的表示能力
2. **支持更多特征**：添加更多开发者特征，如地理位置、行业经验等
3. **实时更新向量**：定期更新开发者向量，确保数据的时效性
4. **支持个性化搜索**：根据用户的搜索历史和反馈，优化搜索结果
5. **可视化匹配过程**：展示匹配过程中考虑的关键因素，提高搜索结果的透明度

## 七、结论

通过添加新的数据采集脚本 `generate_developer_vectors.py`，我们可以生成开发者向量数据，并将其集成到现有的数据采集流程中。这些向量数据将为智能搜索功能提供基础支持，使 OpenScout 能够实现基于自然语言和项目档案的智能开发者搜索功能。
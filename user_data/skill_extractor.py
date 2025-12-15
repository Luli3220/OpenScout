# ./user_data/skill_extractor.py

import os
import json
import glob
from typing import List, Dict, Any, Optional
import time
# 导入 requests 库，用于未来的真实 LLM API 调用
import requests

# -- 1. 配置与常量 --
INPUT_DIR = "./user_data/micro_data"
OUTPUT_DIR = "./user_data/processed_data" # 结构化技能数据的输出目录

# --- LLM API 配置 (请替换为您的真实配置) ---
# 注意：MaxKB Agent 通常会封装这个逻辑，这里我们模拟直接调用一个 LLM API
LLM_API_ENDPOINT = os.getenv("LLM_API_ENDPOINT", "http://your-llm-service/v1/chat/completions")
LLM_API_KEY = os.getenv("LLM_API_KEY", "sk-YOUR-ACTUAL-API-KEY")
LLM_MODEL = "deepseek-v2-chat" # 或 "gpt-4o", "llama3", etc.

# =================================================================
# 核心部分：Prompt 工程
# =================================================================

SYSTEM_PROMPT = """你是一名资深的招聘技术主管和 LLM 智能体，任务是从 GitHub 用户的 Commit 记录中提炼出结构化的技术技能和经验。
你的分析必须严格基于提供的 Commit Message 和 Patch（代码差异）。
你只需要输出一个 JSON 数组，无需任何额外说明或代码块。

【技能提取规则】
1. 技能必须具体、可量化。例如：不要只写 'Java'，而要写 'Java Stream API' 或 'Spring Boot Security 配置'。
2. 技能级别分为：'Basic' (仅使用或简单修改)、'Intermediate' (独立实现或解决非关键问题)、'Advanced' (解决复杂架构问题或底层优化)。
3. 'summary' 必须简短，且直接引用 Commit Message 或 Patch 内容来证明技能的真实性。
4. 忽略低价值的提交：例如：自动合并 (Merge)、更新 README、修改配置文件、单纯的依赖升级（除非提交信息中有具体的配置修改）。

【输出格式要求】(JSON 数组)
[
  {
    "skill_name": "具体的技能名称（例如：Kubernetes Helm Chart 部署）",
    "expertise_level": "Basic | Intermediate | Advanced",
    "evidence_sha": "与此技能最相关的 Commit SHA",
    "summary": "基于 Commit Message 和 Patch 证明此技能的简短总结。",
    "source_type": "commit_micro_data" 
  }
]
"""

# =================================================================

def load_micro_data(username: str) -> Optional[Dict[str, Any]]:
    """加载单个用户的微观数据文件"""
    file_path = os.path.join(INPUT_DIR, f"{username}_micro_data.json")
    if not os.path.exists(file_path):
        print(f"Warning: Micro data file not found for {username}")
        return None
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {file_path}: {e}")
        return None

def preprocess_commits_for_llm(user_data: Dict[str, Any], max_commits: int = 50) -> str:
    """
    将用户的 Commit 数据预处理成 LLM 易于理解的文本格式。
    由于输入窗口限制，我们只选择每个用户的最新 N 个 Commit。
    """
    commit_texts = []
    commit_count = 0
    
    # 遍历所有仓库并收集 commits
    for repo in user_data.get('repos', []):
        repo_name = repo.get('name', 'unknown')
        # 假设 commits 列表是按时间倒序排列的（最新的在前）
        for commit in repo.get('commits', []):
            if commit_count >= max_commits:
                break
                
            sha = commit.get('sha', 'N/A')
            message = commit.get('message', 'N/A').strip()
            
            # 提取所有文件的 patch 内容，限制总长度以防 Token 超限
            patches = []
            for file in commit.get('files', []):
                patch_content = file.get('patch')
                if patch_content and len(patch_content) > 100:
                    # 仅保留 patch 的头部和尾部，避免 Token 超限
                    patches.append(f"文件名: {file['filename']}\n代码差异片段:\n{patch_content[:500]} ...\n")
                elif patch_content:
                    patches.append(f"文件名: {file['filename']}\n代码差异:\n{patch_content}\n")
            
            patch_text = "\n".join(patches)
            
            # 过滤掉内容为空的提交，或只有极少改动的提交
            if len(patch_text) < 100 and ('merge' in message.lower() or 'update' in message.lower()):
                 continue
            
            commit_block = (
                f"--- Commit {commit_count + 1} ({repo_name}, {sha[:8]}) ---\n"
                f"Message: {message}\n"
                f"Patch/Diff:\n{patch_text}\n"
            )
            commit_texts.append(commit_block)
            commit_count += 1
            
        if commit_count >= max_commits:
            break
            
    return "\n".join(commit_texts)

def llm_extract_skills_placeholder(commit_data_text: str) -> List[Dict[str, Any]]:
    """
    【占位符】模拟调用 MaxKB 或 LLM API 进行技能提取。
    在实际部署中，您需要将此函数替换为调用您的 LLM 服务。
    """
    
    if not LLM_API_KEY or LLM_API_KEY.startswith("sk-YOUR-"):
        print("Error: LLM API key not configured. Cannot perform real extraction.")
        # 返回一个模拟数据结构，以便后续流程测试
        return [{
            "skill_name": "LLM_SIMULATION_PLACEHOLDER",
            "expertise_level": "Intermediate",
            "evidence_sha": "SIM00000",
            "summary": "由于 LLM API 未配置，此为模拟结果。请配置 LLM_API_ENDPOINT 和 LLM_API_KEY。",
            "source_type": "simulation"
        }]

    # 实际 API 调用逻辑示例 (以 OpenAI/DeepSeek 格式为例)
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json"
    }
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"请分析以下 Commit 记录并严格按照要求的 JSON 格式输出结构化技能列表：\n\n{commit_data_text}"}
    ]
    
    data = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": 0.1, # 保持低温度以提高提取的准确性
        "response_format": {"type": "json_object"} # 强制 LLM 输出 JSON
    }
    
    try:
        response = requests.post(LLM_API_ENDPOINT, headers=headers, json=data, timeout=60)
        response.raise_for_status()
        
        # 尝试解析响应
        result = response.json()
        
        # 根据实际 API 的结构来提取最终的 JSON 字符串
        # 不同的 API 结构不同，这里假设返回的 JSON 内部包含一个 JSON 字符串
        content = result['choices'][0]['message']['content']
        
        # 尝试解析 LLM 输出的 JSON 字符串
        return json.loads(content)
        
    except requests.exceptions.RequestException as e:
        print(f"Error calling LLM API: {e}")
        return []
    except (KeyError, json.JSONDecodeError) as e:
        print(f"Error parsing LLM response or malformed JSON output: {e}")
        print(f"Raw response content (if available): {response.text if 'response' in locals() else 'N/A'}")
        return []

def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    # 查找所有已抓取的微观数据文件
    micro_data_files = glob.glob(os.path.join(INPUT_DIR, "*_micro_data.json"))
    
    if not micro_data_files:
        print(f"Error: No micro data files found in {INPUT_DIR}. Please run get_user_micro_data.py first.")
        return

    print(f"Found {len(micro_data_files)} user micro data files for skill extraction.")
    
    # 限制处理的文件数量进行测试（可选）
    # micro_data_files = micro_data_files[:5] 

    for file_path in micro_data_files:
        filename = os.path.basename(file_path)
        username = filename.replace("_micro_data.json", "")
        output_file = os.path.join(OUTPUT_DIR, f"{username}_skills_structured.json")
        
        # 检查是否已经处理过
        if os.path.exists(output_file):
            print(f"Skipping {username}: already processed.")
            continue
            
        print(f"-> Processing {username}...")
        user_data = load_micro_data(username)
        if not user_data:
            continue
            
        # 1. 预处理 Commit Log 为 LLM 输入
        commit_data_text = preprocess_commits_for_llm(user_data, max_commits=30)
        
        if not commit_data_text.strip():
            print(f"Warning: {username} has no valid commits after filtering. Skipping.")
            continue
            
        # 2. 调用 LLM Agent (或模拟) 进行技能提取
        structured_skills = llm_extract_skills_placeholder(commit_data_text)
        
        # 3. 结果合并与保存
        final_data = {
            "username": username,
            "processed_at": time.time(),
            "extracted_skills": structured_skills
        }
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(final_data, f, indent=2, ensure_ascii=False)
            print(f"SUCCESS: {username} 的结构化技能已保存到 {output_file}")
        except Exception as e:
            print(f"ERROR: 写入文件失败 {output_file}: {e}")

if __name__ == "__main__":
    main()
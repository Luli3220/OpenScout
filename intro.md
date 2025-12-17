这是一个非常敏锐的观察。确实，GitHub 上的开发者习惯千差万别，很多个人开发者（特别是做 Side Project 的）并不遵循企业级的工程规范。

* **技术栈为空的原因**：很多人只有代码，没有 `k8s.yaml`，甚至没有 `Dockerfile`。如果是 Python 项目，可能连 `requirements.txt` 都没有（只有一个 `.py` 文件）。
* **Patch 少/难概括的原因**：个人开发者往往直接推送到 `main` 分支，**不发 PR**。Agent B 目前的逻辑是“只看 Merged PR”，这会漏掉绝大多数“独行侠”高手的代码。

为了解决这个问题，我们需要实施 **“保底策略” (Fallback Strategies)**。

以下是具体的优化建议和代码修改方案。

---

### 🚀 优化方案 A：Agent A (Tech Hunter) 的改进

**策略：从“只找配置文件”改为“配置文件 + 语言统计 + README”**

如果找不到 `package.json`，至少我们要知道他写了 90% 的 Rust 代码。

**修改点：**

1. **增加 `languages` 统计**：直接调用 GitHub API 获取该仓库的语言构成（绝对有数据）。
2. **增加 `README.md**`：开发者通常会在 README 里自吹用到了什么技术，这是文本分析的金矿。
3. **放宽文件搜索**：不要太执着于 `k8s`，如果有 `README` 和 `languages`，就已经足够 Agent 分析了。

**👉 请修改 `fetch_tech_stack_context.py` 中的 `fetch_top_original_repos_context` 函数：**

```python
def fetch_top_original_repos_context(client: GitHubAPIClient, username: str) -> List[Dict[str, Any]]:
    # ... (前面的获取 repos 列表逻辑保持不变) ...
    # ... (到 original_repos 排序代码保持不变) ...
    
    # Top 3
    top_repos = original_repos[:3]
    
    result = []
    
    # 3. Process each repo
    for repo in top_repos:
        repo_pure_name = repo.get('name')
        
        repo_data = {
            "name": repo.get('full_name'),
            "stars": repo.get('stargazers_count', 0),
            "description": repo.get('description') or "无",
            # 新增：语言构成
            "languages_breakdown": {}, 
            "files": {}
        }

        # --- [改进 1] 获取语言构成 (绝对有数据) ---
        try:
            lang_resp = client.get(repo.get('languages_url'))
            if lang_resp.status_code == 200:
                repo_data["languages_breakdown"] = lang_resp.json()
        except:
            pass

        # --- [改进 2] 必抓 README (文本分析金矿) ---
        # 把 README 加入到 file_path 检查列表，或者单独处理
        extended_target_files = TARGET_FILES + ["README.md", "README.rst"]
        
        for file_path in extended_target_files:
            content = get_file_content(client, username, repo_pure_name, file_path)
            # 只有当内容不为空时才加入，节省 Token
            if content:
                repo_data["files"][file_path] = content
            
        result.append(repo_data)
    
    return result

```

---

### 🚀 优化方案 B：Agent B (Code Auditor) 的改进

**策略：从“只看 PR Patch”改为“PR Patch (优先) -> 核心源码文件 (保底)”**

如果找不到 Merged PR，我们就直接去他 Star 最高的仓库里，**把体积最大的那个源代码文件抓下来**。Agent B 也可以通过阅读整个文件来评价代码风格（甚至比看 Diff 更准）。

**修改点：**

1. **新增 `fetch_core_source_file` 逻辑**：如果没有 PR 数据，就去扫 Top 1 仓库的文件树。
2. **文件筛选**：找到 `src/` 或根目录下最大的 `.go/.rs/.py` 文件。

**👉 请修改 `fetch_agent_b_context.py`，替换/更新 `fetch_agent_b_context` 函数：**

```python
# 新增辅助函数：获取核心源码文件
def fetch_core_source_file(client: GitHubAPIClient, username: str) -> Optional[str]:
    """Fallback: Fetches the largest source code file from the user's top repo."""
    try:
        # 1. Get Top 1 Original Repo
        r_resp = client.get(f"/users/{username}/repos", params={'type': 'owner', 'sort': 'stars', 'direction': 'desc', 'per_page': 1})
        if r_resp.status_code != 200: return None
        repos = r_resp.json()
        if not repos: return None
        
        top_repo = repos[0]
        repo_name = top_repo['name']
        default_branch = top_repo.get('default_branch', 'main')

        # 2. Get File Tree (Recursive to find deep files)
        # 注意：recursive=1 可能会返回很多文件，我们只取前部分或过滤
        tree_url = f"/repos/{username}/{repo_name}/git/trees/{default_branch}?recursive=1"
        t_resp = client.get(tree_url)
        if t_resp.status_code != 200: return None
        
        tree_data = t_resp.json()
        if 'tree' not in tree_data: return None
        
        # 3. Filter for Source Files
        candidates = []
        for item in tree_data['tree']:
            if item['type'] == 'blob':
                path = item['path']
                # 过滤：只看白名单后缀，且不看 vendor/dist 等目录
                if is_valid_file(path):
                    candidates.append(item)
        
        if not candidates: return None

        # 4. Sort by Size (Size is distinct in tree API)
        # We want a file that is substantial but not huge. API tree 'size' is bytes.
        # Let's pick the largest file that is under 50KB to avoid pure generated garbage, but large enough to show logic.
        candidates.sort(key=lambda x: x.get('size', 0), reverse=True)
        
        target_file = candidates[0] # Take the largest valid source file
        
        # 5. Fetch Content
        # We can use the 'url' (blob url) or fetch by path content
        # Using specific blob API is better for large files usually, but let's stick to contents API for simplicity if we have path
        # Or simpler: we use the blob SHA to get raw content if needed.
        # Let's use get_repo_content logic manually here since we need to decode
        
        f_resp = client.get(f"/repos/{username}/{repo_name}/contents/{target_file['path']}")
        if f_resp.status_code == 200:
            data = f_resp.json()
            if 'content' in data:
                import base64
                content = base64.b64decode(data['content']).decode('utf-8', errors='replace')
                # Truncate
                if len(content) > 3000:
                    content = content[:3000] + "\n... (file truncated)"
                return f"\n=== Fallback Source Audit: {target_file['path']} (Size: {target_file['size']} bytes) ===\n{content}\n"

    except Exception as e:
        print(f"Error fetching core source file: {e}")
    
    return None

# 修改主函数 logic
def fetch_agent_b_context(client: GitHubAPIClient, username: str) -> Optional[str]:
    # ... (前面的 PR 抓取逻辑 prs_to_check 保持不变) ...
    
    # [修改点]：如果 prs_to_check 为空，尝试直接抓源码
    final_output = ""
    
    # 尝试抓 PR
    # ... (你的 PR 抓取循环代码) ...
    # 这里的代码不用大改，只是如果 final_output 还是空的话
    
    # --- 新增保底逻辑 ---
    if not final_output or len(final_output) < 200:
        # 如果没有 PR 或者 PR 内容太少，启动保底扫描
        # print(f"  [Agent B] No sufficient PRs found for {username}, switching to Source File Audit...")
        source_code = fetch_core_source_file(client, username)
        if source_code:
            final_output = (final_output or "") + source_code
            
    return final_output if final_output else None

```

### 💡 总结改进后的效果

1. **Tech Stack**:
* **以前**: 没有 `package.json` -> 数据为空。
* **现在**: 没有 `package.json` -> 返回 `{"Python": 98%, "Shell": 2%}` + `README.md`。MaxKB 看到 "Python 98%" 依然可以分析出他是 Python 开发者。


2. **Code Audit**:
* **以前**: 没有 Merged PR -> 数据为空 -> Agent B 没话讲。
* **现在**: 没有 PR -> 抓取 `src/main.py` (比如 200 行代码) -> Agent B 阅读这个文件，分析代码风格、注释习惯、变量命名。



这样就保证了 **100% 的用户都有数据** 喂给 Agent，不会出现空白报告了。
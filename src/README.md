# GitHub User Data Collection & Analysis

## 简介
本目录包含一组 Python 脚本，用于批量收集 GitHub 用户名单，并进一步抓取这些用户在 GitHub / OpenDigger 上的指标数据，最终产出可用于分析与可视化的结构化 JSON 文件。

## 1. 核心代码

### `get_user_name.py` (获取用户名单)
*   **作用**: 通过 GitHub Search API 按粉丝数区间 (`followers:min..max`) 抓取用户名列表，并自适应缩放区间以规避 Search API 的 1000 条结果上限。
*   **主要输入**:
    *   可选：项目根目录 `config.json` 中的 `github_token`（用于提升速率限制）
    *   可选：已存在的 `data/users_list.json`（会自动加载并去重，起到“断点续跑”的效果）
*   **主要输出**: `data/users_list.json`（JSON 数组：用户名字符串列表）

### `get_user_info.py` (获取详细数据)
*   **作用**: 读取用户名单，批量抓取 OpenDigger 指标（当前包含 `openrank.json`、`activity.json`），并将成功结果汇总保存。
*   **主要输入**: `data/users_list.json`
*   **主要输出**: `data/macro_data/macro_data_results.json`（JSON 对象：`username -> {username, openrank, activity, status}`）

### `get_all_metrics.py` (抓取 6 维原始指标数据)
*   **作用**: 综合使用 GitHub API + OpenDigger API，为每个用户抓取并计算多维原始指标与 0-100 分数（影响力、贡献度、维护力、参与度、多样性、代码能力），并拆分为文件落盘。
*   **主要输入**:
    *   `data/users_list.json`
    *   项目根目录 `config.json` 中的 `github_tokens`（数组）或环境变量 `GITHUB_TOKENS`（逗号分隔），用于轮询 Token
    *   可选：`--refresh` 或环境变量 `REFRESH_DATA=1`（强制重抓，忽略已存在文件）
*   **主要输出**: `data/raw_users/<username>/` 目录下的多个 JSON 文件，例如：
    *   `<username>_influence.json`
    *   `<username>_contribution.json`
    *   `<username>_maintainership.json`
    *   `<username>_engagement.json`
    *   `<username>_diversity.json`
    *   `<username>_code_capability.json`

### `calculate_radar.py` (计算雷达图分数)
*   **作用**: 读取 `data/raw_users/<username>/` 下的原始指标，进行对数变换 + 统计归一化，生成 6 维雷达分数（50-100 区间）。
*   **主要输入**:
    *   `data/users_list.json`
    *   `data/raw_users/<username>/*_*.json`（由 `get_all_metrics.py` 生成）
    *   可选：`--refresh` 或环境变量 `REFRESH_DATA=1`（忽略已有输出重新计算）
*   **主要输出**: `data/radar_scores.json`（JSON 对象：`username -> [influence, contribution, maintainership, engagement, diversity, code_capability]`）

### `fetch_representative_repos.py` (抓取代表仓库)
*   **作用**: 为每个用户抓取其个人仓库列表，并对仓库计算一个代表性/贡献度分数（结合代码量、stars、forks、该用户在仓库中的贡献次数等），用于挑选“代表作”仓库。
*   **主要输入**:
    *   `data/users_list.json`
    *   项目根目录 `config.json` 的 `github_token` / `github_tokens[0]` 或环境变量 `GITHUB_TOKEN`
    *   可选：`--refresh` 或环境变量 `REFRESH_DATA=1`
*   **主要输出**: `data/raw_users/<username>/representative_repos.json`（JSON 数组：仓库列表与打分、语言构成等字段）

### `fetch_tech_stack_context.py` (抓取技术栈上下文)
*   **作用**: 为每个用户选取其 star 最高的 3 个非 fork 仓库，抓取语言构成与关键工程文件（如 `package.json`、`go.mod`、`Dockerfile`、CI 配置等）的内容片段，形成用于“技术栈画像”的上下文数据。
*   **主要输入**:
    *   `data/users_list.json`
    *   项目根目录 `config.json` 的 `github_tokens`（数组）或 `github_token`
    *   可选：`--refresh` 或环境变量 `REFRESH_DATA=1`
*   **主要输出**: `data/raw_users/<username>/tech_stack.json`（JSON 数组：Top3 仓库信息、语言构成、目标文件内容片段）

## 2. 如何运行

### 第一步：获取用户名单
```bash
# 确保已安装 requests、tqdm
# 默认配置：从 500 粉丝开始，目标获取 500 用户
python get_user_name.py
```
> 输出文件: `../data/users_list.json`

### 第二步：抓取 OpenDigger 指标 (OpenRank & Activity)
```bash
# 默认配置：从 users_list.json 读取用户名
python get_user_info.py
```
> 输出文件: `../data/macro_data/macro_data_results.json`

### 第三步：抓取多维原始指标 (可选)
```bash
python get_all_metrics.py
```
> 输出目录: `../data/raw_users/<username>/`

### 第四步：计算雷达分数 (可选)
```bash
python calculate_radar.py
```
> 输出文件: `../data/radar_scores.json`

### 额外：代表仓库与技术栈上下文 (可选)
```bash
python fetch_representative_repos.py
python fetch_tech_stack_context.py
```
> 输出文件: `../data/raw_users/<username>/representative_repos.json` 与 `../data/raw_users/<username>/tech_stack.json`



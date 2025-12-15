# GitHub User Data Collection & Analysis

## 简介
本项目包含两个核心 Python 脚本，旨在自动化收集 GitHub 活跃用户名单，并进一步抓取这些用户在 OpenDigger 上的详细开源分析数据。

## 1. 核心代码

### `get_user_name.py` (获取用户名单)
*   **功能**: 利用 GitHub Search API 批量抓取 GitHub 用户名。
*   **特性**:
    *   **自适应分段**: 自动将查询条件（如粉丝数）拆分为小区间（如 `followers:500..550`），突破 GitHub API 单次返回 1000 条的限制。
    *   **断点续传**: 自动记录抓取进度（`fetch_state.json`），中断后可无缝继续。
    *   **去重保存**: 实时去重并定期（每 500 条）保存到 JSON，防止数据丢失。
    *   **防止死循环**: 智能处理超过 1000 条结果的密集区间。

### `get_user_info.py` (获取详细数据)
*   **功能**: 根据用户名单，批量获取 OpenDigger 的多维指标数据（OpenRank、Activity、Network 等）。
*   **特性**:
    *   **多线程并发**: 使用 `ThreadPoolExecutor` 加速抓取。
    *   **可视化进度**: 集成 `tqdm` 进度条，实时展示抓取状态和剩余时间。
    *   **智能过滤**: 自动剔除无效数据，只保留成功抓取的用户记录。
    *   **增量抓取**: 自动跳过已存在的记录，支持多次运行补充数据。

## 2. 如何运行

### 第一步：获取用户名单
```bash
# 确保已安装 requests
# 默认配置：从 500 粉丝开始，目标获取 6000 用户
python get_user_name.py
```
> 输出文件: `users_list.json`

### 第二步：获取详细数据
```bash
# 确保已安装 tqdm
# 自动读取上一步生成的 users_list.json
python get_user_info.py
```
> 输出文件: `_users_info.json`

## 3. 文件结构
*   `get_user_name.py`: 用户抓取脚本
*   `get_user_info.py`: 数据详情抓取脚本
*   `users_list.json`: (自动生成) 纯用户名的 JSON 列表
*   `_users_info.json`: (自动生成) 包含详细指标的最终数据文件
*   `fetch_state.json`: (自动生成) 用于记录抓取进度的状态文件

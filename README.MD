[![Python Version](https://img.shields.io/badge/python-%3E%3D3.8-red)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

# OpenScout

## 目录
- [简介](#简介)
- [核心特性](#核心特性)
- [技术架构](#技术架构)
- [安装部署](#安装部署)
- [MaxKB 智能体配置](#maxkb-智能体配置)

---

## 简介

**OpenScout** 是一个专注于 GitHub 开发者深度画像与技术能力评估的智能分析系统。通过结合 GitHub API、OpenDigger 开源生态数据以及多维度评估模型，OpenScout 能够自动化构建开发者的全景技术档案，从影响力、贡献度、维护力、参与度、多样性、代码能力六个维度进行量化评分。

本项目采用**多 Agent 协作**的数据采集与分析架构，旨在帮助开源社区、企业与猎头发现高质量的开发者人才，并为开发者提供客观的个人技术影响力报告。

![搜索页面](image/screenshot-search.png)

---

## 核心特性

### 1. 基于 MaxKB 的多智能体分析流水线
#### Agents 职责概览

- #### **The Career Strategist**：基于 Profile、六维雷达与 OpenRank/活跃度趋势，判断职业阶段（上升/稳定/沉寂）、社区生态位（Maintainer/Core/Casual），给出结论式画像

- #### **The Tech Stack Evaluator**：基于语言分布与 Topics，提炼核心技术栈（排除辅助语言）、评估技术广度（I 型/T 型），并判断技术栈的现代性与技术品味

- #### **The Project Analyst**：基于 Top 仓库的 Description/README 文档，判断项目含金量（玩具/练习/资料/生产级），评估文档与工程素养（安装、架构、测试、徽章等）及沟通表达能力

- #### **Chief Talent Officer**：综合以上三位 Agent 输出，生成结构化的《OpenScout 深度人才评估报告》，包含核心画像、技术基因、项目实战

- #### **Keywords Generator**：基于《OpenScout 深度人才评估报告》生成 概括该任务的3个精准关键词：`tech_core` / `career_persona` / `engineering_trait`。

![Multi-Agent Architecture](image/Multi-agent.png)

### 报告案例 

![报告分析](image/screenshot-report.png)


### 2. 多维度能力雷达 (6-Dimension Radar)
基于自研评估模型，从以下六个维度对开发者进行量化评分（50-100 分）。所有原始指标经过 $\ln(x+1)$ 对数正态分布归一化，并通过 CDF 映射至 50-100 区间。

$$
\text{Score}_{\text{final}} = 50 + 50 \cdot \Phi \left( \frac{\ln(S_{\text{raw}} + 1) - \mu}{\sigma} \right)
$$

我们从六个核心维度对开发者的开源贡献进行量化评估：

#### 1. 影响力 (Influence)

$$S_{\text{inf}} = \underbrace{\color{#e3b341}{0.6 \cdot \text{Stars}}}_{\text{认可度}} + \underbrace{0.4 \cdot (\color{#3fb950}{\text{Forks}} + \color{#f85149}{\text{Issues}})}_{\text{扩散与反馈}}$$

*反映项目在社区中的品牌效应与关注广度。*

---

#### 2. 贡献度 (Contribution)

$$S_{\text{con}} = \underbrace{\color{#238636}{0.7 \cdot \text{PRs}_{\text{merged}}}}_{\text{功能实现}} + \underbrace{\color{#8957e5}{0.3 \cdot \text{Issues}_{\text{created}}}}_{\text{问题发现}}$$

*衡量对开源生态的实质性代码产出与建设。*

---

#### 3. 维护力 (Maintainership)

$$S_{\text{main}} = \underbrace{\color{#0969da}{0.7 \cdot \text{Merged Others' PRs}}}_{\text{决策权力}} + \underbrace{\color{#1a7f37}{0.3 \cdot \text{Review Comments}}}_{\text{质量把控}}$$

*体现作为项目 Lead 处理他人代码的责任感与活跃度。*

---

#### 4. 参与度 (Engagement)

$$S_{\text{eng}} = \underbrace{\color{#0969da}{0.6 \cdot \text{Comments}_{\text{issue}}}}_{\text{社区交流}} + \underbrace{\color{#1a7f37}{0.4 \cdot \text{Comments}_{\text{review}}}}_{\text{技术深研}}$$

*反映开发者在社区讨论与协同开发中的活跃程度。*

---

#### 5. 多样性 (Diversity)

$$S_{\text{div}} = \underbrace{\color{#0969da}{0.6 \cdot \text{Languages}}}_{\text{技能广度}} + \underbrace{\color{#dd7ad2}{0.4 \cdot \text{Topics}}}_{\text{领域跨度}}$$

*通过技术栈种类与项目标签评估开发者的知识领域边界。*

---


#### 6. 代码能力 (Code Capability)

$$S_{\text{code}} = \sum_{PR \in \text{Merged}} \underbrace{\ln(\text{Repo Stars} + 1)}_{\text{项目含金量权重}}$$

*基于合并 PR 所属仓库的 Star 数进行对数加权，体现“在高价值项目中的代码贡献”。*

---

### 雷达 / 趋势 / 技术栈案例

![雷达图 + OpenRank 趋势 + 技术栈分布](image/screenshot-dashboard.png)

### 3. 智能语义搜索 (Smart Search)

OpenScout 不仅支持基于 ID 的精确查询，还内置了强大的**语义搜索引擎**。系统会为每位开发者的技术栈、项目描述和 README 文档生成高维向量索引 (Embeddings)，从而支持自然语言模糊匹配。

- **自然语言交互**：您可以直接输入 "寻找擅长 Rust 和高性能网络的后端工程师" 或 "Looking for a React frontend expert"。
- **向量数据库**：内置轻量级向量存储 (`vector_store.json`)，支持增量更新与持久化，首次启动会自动构建索引。
- **混合特征提取**：搜索算法综合考虑了开发者的编程语言偏好、GitHub Topics 以及核心仓库的 README 内容。

### 4. 仓库智能分析

在开发者详情页的「代表仓库」列表中，支持对单个仓库进行基于大模型的自动介绍与总结：系统会根据仓库 URL 自动拉取 `README.md`、Repository Description 与 Topics，并调用 LLM 生成一段简洁的仓库说明，支持流式输出展示。

#### 案例

![代表仓库](image/screenshot-repos.png)

#### 分析案例

![代表仓库分析](image/screenshot-repo-analysis.png)

---

## 技术架构

OpenScout 面向“数据采集 + 指标建模 + 智能分析 + 可视化展示”构建端到端链路，核心由四层组成：

- **数据层（GitHub / OpenDigger）**：提供开发者事件、仓库元数据与生态宏观指标（OpenRank、Activity 等）。
- **采集与建模层 (Pipeline)**：位于 `src/`，以脚本流水线方式按阶段增量抓取与计算，将结构化结果落盘到 `data/`。包含向量生成器以支持检索。
- **服务层 (Backend API)**：`server.py` 对外提供统一 API（数据查询/流式 AI 响应），托管静态资源（`/images`），并负责后台自动挖掘任务。
- **分析层 (AI Agents)**：
  - **MaxKB 多 Agent**：对结构化表单数据进行“岗位画像/技术栈评估/项目审计”深度分析。
  - **LLM**：
    - **Search Embedding**：使用 `text-embedding-v4` 模型生成用户画像向量。
    - **Repo Summary**：针对单个仓库进行实时流式摘要与技术点提炼。

### 前端技术栈

- `search.htm` / `profile.htm`：原生 HTML + JS 构建的轻量级前端（无需构建工具）。
- **Tailwind CSS**：原子化 CSS 样式框架。
- **Chart.js**：高性能数据可视化引擎（雷达图/趋势图/技术栈分布）。
- **Marked.js**：前端 Markdown 实时渲染（用于 AI 报告与仓库摘要展示）。

### 后端技术栈

- **FastAPI**：高性能 Python Web 框架（异步流式响应、后台任务管理）。
- **OpenDigger API**：开源生态数据分析（OpenRank、Activity）。
- **GitHub API**：基础数据源（用户资料、仓库/事件相关数据）。
- **Qwen API**：提供语义搜索所需的 Embedding 服务和大模型流式推理（仓库智能摘要）。
- **MaxKB API**：多 Agent 智能分析编排。
- `config.json`：统一配置管理（API Tokens、模型参数）。

### 目录结构

```
OpenScout/
├── data/                       # 数据存储目录
│   ├── raw_users/              # 用户维度的详细原始数据（JSON）
│   ├── macro_data/             # OpenDigger 宏观指标缓存
│   ├── users_list.json         # 目标用户名单
│   ├── radar_scores.json       # 最终计算的雷达分数
│   └── vector_store.json       # 开发者向量索引（用于语义检索）
├── src/                        # 核心源代码 (Pipeline)
│   ├── get_user_name.py              # [Scout] 用户名单获取
│   ├── get_user_info.py              # [Metric] OpenDigger 数据获取
│   ├── get_all_metrics.py            # [Metric] 全维度指标抓取
│   ├── calculate_radar.py            # [Analysis] 雷达分计算
│   ├── fetch_representative_repos.py # [Context] 代表作抓取
│   ├── fetch_tech_stack_context.py   # [Context] 技术栈上下文提取
│   └── run_pipeline.py               # [Orchestrator] 数据流水线入口
├── image/                      # 静态图片资源 (Icon, 截图等)
├── search.htm                  # [Frontend] 搜索/首页
├── profile.htm                 # [Frontend] 个人画像详情页
├── server.py                   # [Backend] FastAPI 后端服务
├── config.json                 # 配置文件 (Token, API Key)
├── OpenScout.mk                # [MaxKB] 多 Agent 导出包
├── Intro2MaxKB.md              # MaxKB 配置文档
├── requirements.txt            # 项目依赖文件
└── README.md                   # 项目文档
```

---

## 安装部署

### 环境要求
- Python 3.8+
- 推荐使用虚拟环境 (venv / conda)

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置（GitHub / MaxKB / LLM）
在项目根目录创建/编辑 `config.json`：

```json
{
  // 单个 GitHub 个人访问令牌 (Classic 或 Fine-grained)
  "github_token": "YOUR_GITHUB_TOKEN_HERE",

  // GitHub 令牌池，支持配置多个以绕过 API 速率限制 (Rate Limit)
  "github_tokens": [
    "YOUR_GITHUB_TOKEN_1",
    "YOUR_GITHUB_TOKEN_2"
  ],

  // MaxKB 知识库系统的 API 终端地址
  "maxkb_api_url": "http://your-maxkb-host:8080/chat/api/YOUR_APPLICATION_ID",
  
  // MaxKB 应用的 API Key
  "maxkb_api_key": "application-YOUR_MAXKB_KEY",

  // DeepSeek 官方 API 终端地址 (用于仓库分析)
  "qwen_api_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
  "qwen_api_key": "sk-YOUR_DEEPSEEK_KEY",
  "qwen_embedding_model": "text-embedding-v4"
}
```

### 3. 运行数据流水线([流水线文档](./src/README.md))

#### 方式一：一键全自动运行 (推荐)
使用 `run_pipeline.py` 脚本按顺序执行所有步骤：
```bash
python src/run_pipeline.py
```
该脚本将依次执行：
1. 名单发现 (`get_user_name`)
2. OpenDigger 数据 (`get_user_info`)
3. 六维指标抓取 (`get_all_metrics`)
4. 雷达计算 (`calculate_radar`)
5. 上下文补充 (`fetch_tech_stack_context`, `fetch_representative_repos`)

#### 方式二：分步手动运行

**第一步：获取目标用户名单**
```bash
# 默认配置：扫描 500 粉丝以上的用户
python src/get_user_name.py
```
> 输出: `data/users_list.json`

**第二步：抓取 OpenDigger 宏观数据**
```bash
# 抓取 OpenRank 和 Activity 指标
python src/get_user_info.py
```
> 输出: `data/macro_data/macro_data_results.json`

**第三步：抓取六维原始指标**
```bash
# 这一步会调用 GitHub API，耗时较长
python src/get_all_metrics.py
```
> 输出: `data/raw_users/<username>/*.json`

**第四步：计算雷达分数**
```bash
# 基于抓取的原始指标计算最终得分
python src/calculate_radar.py
```
> 输出: `data/radar_scores.json`

**第五步：抓取补充上下文 (可选)**
```bash
# 获取技术栈详情与代表作
python src/fetch_tech_stack_context.py
python src/fetch_representative_repos.py
```

### 4. 启动服务

```bash
python server.py
```

默认启动后打开 `http://localhost:8001`。首次启动进行搜索时，后台会自动为现有用户生成向量索引，可能需要数分钟。

## MaxKB 智能体配置

MaxKB 侧的部署、导入与联调细节见：[Intro2MaxKB](Intro2MaxKB.md)。

- 导入：将 `OpenScout.mk` 导入 MaxKB
- 配置：为各 Agent 绑定可用模型并发布
- 联调：配置 `config.json` 中的 `maxkb_api_url` / `maxkb_api_key` 后，通过前端触发分析

## 贡献指南
欢迎提交 Issue 或 Pull Request 来改进评估模型或增加新的数据源支持。

---

## License
[MIT License](LICENSE)

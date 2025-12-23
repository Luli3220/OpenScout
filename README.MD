[![Python Version](https://img.shields.io/badge/python-%3E%3D3.8-red)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

# OpenScout

## 目录
- [简介](#简介)
- [核心特性](#核心特性)
- [技术架构](#技术架构)
- [安装部署](#安装部署)
- [MaxKB 智能体配置](#maxkb-智能体配置)

## 简介

**OpenScout** 是一个专注于 GitHub 开发者深度画像与技术能力评估的智能分析系统。通过结合 GitHub API、OpenDigger 开源生态数据以及多维度评估模型，OpenScout 能够自动化构建开发者的全景技术档案，从影响力、贡献度、维护力、参与度、多样性、代码能力六个维度进行量化评分。

本项目采用**多 Agent 协作**的数据采集与分析架构，旨在帮助开源社区、企业与猎头发现高质量的开发者人才，并为开发者提供客观的个人技术影响力报告。

## 核心特性

### 1. 多维度能力雷达 (6-Dimension Radar)
基于自研评估模型，从以下六个维度对开发者进行量化评分（50-100 分）。所有原始指标经过 $\ln(x+1)$ 对数正态分布归一化，并通过 CDF 映射至 50-100 区间。

```text
Score_final = 50 + 50 * Φ((ln(S_raw + 1) - μ) / σ)
```

#### 维度定义与计算公式：

- **影响力 (Influence)**
  ```text
  S_inf = 0.6 * Stars + 0.4 * (Forks + Issues)
  ```
  *综合 Stars、Forks、Issues 等社区关注度指标，反映项目的受关注程度。*

- **贡献度 (Contribution)**
  ```text
  S_con = 0.7 * Merged PRs + 0.3 * Created Issues
  ```
  *核心考量外部 PR 贡献与 Issue 提出数量，反映开发者对开源社区的实质性产出。*

- **维护力 (Maintainership)**
  ```text
  S_main = 1.0 * Merged Others' PRs + 0.3 * Review Comments
  ```
  *评估作为维护者合并 PR 与 Code Review 的活跃度，体现项目维护责任感。*

- **参与度 (Engagement)**
  ```text
  S_eng = 0.6 * Issue Comments + 0.4 * Review Comments
  ```
  *社区互动与讨论参与程度，反映开发者在社区中的活跃交流情况。*

- **多样性 (Diversity)**
  ```text
  S_div = 0.6 * Languages + 0.4 * Topics
  ```
  *技术栈广度与跨领域项目涉猎情况，衡量技术视野的宽广度。*

- **代码能力 (Code Capability)**
  ```text
  S_code = Σ_{PR ∈ Merged} ln(Repo Stars + 1)
  ```
  *基于合并代码所属仓库的 Stars 权重进行深度评估，体现代码被认可的含金量。*

### 2. 智能多 Agent 数据流水线
### 多 Agent 职责概览

- **The Career Strategist**：基于 Profile、六维雷达与 OpenRank/活跃度趋势，判断职业阶段（上升/稳定/沉寂）、社区生态位（Maintainer/Core/Casual），给出结论式画像。
- **The Tech Stack Evaluator**：基于语言分布与 Topics，提炼核心技术栈（排除辅助语言）、评估技术广度（I 型/T 型），并判断技术栈的现代性与技术品味。
- **The Project Analyst**：基于 Top 仓库的 Description/README 片段，判断项目含金量（玩具/练习/资料/生产级），评估文档与工程素养（安装、架构、测试、徽章等）及沟通表达能力。
- **Chief Talent Officer**：综合以上三位 Agent 输出，生成结构化的《OpenScout 深度人才评估报告》，包含核心画像、技术基因、项目实战与招聘建议（岗位方向/面试重点）。
- **Keywords Generator**：基于《OpenScout 深度人才评估报告》生成 3 个精准关键词，并严格按 JSON 输出：`tech_core` / `career_persona` / `engineering_trait`。

![Multi-Agent Architecture](image/Multi-agent.png)

## 技术架构

OpenScout 面向“数据采集 + 指标建模 + 智能分析 + 可视化展示”构建端到端链路，核心由四层组成：

- **数据层（GitHub / OpenDigger）**：提供开发者事件、仓库元数据与生态宏观指标（OpenRank、Activity 等）。
- **采集与建模层（Pipeline）**：位于 `src/`，以脚本流水线方式按阶段增量抓取与计算，将结构化结果落盘到 `data/`。
- **服务层（Backend API）**：`server.py` 对外提供统一 API，并负责触发缺失用户的自动挖掘与缓存读取。
- **分析层（MaxKB 多 Agent）**：通过 MaxKB 编排多 Agent，对结构化表单数据进行“岗位画像/技术栈评估/项目审计/总结归纳”等深度分析。

### 前端技术栈

- `OpenScout.htm`：前端（HTML + JS）
- Tailwind CSS：样式框架
- Chart.js：数据可视化引擎（雷达图/趋势图/技术栈分布）
- Marked.js：Markdown 渲染（多 Agent 分析报告展示）

### 后端技术栈

- FastAPI：Python Web 框架（统一 API、静态页面托管、后台任务）
- OpenDigger API：开源生态数据分析（OpenRank、Activity）
- GitHub API：基础数据源（用户资料、仓库/事件相关数据）
- MaxKB API：多 Agent 智能分析编排（可对接星火等大模型）
- `config.json`：本地配置管理（Token、MaxKB 接入参数）



### 目录结构
```
OpenScout/
├── data/                   # 数据存储目录
│   ├── raw_users/          # 用户维度的详细原始数据（JSON）
│   ├── macro_data/         # OpenDigger 宏观指标缓存
│   ├── users_list.json     # 目标用户名单
│   └── radar_scores.json   # 最终计算的雷达分数
├── src/                    # 核心源代码
│   ├── get_user_name.py              # [Scout] 用户名单获取
│   ├── get_user_info.py              # [Metric] OpenDigger 数据获取
│   ├── get_all_metrics.py            # [Metric] 全维度指标抓取
│   ├── calculate_radar.py            # [Analysis] 雷达分计算
│   ├── fetch_representative_repos.py # [Context] 代表作抓取
│   └── fetch_tech_stack_context.py   # [Context] 技术栈上下文提取
│   └── run_pipeline                  # [Context] 数据初始化or新用户自动挖掘
│   └── README.md                     # [Context] 数据挖掘介绍文档
├── OpenScout.htm           # [Frontend] 前端展示页面
├── server.py               # [Backend] 后端 API 服务
├── OpenScout.mk            # [MaxKB] 多Agent导出包
├── requirements.txt        # [Dependency] 项目依赖文件
├── config.json             # 配置文件 (Token 等)
└── README.md               # 项目文档
└── Intro2MaxKB.md          # MaxKB配置文档
```

## 安装部署

### 环境要求
- Python 3.8+
- 推荐使用虚拟环境 (venv / conda)

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置（GitHub / MaxKB）
在项目根目录创建/编辑 `config.json`：

```json
{
  "github_tokens": [
    "ghp_your_token_1",
    "ghp_your_token_2"
  ],
  "maxkb_api_url": "http://localhost:8080/chat/api/<app_id>",
  "maxkb_api_key": "application-your-api-key"
}
```

说明：

- `github_tokens`：用于 GitHub API 访问与速率限制轮询。
- `maxkb_api_url`：MaxKB 应用 API 的基础路径（不包含 `/chat/completions`）。
- `maxkb_api_key`：MaxKB 访问 Key（用于 `Authorization: Bearer ...`）。

### 3. 运行数据流水线([详情见](./src/README.md))

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

默认启动后打开 `http://localhost:8001`。

## MaxKB 智能体配置

MaxKB 侧的部署、导入与联调细节见：[Intro2MaxKB](Intro2MaxKB.md)。

- 导入：将 `OpenScout.mk` 导入 MaxKB
- 配置：为各 Agent 绑定可用模型并发布
- 联调：配置 `config.json` 中的 `maxkb_api_url` / `maxkb_api_key` 后，通过前端触发分析

## 贡献指南
欢迎提交 Issue 或 Pull Request 来改进评估模型或增加新的数据源支持。

## License
[MIT License](LICENSE)

# OpenScout

[![Python Version](https://img.shields.io/badge/python-%3E%3D3.8-red)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
![b111bf2b96bf376180b7fcd1dd3ede8.png](https://raw.githubusercontent.com/Frank-whw/img/main/blog/202412302221674.png)

## 目录
- [简介](#简介)
- [核心特性](#核心特性)
- [架构概览](#架构概览)
- [快速开始](#快速开始)

## 简介

**OpenScout** 是一个专注于 GitHub 开发者深度画像与技术能力评估的智能分析系统。通过结合 GitHub API、OpenDigger 开源生态数据以及多维度评估模型，OpenScout 能够自动化构建开发者的全景技术档案，从影响力、贡献度、维护力、参与度、多样性、代码能力六个维度进行量化评分。

本项目采用**多 Agent 协作**的数据采集与分析架构，旨在帮助开源社区、企业与猎头发现高质量的开发者人才，并为开发者提供客观的个人技术影响力报告。

## 核心特性

### 1. 多维度能力雷达 (6-Dimension Radar)
基于自研评估模型，从以下六个维度对开发者进行量化评分（50-100 分）。所有原始指标经过 $\ln(x+1)$ 对数正态分布归一化，并通过 CDF 映射至 50-100 区间。

$$ Score_{final} = 50 + 50 \times \Phi\left(\frac{\ln(S_{raw} + 1) - \mu}{\sigma}\right) $$

#### 维度定义与计算公式：

- **影响力 (Influence)**
  $$ S_{inf} = 0.6 \cdot \text{Stars} + 0.4 \cdot (\text{Forks} + \text{Issues}) $$
  *综合 Stars、Forks、Issues 等社区关注度指标，反映项目的受关注程度。*

- **贡献度 (Contribution)**
  $$ S_{con} = 0.7 \cdot \text{Merged PRs} + 0.3 \cdot \text{Created Issues} $$
  *核心考量外部 PR 贡献与 Issue 提出数量，反映开发者对开源社区的实质性产出。*

- **维护力 (Maintainership)**
  $$ S_{main} = 1.0 \cdot \text{Merged Others' PRs} + 0.3 \cdot \text{Review Comments} $$
  *评估作为维护者合并 PR 与 Code Review 的活跃度，体现项目维护责任感。*

- **参与度 (Engagement)**
  $$ S_{eng} = 0.6 \cdot \text{Issue Comments} + 0.4 \cdot \text{Review Comments} $$
  *社区互动与讨论参与程度，反映开发者在社区中的活跃交流情况。*

- **多样性 (Diversity)**
  $$ S_{div} = 0.6 \cdot \text{Languages} + 0.4 \cdot \text{Topics} $$
  *技术栈广度与跨领域项目涉猎情况，衡量技术视野的宽广度。*

- **代码能力 (Code Capability)**
  $$ S_{code} = \sum_{\text{PR} \in \text{Merged}} \ln(\text{Repo Stars} + 1) $$
  *基于合并代码所属仓库的 Stars 权重进行深度评估，体现代码被认可的含金量。*

### 2. 智能多 Agent 数据流水线
系统包含多个专注于不同任务的 Agent 脚本，协同完成从名单发现到深度画像的全过程：
- **Scout Agent (`get_user_name`)**: 自适应分片算法突破 GitHub API 限制，海量扫描活跃开发者
- **Metric Agent (`get_all_metrics`)**: 并发抓取 GitHub 事件流与 OpenDigger 宏观指标
- **Context Agent (`fetch_tech_stack_context`)**: 深度提取核心仓库的工程配置文件（如 `go.mod`, `package.json`），构建技术栈上下文
- **Analysis Agent (`calculate_radar`)**: 运用统计学模型（对数正态分布归一化）计算最终雷达分数

### 3. 代表作自动甄选
- **Representative Repos**: 自动计算并筛选开发者最具代表性的 Top 仓库，综合考量代码贡献量与项目本身的影响力权重。

## 架构概览

![Multi-Agent Architecture](image/Multi-agent.png)

### 目录结构
```
OpenScout/
├── data/                   # 数据存储目录
│   ├── raw_users/          # 用户维度的详细原始数据（JSON）
│   ├── macro_data/         # OpenDigger 宏观指标缓存
│   ├── users_list.json     # 目标用户名单
│   └── radar_scores.json   # 最终计算的雷达分数
├── src/                    # 核心源代码
│   ├── get_user_name.py            # [Scout] 用户名单获取
│   ├── get_user_info.py            # [Metric] OpenDigger 数据获取
│   ├── get_all_metrics.py          # [Metric] 全维度指标抓取
│   ├── calculate_radar.py          # [Analysis] 雷达分计算
│   ├── fetch_representative_repos.py # [Context] 代表作抓取
│   └── fetch_tech_stack_context.py   # [Context] 技术栈上下文提取
├── OpenScout.htm           # [Frontend] 前端展示页面
├── server.py               # [Backend] 后端 API 服务
├── server.mk               # [MaxKB] 多Agent导出包
├── requirements.txt        # [Dependency] 项目依赖文件
├── config.json             # 配置文件 (Token 等)
└── README.md               # 项目文档
```

## 快速开始

### 环境要求
- Python 3.8+
- 推荐使用虚拟环境 (venv / conda)

### 1. 安装依赖
```bash
pip install requests tqdm
```

### 2. 配置 Token
在项目根目录创建 `config.json`，填入你的 GitHub Token：
```json
{
  "github_tokens": [
    "ghp_your_token_1",
    "ghp_your_token_2"
  ]
}
```

### 3. 运行数据流水线

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

## 贡献指南
欢迎提交 Issue 或 Pull Request 来改进评估模型或增加新的数据源支持。

## License
[MIT License](LICENSE)

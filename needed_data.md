根据您提供的《OpenScout：开源人才智能雷达与招募助手技术架构与实施战略报告》，为了构建全方位的人才画像，系统采用了“宏观生态度量”与“微观语义分析”相结合的双数据源策略。

以下是您可以从 OpenDigger 和 GitHub 获取的具体数据清单及其在 OpenScout 中的应用价值：

### 1. OpenDigger 数据（宏观生态与统计指标）
OpenDigger 主要用于获取经过预计算的高阶统计数据，这些数据构成了“人才雷达图”的量化基础，主要通过读取 OSS 上的静态 JSON 文件获取。

* **影响力数据 (`openrank`)**
    * **数据内容：** 用户的 OpenRank 分数。
    * **应用价值：** 作为衡量“社区影响力”的核心指标，用于抵御单纯的刷 Star 行为，反映用户在核心网络中的信任权重。

* **协作网络数据 (`developer_network.json`)**
    * **数据内容：** 包含节点（`nodes`，即开发者）和边（`edges`，即协作关系）的图结构数据，具体包括连接数（`degree`）和连接强度（`weight`）。
    * **应用价值：** 用于计算用户的“协作力”维度，分析其在项目中的社交中心度。

* **活跃度趋势数据 (`activity.json`)**
    * **数据内容：** 包含 Issue 评论、PR 开启与合并、代码 Review 等多种行为的时间序列数据。
    * **应用价值：**
        * **活跃度 (Activity)：** 通过近期加权算法计算月度活跃度。
        * **工程韧性 (Resilience)：** 通过计算活跃度的标准差（StdDev）来判断用户是“突击型”还是“长跑型（稳定输出）”选手。

* **效率数据 (`change_request_resolution_duration.json`)**
    * **数据内容：** PR（Pull Request）的处理时长数据。
    * **应用价值：** 用于评估代码审查响应速度和问题解决能力，反映“工程质量”维度。

### 2. GitHub API 数据（微观语义与实时画像）
GitHub API 用于获取实时的、文本级的细节信息，这是生成“语义级技能画像”和通过 LLM 进行深度分析的关键。

* **仓库列表与元数据 (`GET /users/{username}/repos`)**
    * **数据内容：** 用户名下的仓库列表、Fork 状态、Push 时间等。
    * **应用价值：** 用于筛选“有效仓库”。OpenScout 需要过滤掉用户 Fork 了但从未贡献的项目，只关注 `fork == false` 或有 Merged PR 的仓库，以避免技能画像虚高。
* **代码提交记录 (`GET /repos/{owner}/{repo}/commits`)**
    * **数据内容：** 具体的 Commit Message（提交信息），例如 "fix: race condition in Redis connection pool"。
    * **应用价值：** 用于提取深层技能标签。通过语义分析，将 Commit Message 转化为具体的技能点（如“并发控制”、“数据库优化”），而不仅仅是编程语言。
* **具体变更内容/Diffs (`GET /repos/{owner}/{repo}/commits/{ref}`)**
    * **数据内容：** 包含具体代码变更的 `patch` 文本。
    * **应用价值：** 针对包含特定关键词（如 `feat`, `refactor`, `perf`）的提交进行深度提取，供大模型分析代码风格和具体技术栈。
* **用户个人信息 (`Profile`)**
    * **数据内容：** Bio（个人简介）、Pinned Repos（置顶仓库）等。
    * **应用价值：** 补充基础画像信息，提供实时的个人展示面。

### 3. 数据映射总结
结合文档中的雷达图模型，这些数据将如下映射：

| 数据源 | 具体文件/接口 | 映射雷达图维度 |
| :--- | :--- | :--- |
| **OpenDigger** | `openrank` | **影响力 (Influence)** |
| **OpenDigger** | `activity.json` | **活跃度 (Activity)** |
| **OpenDigger** | `developer_network.json` | **协作力 (Collaboration)** |
| **OpenDigger** | `change_request_resolution_duration.json` | **工程质量 (Quality)** |
| **GitHub API** | `Commits` & `Languages` | **技术广度 (Breadth) & 技能云** |

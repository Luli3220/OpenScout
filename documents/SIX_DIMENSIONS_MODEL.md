# OpenScout 六维开发者评估模型

## 1. 核心理念
OpenScout 采用独创的六维评估模型，从多个角度全面量化开发者的开源能力与社区影响力。该模型不仅仅关注代码提交量，更深入分析代码质量、社区互动、项目维护责任以及技术栈的广度。

## 2. 六维数据来源与计算逻辑

### 🌟 影响力 (Influence)
*   **定义**: 衡量开发者在开源社区中的声望和项目受关注程度。
*   **数据来源**:
    *   **OpenDigger OpenRank**: 直接调用 OpenDigger API 获取该用户的时间序列 OpenRank 值（取最新值）。OpenRank 是基于网络分析算法（类似 PageRank）计算的权威影响力指数。
    *   **GitHub Repos API**: 遍历用户拥有的所有原创仓库（非 Fork），统计总 **Stars**（收藏数）和 **Forks**（复刻数）。
    *   **GitHub Issues**: 统计用户项目的 **Open Issues** 总数，作为项目热度的辅助指标。
*   **计算权重 (示例)**:
    *   Stars (60%): 直接反映项目受众规模。
    *   Forks + Issues (40%): 反映项目的参与度和使用深度。
    *   *(注: OpenRank 目前作为原始指标参考，未来将整合进核心算法)*

### 🛠️ 贡献度 (Contribution)
*   **定义**: 衡量开发者对**外部**开源生态的实际代码贡献能力。
*   **数据来源**:
    *   **GitHub Events API**: 抓取用户过去 90 天的动态流 (`/users/{username}/events/public`)。
    *   **External PRs**: 筛选出用户向**非自己名下**仓库提交的 Pull Request，并重点统计被 **Merged (已合并)** 的 PR 数量。
    *   **Issue Creation**: 统计用户创建的 Issue 数量，反映其发现问题和提出建议的活跃度。
*   **计算权重 (示例)**:
    *   已合并的外部 PR (70%): 高质量代码贡献的核心体现。
    *   创建 Issue (30%): 社区参与的体现。

### 🛡️ 维护力 (Maintainership)
*   **定义**: 衡量开发者作为项目维护者（Maintainer）管理代码合入和把控项目质量的能力。
*   **数据来源**:
    *   **GitHub Events API**: 深入分析 `PullRequestEvent`。
    *   **Merge Actions**: 统计用户作为执行者（Actor）**合并他人 PR** 的次数。这是一个关键指标，只有拥有仓库写权限的核心维护者才能执行此操作。
*   **计算权重 (示例)**:
    *   合并他人 PR 数量 (100%): 直接反映维护职责的履行情况。

### 💬 活跃度 (Engagement)
*   **定义**: 衡量开发者在技术讨论、代码审查（Code Review）等软技能方面的投入。
*   **数据来源**:
    *   **GitHub Events API**:
        *   `IssueCommentEvent`: 统计在 Issue 下的评论互动。
        *   `PullRequestReviewCommentEvent`: 统计在代码审查过程中的技术评论。
*   **计算权重 (示例)**:
    *   Issue 评论 (60%): 解决问题、答疑解惑的能力。
    *   PR 审查评论 (40%): 团队协作与代码质量把控能力。

### 🌈 多样性 (Diversity)
*   **定义**: 衡量开发者技术栈的广度（T型人才横向能力）和涉猎领域的丰富程度。
*   **数据来源**:
    *   **GitHub Repos API**: 遍历用户拥有的所有原创仓库。
    *   **Languages**: 提取每个仓库的 `language` 字段，去重统计掌握的编程语言数量。
    *   **Topics**: 提取每个仓库的 `topics` (标签)，去重统计涉足的技术领域（如 `machine-learning`, `web`, `security` 等）。
*   **计算权重 (示例)**:
    *   语言数量 (60%): 技术栈宽度的直接体现。
    *   主题数量 (40%): 业务领域和兴趣点的丰富度。

### 💻 代码能力 (Code Capability)
*   **定义**: 衡量开发者编写代码的技术含金量、工程规范意识以及被同行认可的技术深度。
*   **数据来源**:
    *   **GitHub Events API**: 分析 `PullRequestEvent`。
    *   **Core Contribution Value**: 统计被合并 PR 所属仓库的 Star 数，证明技术实力。
    *   **PR Merge Rate**: 计算 PR 的合并率，反映代码质量和通过率。
*   **计算权重 (示例)**:
    *   核心贡献含金量 (100%): $\sum \log(Repo\_Stars + 1)$，侧重于贡献的质量和难度。

## 3. 总结
通过整合 OpenDigger 的权威算法数据与 GitHub 原生 API 的实时行为数据，OpenScout 能够构建出一个比单纯 "Commit 数" 更立体、更真实的开发者画像。

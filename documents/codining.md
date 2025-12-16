

# 第六维度：💻 代码能力 (Code Capability)

## 1. 核心定义
衡量开发者编写代码的技术含金量、工程规范意识以及被同行认可的技术深度。它区别于“贡献度”（做了多少），这里关注的是（做得多好/多难）。

## 2. 数据来源与计算指标

### 方案 A：快速实现版 (适合现有 Demo)
*不需要深度扫描代码，利用 PR 的“含金量”和“通过率”来侧面印证。*

#### (1) 核心贡献含金量 (Core Contribution Value)
* **逻辑**: 向 10k stars 的库提交代码，比向 10 stars 的库提交代码，更能证明技术实力。
* **计算**:
    $$\sum (Merged\_PR_i \times \log(Repo\_Stars_i))$$
* **数据**: 既然你已经有了 `Merged External PRs`，只需要关联一下那个目标仓库的 Stars 数即可。

#### (2) PR 合并率 (PR Merge Rate)
* **逻辑**: 代码能力强的人，PR 被合入的概率高；代码质量差的人，PR 容易被 Close 或反复修改。
* **计算**:
    $$\frac{Merged\_PRs}{Merged\_PRs + Closed\_PRs\_(Unmerged)}$$
* **数据**: GitHub Events 或 Search API。


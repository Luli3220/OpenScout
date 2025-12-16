# OpenScout 开发者雷达图评分算法规范 (v1.0)

## 1. 算法设计思路
本模型旨在将原始的 GitHub 挖掘数据转换为 0-100 的标准分，用于前端雷达图展示。考虑到开源数据的长尾效应，我们采用 **"对数平滑 + Z-Score 标准化 + 概率分布映射"** 的三层处理逻辑。

## 2. 详细计算步骤

### 第一步：维度原始值聚合 (Raw Score Calculation)
根据 `FIVE_DIMENSIONS_MODEL.md` 定义的权重，计算五个维度的原始加权和。

设 $R$ 为某维度的原始得分：

#### 🌟 影响力 (Influence)
$$R_{inf} = (Stars \times 0.6) + ((Forks + Issues) \times 0.4)$$
*(注: OpenRank暂未加入计算，如加入可作为乘数因子)*

#### 🛠️ 贡献度 (Contribution)
$$R_{con} = (Merged\_External\_PRs \times 0.7) + (Created\_Issues \times 0.3)$$

#### 🛡️ 维护力 (Maintainership)
$$R_{main} = (Merged\_Others\_PRs \times 0.7) + (Review\_Comments \times 0.3)$$
*(注: 引入 Code Review 作为辅助指标，避免纯维护者得分过低)*

#### 💬 活跃度 (Engagement)
$$R_{eng} = (Issue\_Comments \times 0.6) + (Review\_Comments \times 0.4)$$

#### 🌈 多样性 (Diversity)
$$R_{div} = (Languages \times 0.6) + (Topics \times 0.4)$$

#### 💻 代码能力 (Code Capability)
$$R_{code} = \text{Core Contribution Value}$$
*   **Core Contribution Value**: $\sum \ln(Repo\_Stars + 1)$ (仅统计被合并的外部 PR)
*   **Fallback**: 若 Core Value 为 0，但有 `Closed PRs` 或 `Reviews`，给予基础分（如 15 分），避免得分为 0。

---

### 第二步：数据平滑与正态化 (Normalization)
由于 GitHub 数据存在极值（例如某人 Star 数为 5000，大多数人为 10），直接归一化会导致大多数人得分趋近于 0。

#### 1. 对数转换 (Log Transformation)
对原始值进行对数处理，减弱极值影响，使其更接近正态分布。需加 1 避免 $\ln(0)$ 错误。
$$L_{dim} = \ln(R_{dim} + 1)$$

#### 2. Z-Score 标准化 (Standardization)
计算样本集（100人）的均值（$\mu$）和标准差（$\sigma$），计算每个人的标准分数。
$$Z_{dim} = \frac{L_{dim} - \mu_{L}}{\sigma_{L}}$$
* $\mu_{L}$: 该维度下所有候选人 $L$ 值的平均数。
* $\sigma_{L}$: 该维度下所有候选人 $L$ 值的标准差。

---

### 第三步：百分制映射 (Score Mapping)
利用标准正态分布的**累积分布函数 (CDF)** 将 Z-Score 映射到概率区间 (0-1)，然后线性映射到 **50-100** 分区间。

$$Score_{final} = 50 + (\Phi(Z_{dim}) \times 50)$$

* $\Phi(z)$: 标准正态分布的累积分布函数。
* **直观理解**:
    * **起始分**: 50 分（只要有数据，就在 50 分基础上叠加）。
    * **平均水平 ($Z=0$)**: $50 + (0.5 \times 50) = 75$ 分。
    * **顶尖水平 ($Z=2$)**: $50 + (0.977 \times 50) \approx 98.8$ 分。
    * **入门水平 ($Z=-2$)**: $50 + (0.023 \times 50) \approx 51.1$ 分。

---

## 3. 极值与边界处理 (Edge Cases)

1.  **零值处理**:
    如果原始数据 $R = 0$（例如完全没有维护过项目），直接赋值 $Score = 50$（作为基础起点），不参与 Z-Score 计算。

2.  **超级巨星处理 (Outliers)**:
    如果某人的数据过于离谱（例如 Star 数是第二名的 10 倍），在计算均值和标准差时，建议剔除该最大值，或者设置封顶阈值（Winsorization），防止他一个人把剩下 99 个人都压成不及格。

---

## 4. Python 代码实现示例 (伪代码)

```python
import numpy as np
from scipy.stats import norm

def calculate_radar_score(raw_values):
    """
    raw_values: 一个列表，包含100个候选人在某一维度（如影响力）的原始值 R
    """
    # 1. 对数转换
    log_values = np.log1p(raw_values)  # log(x+1)

    # 2. 计算统计量 (可选择剔除最高分来计算均值，避免压制)
    mu = np.mean(log_values)
    sigma = np.std(log_values)

    # 防止标准差为0（所有人数据都一样）
    if sigma == 0:
        return [50 for _ in raw_values]

    scores = []
    for val in log_values:
        # 3. Z-Score
        z_score = (val - mu) / sigma
        
        # 4. CDF 映射到 0-100
        # norm.cdf 返回 0-1 的概率值
        final_score = norm.cdf(z_score) * 100
        
        # 保留一位小数
        scores.append(round(final_score, 1))
        
    return scores
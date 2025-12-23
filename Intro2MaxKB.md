# MaxKB 集成指南（OpenScout 多 Agent）

本指南面向需要在本地/内网部署 MaxKB，并将 OpenScout 的多 Agent 编排导入 MaxKB 的开发者与运维人员。内容覆盖：部署、导入、配置、联调与排障。

## 1. 目标与产出

- 在 MaxKB 中导入 OpenScout 的多 Agent 编排（`OpenScout.mk`）。
- 在 MaxKB 中配置各 Agent 使用的模型/供应商参数（如 OpenAI 兼容接口、私有模型等）。
- 在 OpenScout 后端（`config.json`）中配置 MaxKB 的调用地址与鉴权 Key，使前端可以触发分析并展示结果。

## 2. 前置条件

- 已具备可用的 MaxKB 实例（本地或内网可访问）。
- 已导入或创建可用的大模型配置（MaxKB 支持的模型供应商/私有推理服务均可）。
- 具备部署机器的网络访问权限（OpenScout 后端需要能访问 MaxKB）。

## 3. 本地部署 MaxKB

推荐优先参考 MaxKB 官方/社区教程进行部署与启动：

- https://github.com/1panel-dev/MaxKB

部署完成后，请先确认：

- MaxKB 管理控制台可正常访问；
- 已能在控制台中创建/管理 Agent；
- 可获取到 MaxKB 的 API Key 与应用 API 路径（下文会用到）。

## 4. 导入 OpenScout 多 Agent 编排

1. 进入 MaxKB 控制台的 Agent 管理页面，选择「导入」或「导入 Agent」。
2. 选择仓库根目录中的 `OpenScout.mk` 导出包
3. 导入后，在 Agent 列表中会看到 OpenScout 的多 Agent 编排。

![导入 OpenScout.mk](image/1.png)

## 5. 配置各 Agent 的模型与参数

导入完成后，需要将每个 Agent 绑定到你实际可用的模型配置上（例如：把默认模型替换为你的自建模型/云模型）。

1. 进入「Agent 管理」→ 打开 OpenScout 相关 Agent 详情。
2. 在模型设置处选择你已创建的模型配置，并根据需要调整：
   - 温度、最大输出 token；
3. 保存并发布 Agent。

![修改 Agent 模型](image/2.png)
![保存与发布](image/3.png)

## 6. 获取 MaxKB 调用地址与 API Key

OpenScout 后端会以 HTTP 的方式调用 MaxKB 的对话补全接口。你需要从 MaxKB 控制台获取：

- **API Key**：用于请求头 `Authorization: Bearer <key>`。
- **API 路径（App API URL）**：形如：
  - `http://localhost:8080/chat/api/019b49bc-be58-74e0-a63d-f2241073635c`

注意：OpenScout 后端会自动在该 URL 后拼接 `/chat/completions`，因此你在 `config.json` 中只需要保留到 `<app_id>` 为止。

![查看 Base URL / API Key](image/4.png)

## 7. 在 OpenScout 中配置 MaxKB（推荐方式）

编辑项目根目录的 `config.json`，增加以下字段（示例中的值请替换为你的环境）：

```json
{
  "github_tokens": ["ghp_your_token_1"],
  "maxkb_api_url": "http://localhost:8080/chat/api/<app_id>",
  "maxkb_api_key": "application-your-api-key"
}
```

字段说明：

- `maxkb_api_url`：MaxKB 应用 API 的基础路径（不包含 `/chat/completions`）。
- `maxkb_api_key`：MaxKB 访问 Key。

## 8. 联调验证（建议按顺序）

### 8.1 启动 OpenScout 后端

```bash
python server.py
```

默认启动地址见控制台输出（通常为 `http://localhost:8001`）。

### 8.2 通过浏览器触发分析

打开 `http://localhost:8001`，输入一个 GitHub 用户名点击「分析」。

预期表现：

- 页面基础数据（雷达/趋势/技术栈等）可先行加载；
- AI 分析内容随后逐步显示（由 `/api/analyze/{username}` 请求驱动）。

### 8.3 直接验证 MaxKB API（可选）

如需跳过 OpenScout 直接验证 MaxKB，可使用以下方式（仅示意）：

```bash
curl -X POST "http://localhost:8080/chat/api/<app_id>/chat/completions" \
  -H "Authorization: Bearer application-your-api-key" \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"ping\",\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}],\"stream\":false}"
```

若返回 HTTP 200 且包含 `choices` 等字段，说明 MaxKB API 可用。

## 9. 常见问题与排障

### 9.1 请求 401/403

- 检查 `maxkb_api_key` 是否正确；
- 检查 MaxKB 是否对 Key 做了 IP 白名单或权限限制；
- 确认请求头为 `Authorization: Bearer <key>`。

### 9.2 请求超时或返回 5xx

- 模型端响应慢：适当提升后端超时配置（OpenScout 默认对分析接口设置了较长超时）；
- MaxKB 资源不足：检查 MaxKB 服务端 CPU/内存/并发限制；
- 网络链路问题：确认 OpenScout 后端机器到 MaxKB 的连通性与 DNS 解析。

### 9.3 返回结构不符合预期

OpenScout 前端当前按 MaxKB 的 `choices[0].answer_list` 进行解析，若你在 MaxKB 侧修改了输出结构或模板，需保证输出仍然兼容该结构。

## 10. 安全建议

- 不要将真实 Token/API Key 提交到仓库；生产环境建议通过环境变量或私有配置注入。
- 内网部署建议启用 HTTPS 与鉴权策略，并限制 MaxKB 管理台的外部访问。

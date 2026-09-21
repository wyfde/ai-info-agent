# AI-INFO

面向 AI 产品经理、入门级 AI 解决方案顾问和 AI 应用开发求职者的行业信息筛选 agent。

## 工作流

1. 从 `data/inbox`、微信公众号 RSS/Atom 和已授权的飞书群采集信息。
2. 去重并按求职价值分类，生成不超过 500 字的日报。
3. 每天 22:00 保存日报。
4. 次日 08:00 将原日报发送到飞书。

## 配置

复制或修改 [config/config.json](config/config.json)：

- `wechat.rss_feeds`：微信公众号 RSS/Atom 地址。
- `feishu.group_chats`：飞书群 `chat_id` 和名称。
- `llm`：OpenAI 兼容接口的模型与地址。
- `inbox_dir`：也可以直接把文章或导出的群消息放入 `data/inbox`。

敏感信息通过环境变量提供：

```powershell
$env:AI_JOB_INTEL_LLM_API_KEY = "..."
$env:FEISHU_APP_ID = "..."
$env:FEISHU_APP_SECRET = "..."
$env:FEISHU_RECEIVE_ID = "..."
$env:FEISHU_WEBHOOK_URL = "..."
```

将 LLM API Key 写入项目配置：

```powershell
& "D:\AI-INFO\scripts\configure_llm.ps1"
& "D:\AI-INFO\scripts\check_llm.ps1"
```

Key 会写入 `config/config.json` 的 `llm.api_key` 字段。该配置文件已被 `.gitignore` 排除。也可以手动编辑：

```json
"llm": {
  "api_key": "你的API Key"
}
```

还可以只在当前 PowerShell 会话中临时设置：

```powershell
$env:AI_JOB_INTEL_LLM_API_KEY = "你的API Key"
```

发送日报只需要 `FEISHU_WEBHOOK_URL`，或者飞书应用的三项凭证。自动读取飞书群必须使用具备群消息读取权限的飞书应用。

## 接入飞书群

### 只发送日报

1. 在目标飞书群中添加“自定义机器人”。
2. 复制 Webhook 地址。
3. 设置环境变量 `FEISHU_WEBHOOK_URL`。
4. 运行 `scripts\run_morning.ps1` 测试发送。

这种方式不能读取群消息。

### 自动读取并发送

1. 在飞书开放平台创建“企业自建应用”。
2. 开启机器人能力，发布应用并让企业管理员审核通过。
3. 为应用添加群组和消息相关权限，至少包括 `im:chat:readonly`、`im:message.group_msg` 和发送消息权限。
4. 将机器人添加进目标飞书群。
5. 设置 `FEISHU_APP_ID` 和 `FEISHU_APP_SECRET`。
6. 运行 `scripts\list_feishu_chats.ps1`，找到目标群的 `chat_id`。
7. 将 `chat_id` 和群名写入 `config\config.json` 的 `feishu.group_chats`。
8. 将 `FEISHU_RECEIVE_ID` 设置为同一个 `chat_id`，用于发送日报。

## 发送到飞书多维表格

1. 在飞书创建多维表格，并建立字段：`日期`、`分类`、`标题`、`链接`、`摘要`、`求职启示`。
2. 复制多维表格 URL，写入 `config\config.json` 的 `feishu.bitable.url`。
3. 确认 `feishu.delivery` 为 `bitable`。
4. 在飞书开放平台为应用添加 `bitable:app` 权限并重新发布，同时在多维表格中把应用设为“可编辑”协作者。
5. 运行 `scripts\check_bitable.ps1` 检查目标表和字段权限。
6. 运行 `scripts\run_morning.ps1`，将前一晚日报逐条写入表格。

## 云端运行

项目包含两个 GitHub Actions 定时任务：

- `ai-info-evening.yml`：北京时间每天22:00采集并生成日报，提交到 `cloud_state`。
- `ai-info-morning.yml`：北京时间每天08:00读取前一晚报并写入飞书多维表格。

部署步骤：

1. 在 GitHub 创建私有仓库，并将 `D:\AI-INFO` 初始化为该仓库。
2. 在仓库的 `Settings > Secrets and variables > Actions` 添加：
   - `AI_JOB_INTEL_LLM_API_KEY`
   - `FEISHU_APP_ID`
   - `FEISHU_APP_SECRET`
3. 在仓库的 `Settings > Actions > General` 将 Workflow permissions 设为 `Read and write permissions`。
4. 打开 `Actions`，分别手动运行两个 Workflow，确认成功。
5. 云端验证成功后，关闭本机的两个 Codex 定时任务，避免重复执行。

## 运行

```powershell
$env:PYTHONPATH = "D:\AI-INFO\src"
py -3.10 -m ai_job_intel --config "D:\AI-INFO\config\config.json" collect
py -3.10 -m ai_job_intel --config "D:\AI-INFO\config\config.json" run-evening
py -3.10 -m ai_job_intel --config "D:\AI-INFO\config\config.json" run-morning
```

定时脚本位于 `scripts`，运行测试：

```powershell
$env:PYTHONPATH = "D:\AI-INFO\src"
py -3.10 -m unittest discover -s D:\AI-INFO\tests -v
```

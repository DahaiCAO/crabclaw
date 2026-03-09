# Slack（中文）

<p align="center">
  <a href="../../en/channels/slack.md"><strong>English</strong></a> | <a href="../../zh-CN/channels/slack.md"><strong>中文</strong></a>
</p>

使用 **Socket Mode**（无需公网 URL）。

## 1. 创建 Slack 应用
- 访问 https://api.slack.com/apps → Create New App → “From scratch”
- 选择名称与工作区

## 2. 配置应用
- **Socket Mode**：开启 → 生成 **App-Level Token**（`xapp-...`）
- **OAuth & Permissions**：添加 robot scopes `chat:write`, `reactions:write`, `app_mentions:read`
- **Event Subscriptions**：开启 → 订阅 `message.im`, `message.channels`, `app_mention`
- **App Home**：开启 **Messages Tab**
- **Install App**：安装到工作区 → 复制 **Bot Token**（`xoxb-...`）

## 3. 配置 crabclaw
```json
{
  "channels": {
    "slack": {
      "enabled": true,
      "botToken": "xoxb-...",
      "appToken": "xapp-...",
      "allowFrom": ["YOUR_SLACK_USER_ID"],
      "groupPolicy": "mention"
    }
  }
}
```

## 4. 运行
```bash
crabclaw gateway
```

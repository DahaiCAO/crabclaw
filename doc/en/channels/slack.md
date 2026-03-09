# Slack (EN)

<p align="center">
  <a href="../../en/channels/slack.md"><strong>English</strong></a> | <a href="../../zh-CN/channels/slack.md"><strong>中文</strong></a>
</p>

Uses **Socket Mode** (no public URL required).

## 1. Create a Slack app
- Go to https://api.slack.com/apps → Create New App → “From scratch”
- Pick a name and workspace

## 2. Configure the app
- **Socket Mode**: ON → generate **App-Level Token** (`xapp-...`)
- **OAuth & Permissions**: add bot scopes `chat:write`, `reactions:write`, `app_mentions:read`
- **Event Subscriptions**: ON → subscribe `message.im`, `message.channels`, `app_mention`
- **App Home**: enable **Messages Tab**
- **Install App**: install to workspace → copy **Bot Token** (`xoxb-...`)

## 3. Configure crabclaw
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

## 4. Run
```bash
crabclaw gateway
```

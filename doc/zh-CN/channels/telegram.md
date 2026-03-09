# Telegram（中文）

<p align="center">
  <a href="../../en/channels/telegram.md"><strong>English</strong></a> | <a href="../../zh-CN/channels/telegram.md"><strong>中文</strong></a>
</p>

## 1. 创建 Bot
- 打开 Telegram，搜索 `@BotFather`
- 发送 `/newbot`，按指引创建
- 复制生成的 Bot Token

## 2. 配置
在 `~/.crabclaw/config.json` 添加：
```json
{
  "channels": {
    "telegram": {
      "enabled": true,
      "token": "YOUR_BOT_TOKEN",
      "allowFrom": ["YOUR_USER_ID"]
    }
  }
}
```
说明：`YOUR_USER_ID` 可在 Telegram 中查看为 `@yourUserId`，填写时不带 `@`。

## 3. 运行
```bash
crabclaw gateway
```

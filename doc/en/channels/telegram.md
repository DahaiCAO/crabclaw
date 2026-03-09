# Telegram (EN)

<p align="center">
  <a href="../../en/channels/telegram.md"><strong>English</strong></a> | <a href="../../zh-CN/channels/telegram.md"><strong>中文</strong></a>
</p>

## 1. Create a bot
- Open Telegram, search `@BotFather`
- Send `/newbot`, follow prompts
- Copy the bot token

## 2. Configure
Add to `~/.crabclaw/config.json`:
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
Note: Find your `YOUR_USER_ID` in Telegram as `@yourUserId`. Use it without `@`.

## 3. Run
```bash
crabclaw gateway
```

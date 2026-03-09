# Discord (EN)

<p align="center">
  <a href="../../en/channels/discord.md"><strong>English</strong></a> | <a href="../../zh-CN/channels/discord.md"><strong>中文</strong></a>
</p>

## 1. Create a bot
- Go to https://discord.com/developers/applications
- Create an application → Bot → Add Bot
- Copy the bot token

## 2. Enable intents
- In Bot settings, enable **MESSAGE CONTENT INTENT**
- (Optional) Enable **SERVER MEMBERS INTENT**

## 3. Get your User ID
- Settings → Advanced → enable **Developer Mode**
- Right-click avatar → **Copy User ID**

## 4. Configure
```json
{
  "channels": {
    "discord": {
      "enabled": true,
      "token": "YOUR_BOT_TOKEN",
      "allowFrom": ["YOUR_USER_ID"]
    }
  }
}
```

## 5. Invite the bot
- OAuth2 → URL Generator
- Scopes: `bot`
- Bot Permissions: `Send Messages`, `Read Message History`
- Open invite URL and add the bot to your server

## 6. Run
```bash
crabclaw gateway
```

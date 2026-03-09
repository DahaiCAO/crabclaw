# Discord（中文）

<p align="center">
  <a href="../../en/channels/discord.md"><strong>English</strong></a> | <a href="../../zh-CN/channels/discord.md"><strong>中文</strong></a>
</p>

## 1. 创建 Bot
- 前往 https://discord.com/developers/applications
- 创建应用 → Bot → Add Bot
- 复制 Bot Token

## 2. 开启 Intents
- 在 Bot 设置中开启 **MESSAGE CONTENT INTENT**
- （可选）开启 **SERVER MEMBERS INTENT**

## 3. 获取你的 User ID
- 设置 → 高级 → 开启 **开发者模式**
- 右键头像 → **Copy User ID**

## 4. 配置
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

## 5. 邀请 Bot
- OAuth2 → URL Generator
- Scopes: `bot`
- 权限：`Send Messages`, `Read Message History`
- 打开生成的邀请链接，添加该 Bot 到你的服务器

## 6. 运行
```bash
crabclaw gateway
```

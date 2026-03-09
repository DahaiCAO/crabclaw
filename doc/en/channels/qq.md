# QQ (EN)

<p align="center">
  <a href="../../en/channels/qq.md"><strong>English</strong></a> | <a href="../../zh-CN/channels/qq.md"><strong>中文</strong></a>
</p>

Uses **botpy SDK** with WebSocket. Currently supports private messages only.

## 1. Register & create bot
- Visit https://q.qq.com → register as a developer
- Create a bot application
- Copy **AppID** and **AppSecret**

## 2. Sandbox setup
- In bot console: **沙箱配置**
- Add your own QQ number to **在消息列表配置**
- Scan the bot QR → open bot profile → tap “发消息”

## 3. Configure
```json
{
  "channels": {
    "qq": {
      "enabled": true,
      "appId": "YOUR_APP_ID",
      "secret": "YOUR_APP_SECRET",
      "allowFrom": ["YOUR_OPENID"]
    }
  }
}
```

## 4. Run
```bash
crabclaw gateway
```

# DingTalk (EN)

<p align="center">
  <a href="../../en/channels/dingtalk.md"><strong>English</strong></a> | <a href="../../zh-CN/channels/dingtalk.md"><strong>中文</strong></a>
</p>

Uses **Stream Mode** (no public IP required).

## 1. Create a DingTalk bot
- Visit https://open-dev.dingtalk.com/
- Create app → Add **Robot** capability
- Toggle **Stream Mode** ON
- Get **AppKey** and **AppSecret**
- Publish the app

## 2. Configure
```json
{
  "channels": {
    "dingtalk": {
      "enabled": true,
      "clientId": "YOUR_APP_KEY",
      "clientSecret": "YOUR_APP_SECRET",
      "allowFrom": ["YOUR_STAFF_ID"]
    }
  }
}
```

## 3. Run
```bash
crabclaw gateway
```

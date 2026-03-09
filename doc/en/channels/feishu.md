# Feishu (EN)

<p align="center">
  <a href="../../en/channels/feishu.md"><strong>English</strong></a> | <a href="../../zh-CN/channels/feishu.md"><strong>中文</strong></a>
</p>

Uses **WebSocket long connection** (no public IP required).

## 1. Create a Feishu bot
- Visit https://open.feishu.cn/app
- Create app → Enable **Bot** capability
- Permissions: add `im:message` (send) and `im:message.p2p_msg:readonly` (receive)
- Events: add `im.message.receive_v1` (receive messages)
  - Select **Long Connection** mode
- Get **App ID** and **App Secret**
- Publish the app

## 2. Configure
```json
{
  "channels": {
    "feishu": {
      "enabled": true,
      "appId": "cli_xxx",
      "appSecret": "xxx",
      "encryptKey": "",
      "verificationToken": "",
      "allowFrom": ["ou_YOUR_OPEN_ID"]
    }
  }
}
```

## 3. Run
```bash
crabclaw gateway
```

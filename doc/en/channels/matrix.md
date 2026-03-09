# Matrix (EN)

<p align="center">
  <a href="../../en/channels/matrix.md"><strong>English</strong></a> | <a href="../../zh-CN/channels/matrix.md"><strong>中文</strong></a>
</p>

## 0. Install Matrix extras
```bash
pip install crabclaw-ai[matrix]
```

## 1. Account
- Create or reuse a Matrix account on your homeserver (e.g. `matrix.org`)
- Confirm login with Element

## 2. Credentials
- `userId` (e.g. `@crabclaw:matrix.org`)
- `accessToken`
- `deviceId` (recommended to restore session)

## 3. Configure
```json
{
  "channels": {
    "matrix": {
      "enabled": true,
      "homeserver": "https://matrix.org",
      "userId": "@crabclaw:matrix.org",
      "accessToken": "syt_xxx",
      "deviceId": "crabclaw01",
      "e2eeEnabled": true,
      "allowFrom": ["@your_user:matrix.org"],
      "groupPolicy": "open",
      "groupAllowFrom": [],
      "allowRoomMentions": false,
      "maxMediaBytes": 20971520
    }
  }
}
```

## 4. Run
```bash
crabclaw gateway
```

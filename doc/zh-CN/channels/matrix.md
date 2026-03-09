# Matrix（中文）

<p align="center">
  <a href="../../en/channels/matrix.md"><strong>English</strong></a> | <a href="../../zh-CN/channels/matrix.md"><strong>中文</strong></a>
</p>

## 0. 安装 Matrix 依赖
```bash
pip install crabclaw-ai[matrix]
```

## 1. 账号
- 在你的 homeserver（如 `matrix.org`）创建或复用一个账号
- 使用 Element 客户端确认可登录

## 2. 凭证
- `userId`（例：`@crabclaw:matrix.org`）
- `accessToken`
- `deviceId`（推荐设置，便于恢复会话）

## 3. 配置
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

## 4. 运行
```bash
crabclaw gateway
```

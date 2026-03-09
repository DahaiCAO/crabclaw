# 飞书（中文）

<p align="center">
  <a href="../../en/channels/feishu.md"><strong>English</strong></a> | <a href="../../zh-CN/channels/feishu.md"><strong>中文</strong></a>
</p>

使用 **长连接 WebSocket**（无需公网 IP）。

## 1. 创建飞书 Bot
- 访问 https://open.feishu.cn/app
- 创建应用 → 开启 **Bot** 能力
- 权限：添加 `im:message`（发送）与 `im:message.p2p_msg:readonly`（接收）
- 事件：添加 `im.message.receive_v1`（接收消息）
  - 选择 **长连接** 模式
- 获取 **App ID** 与 **App Secret**
- 发布应用

## 2. 配置
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

## 3. 运行
```bash
crabclaw gateway
```

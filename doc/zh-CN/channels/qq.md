# QQ（中文）

<p align="center">
  <a href="../../en/channels/qq.md"><strong>English</strong></a> | <a href="../../zh-CN/channels/qq.md"><strong>中文</strong></a>
</p>

使用 **botpy SDK** 的 WebSocket。当前仅支持单聊。

## 1. 注册与创建
- 访问 https://q.qq.com 注册为开发者
- 创建机器人应用
- 复制 **AppID** 与 **AppSecret**

## 2. 沙箱配置
- 在机器人控制台进入 **沙箱配置**
- 在 **在消息列表配置** 中添加你自己的 QQ 号码
- 扫机器人二维码 → 打开资料页 → 点击“发消息”

## 3. 配置
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

## 4. 运行
```bash
crabclaw gateway
```

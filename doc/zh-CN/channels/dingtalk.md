# 钉钉（中文）

<p align="center">
  <a href="../../en/channels/dingtalk.md"><strong>English</strong></a> | <a href="../../zh-CN/channels/dingtalk.md"><strong>中文</strong></a>
</p>

使用 **Stream Mode**（无需公网 IP）。

## 1. 创建机器人
- 访问 https://open-dev.dingtalk.com/
- 创建应用 → 添加 **机器人** 能力
- 开启 **Stream Mode**
- 获取 **AppKey** 与 **AppSecret**
- 发布应用

## 2. 配置
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

## 3. 运行
```bash
crabclaw gateway
```

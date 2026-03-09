# WhatsApp（中文）

<p align="center">
  <a href="../../en/channels/whatsapp.md"><strong>English</strong></a> | <a href="../../zh-CN/channels/whatsapp.md"><strong>中文</strong></a>
</p>

需要 **Node.js ≥ 20**。

## 1. 设备绑定
```bash
crabclaw channels login
# 在 WhatsApp → 设置 → 已链接设备 中扫码
```

## 2. 配置
```json
{
  "channels": {
    "whatsapp": {
      "enabled": true,
      "allowFrom": ["+1234567890"]
    }
  }
}
```

## 3. 运行（两个终端）
```bash
# 终端 1
crabclaw channels login

# 终端 2
crabclaw gateway
```

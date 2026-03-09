# WhatsApp (EN)

<p align="center">
  <a href="../../en/channels/whatsapp.md"><strong>English</strong></a> | <a href="../../zh-CN/channels/whatsapp.md"><strong>中文</strong></a>
</p>

Requires **Node.js ≥ 20**.

## 1. Link device
```bash
crabclaw channels login
# Scan QR in WhatsApp → Settings → Linked Devices
```

## 2. Configure
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

## 3. Run (two terminals)
```bash
# Terminal 1
crabclaw channels login

# Terminal 2
crabclaw gateway
```

# Email（中文）

<p align="center">
  <a href="../../en/channels/email.md"><strong>English</strong></a> | <a href="../../zh-CN/channels/email.md"><strong>中文</strong></a>
</p>

为 crabclaw 准备一个独立邮箱账号。使用 IMAP 轮询收件，SMTP 发送回复。

## 1. 凭证（Gmail 示例）
- 创建独立 Gmail 账号
- 开启两步验证 → 创建 **App Password**
- IMAP 与 SMTP 均使用该 App Password

## 2. 配置
```json
{
  "channels": {
    "email": {
      "enabled": true,
      "consentGranted": true,
      "imapHost": "imap.gmail.com",
      "imapPort": 993,
      "imapUsername": "my-crabclaw@gmail.com",
      "imapPassword": "your-app-password",
      "smtpHost": "smtp.gmail.com",
      "smtpPort": 587,
      "smtpUsername": "my-crabclaw@gmail.com",
      "smtpPassword": "your-app-password",
      "fromAddress": "my-crabclaw@gmail.com",
      "allowFrom": ["your-real-email@gmail.com"]
    }
  }
}
```

## 3. 运行
```bash
crabclaw gateway
```

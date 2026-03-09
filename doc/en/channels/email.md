# Email (EN)

<p align="center">
  <a href="../../en/channels/email.md"><strong>English</strong></a> | <a href="../../zh-CN/channels/email.md"><strong>中文</strong></a>
</p>

Give crabclaw its own email account. It polls IMAP and replies via SMTP.

## 1. Credentials (Gmail example)
- Create a dedicated Gmail account
- Enable 2-Step Verification → create **App Password**
- Use this password for both IMAP and SMTP

## 2. Configure
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

## 3. Run
```bash
crabclaw gateway
```

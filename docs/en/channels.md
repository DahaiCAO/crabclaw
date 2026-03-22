# Multi-Channel and Identity Mapping

## Supported Channel Families

Crabclaw includes adapters for:
- Telegram
- Discord
- WhatsApp
- Feishu/Lark
- DingTalk
- Slack
- Email
- Matrix
- WeCom
- Mochat

## Enable a Channel

Set in `~/.crabclaw/config.json`:

```json
{
  "channels": {
    "telegram": {
      "enabled": true,
      "token": "xxx",
      "allowFrom": ["123456789"]
    }
  }
}
```

## `allowFrom` Behavior

- `allowFrom: []` => deny all.
- `allowFrom: ["*"]` => allow all.
- `allowFrom: ["id1", "id2"]` => allow only listed senders.

## User-Scoped Channel Config

Current design stores account config per user:
- `workspace/portfolios/<user_id>/channels/<channel>.json`

Dashboard Channels page can:
- add/delete user channel configs,
- maintain identity mappings.

## Identity Mapping

Mapping model:
- `(channel, external_id) -> user_id`

This powers:
- inbound user scope resolution,
- outbound multi-channel fanout,
- cross-end synchronized display.

## Fanout and Loop Protection

- fanout excludes source endpoint when possible,
- inbound echo is filtered by recent outbound fingerprint,
- dashboard suppresses duplicates by `event_id`.

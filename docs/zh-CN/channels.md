# 多通道与身份映射

## 支持的通道类型

当前仓库已集成：
- Telegram
- Discord
- WhatsApp
- 飞书/Lark
- 钉钉
- Slack
- Email
- Matrix
- 企业微信（WeCom）
- Mochat

## 启用通道

在 `~/.crabclaw/config.json` 中配置：

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

## `allowFrom` 当前行为

- `allowFrom: []`：拒绝所有来源。
- `allowFrom: ["*"]`：允许所有来源。
- `allowFrom: ["id1","id2"]`：仅允许白名单用户。

## 用户级通道配置

当前设计将账号配置存储在用户 portfolio：
- `workspace/portfolios/<user_id>/channels/<channel>.json`

Dashboard 的 Channels 页面可直接：
- 新增/删除用户通道配置；
- 管理身份映射。

## 身份映射模型

- `(channel, external_id) -> user_id`

作用：
- 入站消息归属用户域；
- 出站消息按用户进行多通道扇出；
- 多端同步展示。

## 扇出与回环保护

- 扇出时优先跳过来源端点；
- 入站回声由近期 outbound 指纹过滤；
- Dashboard 以 `event_id` 去重渲染。

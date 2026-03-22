# Crabclaw Glossary（术语表）

This glossary is the canonical terminology reference for both English and Chinese docs.

## Core Terms

| English | 中文 | Definition |
|---|---|---|
| Agent OS | 智能体操作系统 | Runtime platform for cognition, perception, action, memory, and multi-channel interaction. |
| HAOS | 类人智能体操作系统 | Human-like architecture used by Crabclaw for layered cognition and behavior loops. |
| Sapiens Core | Sapiens 认知核心 | Cognitive core that consumes stimuli and emits decisions/actions. |
| MessageBus | 消息总线 | Queue-based channel for inbound/outbound runtime messages. |
| BroadcastManager | 广播管理器 | User-scoped publish/subscribe channel for synchronized event delivery. |
| User Scope (`user_scope`) | 用户域 | Isolation boundary for session, memory, and event routing. |
| Identity Mapping | 身份映射 | Mapping from `(channel, external_id)` to `user_id`. |
| Portfolio | 用户档案目录 | User-owned workspace subtree storing memory/history/channel config. |
| Fanout | 多通道扇出 | Send one agent reply to multiple mapped channel endpoints. |
| Loop Guard | 回环保护 | Filtering mechanism to prevent self-echo and cyclical re-processing. |
| Event ID (`event_id`) | 事件ID | Stable identifier used for de-duplication and observability. |
| Request ID (`request_id`) | 请求ID | Correlation identifier linking one request to downstream events/replies. |
| Inbound Message | 入站消息 | Message entering runtime from channel or gateway. |
| Outbound Message | 出站消息 | Message emitted by runtime to channels. |
| Agent Reply | 智能体回复 | User-facing reply event published to dashboard and channels. |
| Channel Config | 通道配置 | Per-channel account/runtime parameters, now user-scoped. |
| `allowFrom` | 来源白名单 | Channel sender allowlist; empty list now means deny all. |
| Dashboard | 仪表盘 | Web UI + WS client for chat, channels, and user operations. |
| Gateway | 网关 | HTTP ingress endpoint for external message injection. |
| E2E Validation | 端到端验证 | Scripted runtime check for consistency, de-dup, and loop safety. |

## Recommended Wording Rules

- Use “user scope” for isolation context; avoid mixing with “session id”.
- Use “identity mapping” for external-to-internal identity binding.
- Use “fanout” only for one-to-many outbound delivery.
- Use “event_id/request_id” as fixed technical terms without translation in code snippets.

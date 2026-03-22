# Crabclaw Architecture (Current)

## 1. Business Scenarios

Crabclaw is designed for:
- personal AI companion with continuous cognition,
- multi-channel customer/personal assistant operations,
- one-user-many-endpoint synchronization,
- secure multi-tenant local deployment.

Typical scenario:
1. User sends message from Feishu or Telegram.
2. Message is mapped to unified `user_id`.
3. Sapiens generates reply in user scope.
4. Reply is faned out to mapped channels and synchronized to dashboard.

## 2. Layered Architecture

```mermaid
flowchart TB
  subgraph L1[Access Layer]
    CH[Channels]
    GW[Gateway HTTP]
    DB[Dashboard HTTP/WS]
  end

  subgraph L2[Messaging Layer]
    MB[MessageBus]
    BM[BroadcastManager]
  end

  subgraph L3[Cognitive Layer]
    IO[IOProcessor]
    SA[Sapiens]
  end

  subgraph L4[Identity and Storage]
    UM[UserManager]
    SM[SessionManager]
    MS[MemoryStore]
    PF[Portfolio Files]
  end

  CH --> MB
  GW --> MB
  MB --> BM
  BM --> IO
  IO --> SA
  SA --> IO
  IO --> MB
  UM --> BM
  UM --> IO
  SM --> PF
  MS --> PF
```

## 3. Key Runtime Paths

### 3.1 Inbound Path

```mermaid
sequenceDiagram
  participant C as Channel/Gateway
  participant B as MessageBus
  participant S as Scheduler
  participant M as BroadcastManager
  participant I as IOProcessor
  participant P as Sapiens

  C->>B: publish_inbound(InboundMessage)
  B->>S: event inbound
  S->>M: publish(scope=user_id, inbound_message[event_id])
  M->>I: user_message
  I->>P: stimulus
```

### 3.2 Outbound/Fanout Path

```mermaid
sequenceDiagram
  participant P as Sapiens
  participant I as IOProcessor
  participant B as MessageBus
  participant S as Scheduler
  participant M as BroadcastManager
  participant C as Channels

  P->>I: Action(send_message)
  I->>I: loop-guard + target collection
  I->>B: publish_outbound(OutboundMessage[event_id])
  B->>S: event outbound
  S->>M: outbound_message + agent_reply
  B->>C: consume_outbound and send
```

## 4. Identity and Isolation Model

- Identity mapping: `identities/mappings.json`
- User profile: `users/<user_id>.json`
- User portfolio:
  - `portfolios/<user_id>/memory/`
  - `portfolios/<user_id>/history/`
  - `portfolios/<user_id>/channels/`

Isolation principles:
- session uses `user_scope`,
- memory uses `user_scope`,
- channel account config is user-owned,
- dashboard/gateway events are scoped by `user_id`.

## 5. Reliability Controls

- loop protection based on recent outbound fingerprint,
- duplicate suppression on dashboard by `event_id`,
- stable event identity across endpoints,
- request correlation by `request_id`.

## 6. Design Delta vs Legacy

- request-response only → scoped pub/sub + fanout,
- global chat context → user-isolated state,
- weak observability → event-level observability and E2E check tooling.

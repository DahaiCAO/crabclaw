# Developer Guide (Current Design)

## 1. Dev Environment

```bash
git clone https://github.com/DahaiCAO/crabclaw.git
cd crabclaw
python -m venv .venv
. .venv/bin/activate
pip install -U pip
pip install -e .
```

Frontend bridge:

```bash
cd bridge
npm install
npm run build
```

## 2. Project Structure

- `crabclaw/agent`: scheduler, IO loop, cognition runtime.
- `crabclaw/bus`: queue and broadcast primitives.
- `crabclaw/channels`: channel adapters.
- `crabclaw/dashboard`: dashboard server and static app.
- `crabclaw/user`: user, identity mapping, account lifecycle.
- `tests`: multi-user and runtime behavior tests.

## 3. Design Rules for New Features

1. Always preserve `user_scope` semantics.
2. New outbound paths must carry `request_id` and `event_id`.
3. Avoid loopback by checking source channel and recent fingerprints.
4. Keep dashboard events idempotent (de-dup friendly payloads).

## 4. Adding a New Channel

1. Create adapter in `crabclaw/channels`.
2. Implement receive path with `_handle_message`.
3. Ensure message metadata can carry `user_id` and `request_id`.
4. Implement send path in `send`.
5. Add config schema fields in `config/schema.py`.
6. Verify dashboard Channels page parameter rendering.

## 5. Identity and Fanout Integration

- Use `UserManager.map_identity` for external identity bindings.
- Resolve user by:
  - `resolve_user_by_identity(channel, sender_id)`,
  - fallback `resolve_user_by_identity(channel, chat_id)`.
- Fanout targets are selected from user mappings, excluding source endpoint.

## 6. Testing Strategy

Run:

```bash
ruff check crabclaw tests scripts
python -m pytest -q tests/test_multi_user_isolation.py
node --check crabclaw/dashboard/static/app.js
```

For runtime observability:

```bash
python scripts/e2e_multichannel_sync_check.py --help
```

## 7. Documentation Requirements

For architecture-impacting changes:
- update `README.md` and `README.zh-CN.md`,
- update docs in both `docs/en` and `docs/zh-CN`,
- keep examples aligned with actual CLI and API behavior.

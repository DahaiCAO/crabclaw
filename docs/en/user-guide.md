# User Guide (Current Design)

## 1. Setup

```bash
crabclaw onboard
```

Then edit `~/.crabclaw/config.json`:
- set provider key(s),
- set default model,
- enable channel(s) if needed.

## 2. Service Startup

```bash
crabclaw gateway
```

Optional dashboard:

```bash
crabclaw dashboard
```

Dashboard URL:
- `http://127.0.0.1:18791`

## 3. Account and Login

- Default admin account is created on first bootstrap:
  - username: `admin`
  - password: `admin2891`
- Dashboard auth is token-based:
  - login with `/api/login`,
  - session restore via `/api/me`.

## 4. Multi-Channel Usage

1. Enable channel in config (`channels.<name>.enabled=true`).
2. Configure channel credentials.
3. Use Channels page in dashboard:
   - add user-specific channel account configs,
   - maintain identity mappings.

Identity mapping example:
- `channel=feishu`, `external_id=ou_xxx` -> current user.

## 5. Multi-End Synchronized Display

Expected behavior:
- inbound from one mapped channel appears in dashboard for same user scope,
- outbound reply appears consistently on all connected clients,
- duplicate events are suppressed.

## 6. Account Lifecycle

From dashboard user menu:
- Switch Account: clear local auth and jump to login.
- Logout: server logout + local state cleanup.
- Delete Account: remove user profile and isolated portfolio.

## 7. Security Tips

- Use strict `allowFrom` list in production.
- `allowFrom: []` denies all by default.
- Use `allowFrom: ["*"]` only if intentionally open.
- Set `tools.restrictToWorkspace=true` for safer tool operation.

## 8. Observability Validation

Run E2E check:

```bash
python scripts/e2e_multichannel_sync_check.py \
  --dashboard-http http://127.0.0.1:18791 \
  --dashboard-ws ws://127.0.0.1:18792/ws \
  --gateway-http http://127.0.0.1:18790 \
  --username admin \
  --password admin2891
```

Pass criteria:
- both clients receive inbound and outbound,
- no duplicate events,
- consistent outbound `event_id`.

# Security Policy

## Reporting a Vulnerability

If you discover a security issue in Crabclaw:

1. Do not open a public issue for exploitable details.
2. Create a GitHub Security Advisory, or contact maintainers directly.
3. Include:
   - impact,
   - affected version/commit,
   - reproducible steps,
   - suggested mitigation (if available).

## Current Security Model

### Authentication and Session

- Dashboard uses token-based auth (`/api/login` + `/api/me`).
- User identity is carried by token subject (`user_id`).
- Account lifecycle endpoints:
  - `/api/logout`
  - `/api/delete-account`

### Channel Access Control

- `channels.*.allowFrom` is explicit allowlist.
- In current design, `allowFrom: []` means deny all.
- To allow all senders intentionally, use `allowFrom: ["*"]`.

### Multi-User Isolation

- User profile: `workspace/users/*.json`
- User portfolio: `workspace/portfolios/<user_id>/...`
- User-scoped session and memory (`user_scope`).
- User-scoped channel config and identity mapping.

### Tool and Filesystem Safety

- `tools.restrictToWorkspace: true` is strongly recommended in production.
- Keep the runtime user non-root and least-privileged.
- Review logs and audit events regularly.

### Network and Integration Safety

- Prefer HTTPS endpoints for provider/tool integrations.
- Keep bridge ports and dashboard ports protected by host/network policy.
- Do not expose internal endpoints publicly without reverse proxy/auth policy.

## Operational Best Practices

### Secret Management

- Never commit API keys/tokens.
- Store secrets in `~/.crabclaw/config.json` with strict permissions.
- Use separate keys for development and production.
- Rotate keys periodically.

### Dependency Security

- Keep Python and Node dependencies updated.
- Run dependency audits regularly:

```bash
pip install pip-audit
pip-audit
```

```bash
cd bridge
npm audit
```

### Deployment Hardening

- Run in container/VM for production.
- Use dedicated service account.
- Restrict filesystem permissions for `~/.crabclaw`.
- Monitor logs and set alerting for abnormal traffic/usage.

## Incident Response Checklist

1. Revoke compromised credentials immediately.
2. Preserve and review logs.
3. Rotate keys/tokens and force re-authentication.
4. Patch/upgrade affected environment.
5. Publish internal postmortem and mitigation status.

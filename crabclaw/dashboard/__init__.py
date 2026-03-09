"""Simple web dashboard for observability.

The dashboard is intentionally lightweight:
- HTTP server serves a static UI (no external dependencies).
- WebSocket server streams JSON events (audit logs, state snapshots, reflection outputs).
"""


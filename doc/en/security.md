# Security (EN)

<p align="center">
  <a href="../en/security.md"><strong>English</strong></a> | <a href="../zh-CN/security.md"><strong>中文</strong></a>
</p>

For production deployments:
- Set `"restrictToWorkspace": true` to sandbox all tools.
- Channel access defaults may vary by version; to allow all senders, set `"allowFrom": ["*"]`.

Options:
| Option | Default | Description |
|--------|---------|-------------|
| `tools.restrictToWorkspace` | `false` | Restrict file and shell tools to workspace dir |
| `tools.exec.pathAppend` | `""` | Extra PATH entries when running commands |
| `channels.*.allowFrom` | `[]` | Whitelist of user IDs; `["*"]` allows everyone |

Full details: see [README.md](../../README.md#L863).

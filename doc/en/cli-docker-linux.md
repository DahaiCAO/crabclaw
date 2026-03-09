# CLI, Docker & Linux Service (EN)

<p align="center">
  <a href="../en/cli-docker-linux.md"><strong>English</strong></a> | <a href="../zh-CN/cli-docker-linux.md"><strong>中文</strong></a>
</p>

## CLI
Commands:
| Command | Description |
|---------|-------------|
| `crabclaw onboard` | Initialize config & workspace |
| `crabclaw agent` | Interactive chat |
| `crabclaw agent -m "..."` | Single message chat |
| `crabclaw gateway` | Start gateway |
| `crabclaw status` | Show status |

## Docker
```bash
docker compose run --rm crabclaw-cli onboard
vim ~/.crabclaw/config.json
docker compose up -d crabclaw-gateway
```

## Linux Service
Systemd user service example:
```ini
[Unit]
Description=crabclaw Gateway
After=network.target

[Service]
Type=simple
ExecStart=%h/.local/bin/crabclaw gateway
Restart=always
RestartSec=10
NoNewPrivileges=yes
ProtectSystem=strict
ReadWritePaths=%h

[Install]
WantedBy=default.target
```

More details: [README.md](../../README.md#L876).

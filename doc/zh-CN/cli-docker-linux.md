# CLI、Docker 与 Linux 服务（中文）

<p align="center">
  <a href="../en/cli-docker-linux.md"><strong>English</strong></a> | <a href="../zh-CN/cli-docker-linux.md"><strong>中文</strong></a>
</p>

## CLI
常用命令：
| 命令 | 说明 |
|------|-----|
| `crabclaw onboard` | 初始化配置与 workspace |
| `crabclaw agent` | 交互式聊天 |
| `crabclaw agent -m "..."` | 单次对话 |
| `crabclaw gateway` | 启动网关 |
| `crabclaw status` | 查看状态 |

## Docker
```bash
docker compose run --rm crabclaw-cli onboard
vim ~/.crabclaw/config.json
docker compose up -d crabclaw-gateway
```

## Linux 服务
Systemd 用户服务示例：
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

更多细节见根目录 [README.md](../../README.md)。

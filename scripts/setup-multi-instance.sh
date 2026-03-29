#!/bin/bash
# Crabclaw 多实例配置脚本
# 用法: ./setup-multi-instance.sh [实例名称] [端口]

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 默认配置
INSTANCE_NAME=${1:-"telegram"}
BASE_PORT=${2:-18790}

# 计算端口
GATEWAY_PORT=$BASE_PORT
DASHBOARD_HTTP_PORT=$((BASE_PORT + 1))
DASHBOARD_WS_PORT=$((BASE_PORT + 2))

# 实例目录
INSTANCE_DIR="$HOME/.crabclaw-$INSTANCE_NAME"
CONFIG_FILE="$INSTANCE_DIR/config.json"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Crabclaw 多实例配置工具${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 检查 crabclaw 是否安装
if ! command -v crabclaw &> /dev/null; then
    echo -e "${RED}错误: crabclaw 未安装${NC}"
    echo "请先安装 crabclaw: pip install crabclaw"
    exit 1
fi

echo -e "${GREEN}✓${NC} 检查 crabclaw 安装"

# 创建实例目录
echo ""
echo -e "${YELLOW}正在创建实例目录...${NC}"
mkdir -p "$INSTANCE_DIR"
echo -e "${GREEN}✓${NC} 实例目录: $INSTANCE_DIR"

# 检查配置是否已存在
if [ -f "$CONFIG_FILE" ]; then
    echo ""
    echo -e "${YELLOW}警告: 配置文件已存在${NC}"
    read -p "是否覆盖现有配置? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "操作已取消"
        exit 0
    fi
fi

# 创建基础配置
echo ""
echo -e "${YELLOW}正在生成配置文件...${NC}"

cat > "$CONFIG_FILE" << EOF
{
  "language": "zh",
  "providers": {
    "openrouter": {
      "apiKey": "",
      "model": "anthropic/claude-3-5-sonnet-20241022"
    }
  },
  "agents": {
    "defaults": {
      "model": "anthropic/claude-3-5-sonnet-20241022",
      "provider": "openrouter",
      "maxToolIterations": 10,
      "contextWindowTokens": 8000,
      "workspace": "$INSTANCE_DIR/workspace"
    }
  },
  "tools": {
    "exec": {
      "timeout": 60,
      "pathAppend": ""
    },
    "restrictToWorkspace": true,
    "web": {
      "search": {
        "enabled": false
      },
      "proxy": ""
    },
    "mcpServers": []
  },
  "channels": {
    "telegram": {
      "enabled": false,
      "token": ""
    },
    "discord": {
      "enabled": false,
      "token": ""
    },
    "slack": {
      "enabled": false,
      "botToken": "",
      "appToken": "",
      "signingSecret": ""
    },
    "whatsapp": {
      "enabled": false,
      "bridgeUrl": "ws://localhost:3001"
    },
    "feishu": {
      "enabled": false,
      "appId": "",
      "appSecret": ""
    },
    "dingtalk": {
      "enabled": false,
      "clientId": "",
      "clientSecret": ""
    },
    "email": {
      "enabled": false,
      "imapHost": "",
      "imapPort": 993,
      "imapUsername": "",
      "imapPassword": "",
      "smtpHost": "",
      "smtpPort": 587,
      "checkInterval": 60,
      "autoReplyEnabled": false
    }
  },
  "gateway": {
    "enabled": true,
    "port": $GATEWAY_PORT,
    "heartbeat": {
      "enabled": true,
      "intervalS": 1800
    }
  },
  "dashboard": {
    "enabled": true,
    "httpPort": $DASHBOARD_HTTP_PORT,
    "wsPort": $DASHBOARD_WS_PORT,
    "host": "127.0.0.1"
  },
  "workspace_path": "$INSTANCE_DIR/workspace"
}
EOF

echo -e "${GREEN}✓${NC} 配置文件已创建: $CONFIG_FILE"

# 创建工作空间目录
mkdir -p "$INSTANCE_DIR/workspace"
echo -e "${GREEN}✓${NC} 工作空间目录已创建"

# 设置权限
chmod 700 "$INSTANCE_DIR"
chmod 600 "$CONFIG_FILE"
echo -e "${GREEN}✓${NC} 目录权限已设置"

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}  实例 '$INSTANCE_NAME' 配置完成!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "实例信息:"
echo "  名称: $INSTANCE_NAME"
echo "  目录: $INSTANCE_DIR"
echo "  配置: $CONFIG_FILE"
echo ""
echo "端口配置:"
echo "  Gateway:     $GATEWAY_PORT"
echo "  Dashboard HTTP:  $DASHBOARD_HTTP_PORT"
echo "  Dashboard WS:    $DASHBOARD_WS_PORT"
echo ""
echo "下一步:"
echo ""
echo "1. 编辑配置文件添加 API 密钥:"
echo -e "   ${YELLOW}crabclaw config edit --config $CONFIG_FILE${NC}"
echo ""
echo "2. 或使用交互式配置向导:"
echo -e "   ${YELLOW}crabclaw onboard --config $CONFIG_FILE${NC}"
echo ""
echo "3. 启动实例:"
echo -e "   ${YELLOW}crabclaw gateway --config $CONFIG_FILE${NC}"
echo ""
echo "4. 启动 Dashboard:"
echo -e "   ${YELLOW}crabclaw dashboard --config $CONFIG_FILE${NC}"
echo ""
echo "5. 查看配置:"
echo -e "   ${YELLOW}crabclaw config show --config $CONFIG_FILE${NC}"
echo ""

# 创建启动脚本
START_SCRIPT="$INSTANCE_DIR/start.sh"
cat > "$START_SCRIPT" << EOF
#!/bin/bash
# 启动 $INSTANCE_NAME 实例

echo "Starting Crabclaw instance: $INSTANCE_NAME"
echo "Config: $CONFIG_FILE"
echo "Ports: Gateway=$GATEWAY_PORT, Dashboard HTTP=$DASHBOARD_HTTP_PORT, Dashboard WS=$DASHBOARD_WS_PORT"
echo ""

crabclaw gateway --config "$CONFIG_FILE" --port $GATEWAY_PORT
EOF

chmod +x "$START_SCRIPT"
echo -e "${GREEN}✓${NC} 启动脚本已创建: $START_SCRIPT"

# 创建 systemd 服务文件（可选）
SYSTEMD_SERVICE="$INSTANCE_DIR/crabclaw-$INSTANCE_NAME.service"
cat > "$SYSTEMD_SERVICE" << EOF
[Unit]
Description=Crabclaw $INSTANCE_NAME Instance
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTANCE_DIR
ExecStart=$(which crabclaw) gateway --config $CONFIG_FILE --port $GATEWAY_PORT
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

echo -e "${GREEN}✓${NC} Systemd 服务文件已创建: $SYSTEMD_SERVICE"
echo ""
echo "安装 systemd 服务:"
echo -e "   ${YELLOW}sudo cp $SYSTEMD_SERVICE /etc/systemd/system/${NC}"
echo -e "   ${YELLOW}sudo systemctl daemon-reload${NC}"
echo -e "   ${YELLOW}sudo systemctl enable crabclaw-$INSTANCE_NAME${NC}"
echo -e "   ${YELLOW}sudo systemctl start crabclaw-$INSTANCE_NAME${NC}"
echo ""

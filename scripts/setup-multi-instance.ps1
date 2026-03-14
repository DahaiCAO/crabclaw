# Crabclaw 多实例配置脚本 (Windows PowerShell)
# 用法: .\setup-multi-instance.ps1 [-InstanceName "telegram"] [-BasePort 18790]

param(
    [string]$InstanceName = "telegram",
    [int]$BasePort = 18790
)

# 颜色定义
$Red = "Red"
$Green = "Green"
$Yellow = "Yellow"
$Blue = "Cyan"

# 计算端口
$GatewayPort = $BasePort
$DashboardHttpPort = $BasePort + 1
$DashboardWsPort = $BasePort + 2

# 实例目录
$InstanceDir = "$env:USERPROFILE\.crabclaw-$InstanceName"
$ConfigFile = "$InstanceDir\config.json"

Write-Host "========================================" -ForegroundColor $Blue
Write-Host "  Crabclaw 多实例配置工具" -ForegroundColor $Blue
Write-Host "========================================" -ForegroundColor $Blue
Write-Host ""

# 检查 crabclaw 是否安装
try {
    $null = Get-Command crabclaw -ErrorAction Stop
    Write-Host "✓ 检查 crabclaw 安装" -ForegroundColor $Green
} catch {
    Write-Host "错误: crabclaw 未安装" -ForegroundColor $Red
    Write-Host "请先安装 crabclaw: pip install crabclaw"
    exit 1
}

# 创建实例目录
Write-Host ""
Write-Host "正在创建实例目录..." -ForegroundColor $Yellow
New-Item -ItemType Directory -Force -Path $InstanceDir | Out-Null
Write-Host "✓ 实例目录: $InstanceDir" -ForegroundColor $Green

# 检查配置是否已存在
if (Test-Path $ConfigFile) {
    Write-Host ""
    Write-Host "警告: 配置文件已存在" -ForegroundColor $Yellow
    $reply = Read-Host "是否覆盖现有配置? (y/N)"
    if ($reply -notmatch "^[Yy]$") {
        Write-Host "操作已取消"
        exit 0
    }
}

# 创建基础配置
Write-Host ""
Write-Host "正在生成配置文件..." -ForegroundColor $Yellow

$configContent = @"
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
      "contextWindowTokens": 8000
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
    "port": $GatewayPort,
    "heartbeat": {
      "enabled": true,
      "intervalS": 1800
    }
  },
  "dashboard": {
    "enabled": true,
    "httpPort": $DashboardHttpPort,
    "wsPort": $DashboardWsPort,
    "host": "127.0.0.1"
  },
  "workspacePath": "$($InstanceDir.Replace('\', '\\'))\\workspace"
}
"@

$configContent | Out-File -FilePath $ConfigFile -Encoding UTF8
Write-Host "✓ 配置文件已创建: $ConfigFile" -ForegroundColor $Green

# 创建工作空间目录
New-Item -ItemType Directory -Force -Path "$InstanceDir\workspace" | Out-Null
Write-Host "✓ 工作空间目录已创建" -ForegroundColor $Green

Write-Host ""
Write-Host "========================================" -ForegroundColor $Blue
Write-Host "  实例 '$InstanceName' 配置完成!" -ForegroundColor $Green
Write-Host "========================================" -ForegroundColor $Blue
Write-Host ""
Write-Host "实例信息:"
Write-Host "  名称: $InstanceName"
Write-Host "  目录: $InstanceDir"
Write-Host "  配置: $ConfigFile"
Write-Host ""
Write-Host "端口配置:"
Write-Host "  Gateway:        $GatewayPort"
Write-Host "  Dashboard HTTP: $DashboardHttpPort"
Write-Host "  Dashboard WS:   $DashboardWsPort"
Write-Host ""
Write-Host "下一步:"
Write-Host ""
Write-Host "1. 编辑配置文件添加 API 密钥:"
Write-Host "   crabclaw config edit --config $ConfigFile" -ForegroundColor $Yellow
Write-Host ""
Write-Host "2. 或使用交互式配置向导:"
Write-Host "   crabclaw onboard --config $ConfigFile" -ForegroundColor $Yellow
Write-Host ""
Write-Host "3. 启动实例:"
Write-Host "   crabclaw gateway --config $ConfigFile" -ForegroundColor $Yellow
Write-Host ""
Write-Host "4. 启动 Dashboard:"
Write-Host "   crabclaw dashboard --config $ConfigFile" -ForegroundColor $Yellow
Write-Host ""
Write-Host "5. 查看配置:"
Write-Host "   crabclaw config show --config $ConfigFile" -ForegroundColor $Yellow
Write-Host ""

# 创建启动脚本
$StartScript = "$InstanceDir\start.bat"
$startContent = @"
@echo off
REM 启动 $InstanceName 实例

echo Starting Crabclaw instance: $InstanceName
echo Config: $ConfigFile
echo Ports: Gateway=$GatewayPort, Dashboard HTTP=$DashboardHttpPort, Dashboard WS=$DashboardWsPort
echo.

crabclaw gateway --config "$ConfigFile" --port $GatewayPort
"@

$startContent | Out-File -FilePath $StartScript -Encoding UTF8
Write-Host "✓ 启动脚本已创建: $StartScript" -ForegroundColor $Green

# 创建 PowerShell 启动脚本
$StartPsScript = "$InstanceDir\start.ps1"
$startPsContent = @"
# 启动 $InstanceName 实例

Write-Host "Starting Crabclaw instance: $InstanceName" -ForegroundColor Cyan
Write-Host "Config: $ConfigFile"
Write-Host "Ports: Gateway=$GatewayPort, Dashboard HTTP=$DashboardHttpPort, Dashboard WS=$DashboardWsPort"
Write-Host ""

crabclaw gateway --config "$ConfigFile" --port $GatewayPort
"@

$startPsContent | Out-File -FilePath $StartPsScript -Encoding UTF8
Write-Host "✓ PowerShell 启动脚本已创建: $StartPsScript" -ForegroundColor $Green

Write-Host ""
Write-Host "快速启动命令:"
Write-Host "   .\start.ps1" -ForegroundColor $Yellow
Write-Host "   或" -ForegroundColor $Yellow
Write-Host "   start.bat" -ForegroundColor $Yellow
Write-Host ""

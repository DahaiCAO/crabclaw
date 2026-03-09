# 安装与快速开始（中文）

<p align="center">
  <a href="../en/install-quick-start.md"><strong>English</strong></a> | <a href="../zh-CN/install-quick-start.md"><strong>中文</strong></a>
</p>

## 安装

从源码安装：
```bash
git clone https://github.com/DahaiCAO/crabclaw.git
cd crabclaw
pip install -e .
```

使用 uv：
```bash
uv tool install crabclaw-ai
```

从 PyPI 安装：
```bash
pip install crabclaw-ai
```

## 快速开始

在 `~/.crabclaw/config.json` 写入你的 API Key（推荐 OpenRouter）。

初始化：
```bash
crabclaw onboard
```

配置（合并到 `~/.crabclaw/config.json`）：
```json
{
  "providers": { "openrouter": { "apiKey": "sk-or-v1-xxx" } },
  "agents": { "defaults": { "model": "anthropic/claude-opus-4-5", "provider": "openrouter" } }
}
```

开始聊天：
```bash
crabclaw agent
```

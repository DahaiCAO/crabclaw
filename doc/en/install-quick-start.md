# Install & Quick Start (EN)

<p align="center">
  <a href="../en/install-quick-start.md"><strong>English</strong></a> | <a href="../zh-CN/install-quick-start.md"><strong>中文</strong></a>
</p>

## Install

Install from source:
```bash
git clone https://github.com/DahaiCAO/crabclaw.git
cd crabclaw
pip install -e .
```

Install with uv:
```bash
uv tool install crabclaw-ai
```

Install from PyPI:
```bash
pip install crabclaw-ai
```

## Quick Start

Set your API key in `~/.crabclaw/config.json` (OpenRouter recommended).

Initialize:
```bash
crabclaw onboard
```

Configure (merge parts into `~/.crabclaw/config.json`):
```json
{
  "providers": { "openrouter": { "apiKey": "sk-or-v1-xxx" } },
  "agents": { "defaults": { "model": "anthropic/claude-opus-4-5", "provider": "openrouter" } }
}
```

Chat:
```bash
crabclaw agent
```

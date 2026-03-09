# Configuration: Providers & MCP (EN)

<p align="center">
  <a href="../en/configuration-providers-mcp.md"><strong>English</strong></a> | <a href="../zh-CN/configuration-providers-mcp.md"><strong>中文</strong></a>
</p>

Config file: `~/.crabclaw/config.json`

## Providers

Recommended: `openrouter` with access to many models. Direct providers include `anthropic`, `openai`, `deepseek`, `moonshot`, `dashscope`, `zhipu`, and more. Custom OpenAI-compatible endpoints use `providers.custom`.

See provider examples and developer guide in [README.md](../../README.md#L639).

## MCP (Model Context Protocol)

Add MCP tool servers in config:
```json
{
  "tools": {
    "mcpServers": {
      "filesystem": { "command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path"] },
      "my-remote-mcp": { "url": "https://example.com/mcp/", "headers": { "Authorization": "Bearer xxxxx" } }
    }
  }
}
```

Supports Stdio and HTTP transports. Details: [README.md](../../README.md#L808).

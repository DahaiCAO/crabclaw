# 配置：Providers 与 MCP（中文）

<p align="center">
  <a href="../en/configuration-providers-mcp.md"><strong>English</strong></a> | <a href="../zh-CN/configuration-providers-mcp.md"><strong>中文</strong></a>
</p>

配置文件路径：`~/.crabclaw/config.json`

## Providers

推荐使用 `openrouter`（一个 key 访问多模型）。也支持 `anthropic`、`openai`、`deepseek`、`moonshot`、`dashscope`、`zhipu` 等直接连接。自定义 OpenAI 兼容端点使用 `providers.custom`。

完整示例与开发者指南见 [README.md](../../README.md)。

## MCP（Model Context Protocol）

在配置中添加 MCP 工具服务器：
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

支持 Stdio 与 HTTP 两种传输模式。详情见 [README.md](../../README.md)。

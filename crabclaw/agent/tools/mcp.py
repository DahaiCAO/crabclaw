"""MCP client: connects to MCP servers and wraps their tools as native nanobot tools with enhanced security."""

import asyncio
from contextlib import AsyncExitStack
from typing import Any

import httpx
from loguru import logger

from crabclaw.agent.tools.base import Tool
from crabclaw.agent.tools.registry import ToolRegistry
from crabclaw.agent.tools.mcp_secure import (
    MCPSecurityPolicy,
    MCPServerConfig,
    check_mcp_command_safety,
    MAX_TIMEOUT,
)
from crabclaw.utils.audit_logger import audit_log, AuditEventType


class MCPToolWrapper(Tool):
    """Wraps a single MCP server tool as a nanobot Tool with security controls."""

    def __init__(
        self,
        session,
        server_name: str,
        tool_def,
        tool_timeout: int = 30,
        max_calls_per_minute: int = 60,
    ):
        self._session = session
        self._original_name = tool_def.name
        self._name = f"mcp_{server_name}_{tool_def.name}"
        self._description = tool_def.description or tool_def.name
        self._parameters = tool_def.inputSchema or {"type": "object", "properties": {}}
        self._tool_timeout = min(tool_timeout, MAX_TIMEOUT)
        self._server_name = server_name
        
        # Rate limiting
        self._call_count = 0
        self._last_reset = asyncio.get_event_loop().time()
        self._max_calls_per_minute = max_calls_per_minute

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters(self) -> dict[str, Any]:
        return self._parameters

    async def execute(self, **kwargs: Any) -> str:
        from mcp import types
        
        # Check rate limit
        current_time = asyncio.get_event_loop().time()
        if current_time - self._last_reset >= 60:
            self._call_count = 0
            self._last_reset = current_time
        
        if self._call_count >= self._max_calls_per_minute:
            logger.warning(
                "MCP tool '{}' rate limit exceeded ({}/min)",
                self._name, self._max_calls_per_minute
            )
            audit_log(
                AuditEventType.RATE_LIMIT_HIT,
                action="mcp_tool_execute",
                resource=self._name,
                result="rate_limited",
            )
            return f"(MCP tool call rate limited: max {self._max_calls_per_minute} calls per minute)"
        
        self._call_count += 1
        
        # Log execution attempt
        audit_log(
            AuditEventType.COMMAND_EXECUTED,
            action="mcp_tool_execute",
            resource=self._name,
            details={"server": self._server_name, "tool": self._original_name},
        )
        
        try:
            result = await asyncio.wait_for(
                self._session.call_tool(self._original_name, arguments=kwargs),
                timeout=self._tool_timeout,
            )
        except asyncio.TimeoutError:
            logger.warning("MCP tool '{}' timed out after {}s", self._name, self._tool_timeout)
            audit_log(
                AuditEventType.SECURITY_VIOLATION,
                action="mcp_tool_timeout",
                resource=self._name,
                result="timeout",
                details={"timeout": self._tool_timeout},
            )
            return f"(MCP tool call timed out after {self._tool_timeout}s)"
        except Exception as e:
            logger.error("MCP tool '{}' execution error: {}", self._name, e)
            audit_log(
                AuditEventType.SECURITY_VIOLATION,
                action="mcp_tool_error",
                resource=self._name,
                result="error",
                details={"error": str(e)},
            )
            return f"(MCP tool call error: {e})"
        
        parts = []
        for block in result.content:
            if isinstance(block, types.TextContent):
                parts.append(block.text)
            else:
                parts.append(str(block))
        
        return "\n".join(parts) or "(no output)"


async def connect_mcp_servers(
    mcp_servers: dict, registry: ToolRegistry, stack: AsyncExitStack
) -> None:
    """Connect to configured MCP servers and register their tools with security validation."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    
    # Validate and sanitize configurations
    policy = MCPSecurityPolicy()
    
    try:
        validated_servers = policy.validate_server_list(mcp_servers)
    except ValueError as e:
        logger.error("MCP server validation failed: {}", e)
        audit_log(
            AuditEventType.SECURITY_VIOLATION,
            action="mcp_validation_failed",
            result="error",
            details={"error": str(e)},
        )
        return
    
    for name, cfg in validated_servers.items():
        if not cfg.enabled:
            logger.info("MCP server '{}': disabled, skipping", name)
            continue
        
        try:
            # Additional command safety check at runtime
            if cfg.command:
                is_safe, error_msg = check_mcp_command_safety(cfg.command, cfg.args or [])
                if not is_safe:
                    logger.error("MCP server '{}': unsafe command: {}", name, error_msg)
                    audit_log(
                        AuditEventType.SECURITY_VIOLATION,
                        action="mcp_unsafe_command",
                        resource=name,
                        result="blocked",
                        details={"error": error_msg},
                    )
                    continue
            
            if cfg.command:
                params = StdioServerParameters(
                    command=cfg.command, args=cfg.args or [], env=cfg.env or None
                )
                read, write = await stack.enter_async_context(stdio_client(params))
            elif cfg.url:
                from mcp.client.streamable_http import streamable_http_client
                
                # Create secure HTTP client with timeouts
                http_client = await stack.enter_async_context(
                    httpx.AsyncClient(
                        headers=cfg.headers or None,
                        follow_redirects=True,
                        timeout=httpx.Timeout(
                            connect=10.0,
                            read=cfg.tool_timeout,
                            write=10.0,
                            pool=5.0,
                        ),
                        limits=httpx.Limits(
                            max_connections=5,
                            max_keepalive_connections=2,
                        ),
                    )
                )
                read, write, _ = await stack.enter_async_context(
                    streamable_http_client(cfg.url, http_client=http_client)
                )
            else:
                logger.warning("MCP server '{}': no command or url configured, skipping", name)
                continue

            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()

            tools = await session.list_tools()
            registered_count = 0
            
            for tool_def in tools.tools:
                try:
                    wrapper = MCPToolWrapper(
                        session, name, tool_def, tool_timeout=cfg.tool_timeout
                    )
                    registry.register(wrapper)
                    registered_count += 1
                    logger.debug("MCP: registered tool '{}' from server '{}'", wrapper.name, name)
                except Exception as e:
                    logger.error(
                        "MCP: failed to register tool '{}' from server '{}': {}",
                        tool_def.name, name, e
                    )

            logger.info(
                "MCP server '{}': connected, {} tools registered",
                name, registered_count
            )
            
            audit_log(
                AuditEventType.AUTH_SUCCESS,
                action="mcp_server_connected",
                resource=name,
                result="success",
                details={"tools_registered": registered_count},
            )
            
        except Exception as e:
            logger.error("MCP server '{}': failed to connect: {}", name, e)
            audit_log(
                AuditEventType.SECURITY_VIOLATION,
                action="mcp_connection_failed",
                resource=name,
                result="error",
                details={"error": str(e)},
            )


def validate_mcp_config(config: dict[str, Any]) -> tuple[bool, list[str]]:
    """
    Validate MCP configuration without connecting.
    
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    policy = MCPSecurityPolicy()
    
    try:
        validated = policy.validate_server_list(config)
        
        # Check for disabled servers
        disabled = [name for name, cfg in validated.items() if not cfg.enabled]
        if disabled:
            logger.info(f"MCP servers disabled: {', '.join(disabled)}")
        
        return len(errors) == 0, errors
        
    except ValueError as e:
        errors.append(str(e))
        return False, errors


def get_mcp_stats() -> dict[str, Any]:
    """Get MCP connection statistics."""
    return {
        "allowed_commands": list(MCPSecurityPolicy.__dict__.get('ALLOWED_MCP_COMMANDS', set())),
        "max_timeout": MAX_TIMEOUT,
        "max_args": 50,
        "max_env_vars": 20,
    }

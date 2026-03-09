"""Secure MCP client configuration and validation."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from loguru import logger


# Allowed MCP commands (whitelist)
ALLOWED_MCP_COMMANDS = {
    'npx',
    'node',
    'python',
    'python3',
    'uv',
    'uvx',
    'deno',
    'bun',
}

# Blocked command patterns
BLOCKED_COMMAND_PATTERNS = [
    r'[;&|]',
    r'`[^`]*`',
    r'\$\(.*?\)',
    r'<\s*\(.*?\)',
    r'>\s*\(.*?\)',
    r'\|\s*\|',
    r'curl\s+.*\|',
    r'wget\s+.*\|',
    r'eval\s*\(',
    r'exec\s*\(',
    r'system\s*\(',
    r'__import__',
    r'import\s+os\.system',
    r'subprocess\.call',
    r'subprocess\.run',
    r'subprocess\.Popen',
]

# Allowed URL schemes
ALLOWED_URL_SCHEMES = {'http', 'https'}

# Blocked URL patterns
BLOCKED_URL_PATTERNS = [
    r'127\.\d+\.\d+\.\d+',
    r'10\.\d+\.\d+\.\d+',
    r'172\.(1[6-9]|2[0-9]|3[01])\.\d+\.\d+',
    r'192\.168\.\d+\.\d+',
    r'0\.0\.0\.0',
    r'localhost',
    r'\[::1\]',
    r'file://',
]

# Maximum allowed values
MAX_TIMEOUT = 300  # 5 minutes
MAX_ARGS = 50
MAX_ENV_VARS = 20
MAX_ARG_LENGTH = 1000
MAX_URL_LENGTH = 2048


@dataclass
class MCPServerConfig:
    """Validated MCP server configuration."""
    name: str
    command: str | None = None
    args: list[str] | None = None
    env: dict[str, str] | None = None
    url: str | None = None
    headers: dict[str, str] | None = None
    tool_timeout: int = 30
    enabled: bool = True
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        self.validate()
    
    def validate(self) -> None:
        """Validate the configuration."""
        # Must have either command or url
        if not self.command and not self.url:
            raise ValueError(f"MCP server '{self.name}': must have either command or url")
        
        # Cannot have both command and url
        if self.command and self.url:
            raise ValueError(f"MCP server '{self.name}': cannot have both command and url")
        
        if self.command:
            self._validate_command()
        
        if self.url:
            self._validate_url()
        
        self._validate_timeout()
        self._validate_args()
        self._validate_env()
    
    def _validate_command(self) -> None:
        """Validate command configuration."""
        # Check command is in allowed list
        cmd_parts = self.command.split()
        base_cmd = cmd_parts[0] if cmd_parts else self.command
        
        # Remove path if present
        base_cmd = Path(base_cmd).name
        
        if base_cmd not in ALLOWED_MCP_COMMANDS:
            raise ValueError(
                f"MCP server '{self.name}': command '{base_cmd}' not in allowed list. "
                f"Allowed: {', '.join(sorted(ALLOWED_MCP_COMMANDS))}"
            )
        
        # Check for dangerous patterns in full command
        full_cmd = self.command + ' ' + ' '.join(self.args or [])
        for pattern in BLOCKED_COMMAND_PATTERNS:
            if re.search(pattern, full_cmd, re.IGNORECASE):
                raise ValueError(
                    f"MCP server '{self.name}': command contains blocked pattern: {pattern}"
                )
    
    def _validate_url(self) -> None:
        """Validate URL configuration."""
        if len(self.url) > MAX_URL_LENGTH:
            raise ValueError(
                f"MCP server '{self.name}': URL too long ({len(self.url)} > {MAX_URL_LENGTH})"
            )
        
        parsed = urlparse(self.url)
        
        # Check scheme
        if parsed.scheme not in ALLOWED_URL_SCHEMES:
            raise ValueError(
                f"MCP server '{self.name}': URL scheme '{parsed.scheme}' not allowed. "
                f"Allowed: {', '.join(sorted(ALLOWED_URL_SCHEMES))}"
            )
        
        # Check for blocked patterns
        for pattern in BLOCKED_URL_PATTERNS:
            if re.search(pattern, self.url, re.IGNORECASE):
                raise ValueError(
                    f"MCP server '{self.name}': URL matches blocked pattern: {pattern}"
                )
        
        # Check for suspicious characters
        if '\x00' in self.url or '\n' in self.url or '\r' in self.url:
            raise ValueError(f"MCP server '{self.name}': URL contains invalid characters")
    
    def _validate_timeout(self) -> None:
        """Validate timeout configuration."""
        if self.tool_timeout < 1:
            raise ValueError(
                f"MCP server '{self.name}': timeout must be at least 1 second"
            )
        
        if self.tool_timeout > MAX_TIMEOUT:
            raise ValueError(
                f"MCP server '{self.name}': timeout too large ({self.tool_timeout} > {MAX_TIMEOUT})"
            )
    
    def _validate_args(self) -> None:
        """Validate arguments."""
        if not self.args:
            return
        
        if len(self.args) > MAX_ARGS:
            raise ValueError(
                f"MCP server '{self.name}': too many arguments ({len(self.args)} > {MAX_ARGS})"
            )
        
        for i, arg in enumerate(self.args):
            if len(arg) > MAX_ARG_LENGTH:
                raise ValueError(
                    f"MCP server '{self.name}': argument {i} too long ({len(arg)} > {MAX_ARG_LENGTH})"
                )
            
            # Check for dangerous patterns in args
            for pattern in BLOCKED_COMMAND_PATTERNS:
                if re.search(pattern, arg, re.IGNORECASE):
                    raise ValueError(
                        f"MCP server '{self.name}': argument {i} contains blocked pattern: {pattern}"
                    )
    
    def _validate_env(self) -> None:
        """Validate environment variables."""
        if not self.env:
            return
        
        if len(self.env) > MAX_ENV_VARS:
            raise ValueError(
                f"MCP server '{self.name}': too many environment variables ({len(self.env)} > {MAX_ENV_VARS})"
            )
        
        # List of sensitive environment variable names that shouldn't be set
        sensitive_vars = {
            'PATH', 'LD_LIBRARY_PATH', 'LD_PRELOAD',
            'SHELL', 'HOME', 'USER', 'USERNAME',
        }
        
        for key in self.env.keys():
            if key.upper() in sensitive_vars:
                logger.warning(
                    f"MCP server '{self.name}': overriding sensitive env var: {key}"
                )


class MCPSecurityPolicy:
    """Security policy for MCP servers."""
    
    def __init__(
        self,
        max_servers: int = 10,
        require_validation: bool = True,
        allow_custom_commands: bool = False,
    ):
        self.max_servers = max_servers
        self.require_validation = require_validation
        self.allow_custom_commands = allow_custom_commands
    
    def validate_server_list(self, servers: dict[str, Any]) -> dict[str, MCPServerConfig]:
        """Validate a list of MCP server configurations."""
        if len(servers) > self.max_servers:
            raise ValueError(
                f"Too many MCP servers configured ({len(servers)} > {self.max_servers})"
            )
        
        validated = {}
        for name, config in servers.items():
            try:
                if isinstance(config, dict):
                    validated[name] = MCPServerConfig(name=name, **config)
                elif hasattr(config, 'command') or hasattr(config, 'url'):
                    # Handle dataclass-like objects
                    validated[name] = MCPServerConfig(
                        name=name,
                        command=getattr(config, 'command', None),
                        args=getattr(config, 'args', None),
                        env=getattr(config, 'env', None),
                        url=getattr(config, 'url', None),
                        headers=getattr(config, 'headers', None),
                        tool_timeout=getattr(config, 'tool_timeout', 30),
                        enabled=getattr(config, 'enabled', True),
                    )
                else:
                    logger.warning(f"MCP server '{name}': unknown config format, skipping")
                    continue
            except ValueError as e:
                if self.require_validation:
                    raise
                logger.error(f"MCP server '{name}': validation failed: {e}")
                continue
        
        return validated


def sanitize_mcp_config(config: dict[str, Any]) -> dict[str, Any]:
    """Sanitize MCP configuration for display/logging."""
    sanitized = {}
    
    for name, server_config in config.items():
        if isinstance(server_config, dict):
            sanitized[name] = {
                k: v for k, v in server_config.items()
                if k not in {'env', 'headers'}  # Remove sensitive fields
            }
            sanitized[name]['has_env'] = bool(server_config.get('env'))
            sanitized[name]['has_headers'] = bool(server_config.get('headers'))
        else:
            sanitized[name] = {"type": str(type(server_config))}
    
    return sanitized


def check_mcp_command_safety(command: str, args: list[str]) -> tuple[bool, str]:
    """Check if an MCP command is safe to execute."""
    full_cmd = command + ' ' + ' '.join(args)
    
    # Check command is in allowed list
    cmd_parts = command.split()
    base_cmd = Path(cmd_parts[0]).name if cmd_parts else command
    
    if base_cmd not in ALLOWED_MCP_COMMANDS:
        return False, f"Command '{base_cmd}' not in allowed list"
    
    # Check for dangerous patterns
    for pattern in BLOCKED_COMMAND_PATTERNS:
        if re.search(pattern, full_cmd, re.IGNORECASE):
            return False, f"Command contains blocked pattern: {pattern}"
    
    return True, ""

"""Shell execution tool with enhanced security."""

import asyncio
import os
import re
import shlex
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from loguru import logger

from crabclaw.agent.tools.base import Tool


class PermissionLevel(Enum):
    """Permission levels for command execution."""
    READ_ONLY = 1
    LIMITED = 2
    STANDARD = 3
    ELEVATED = 4


@dataclass
class SecurityPolicy:
    """Security policy for command execution."""
    permission_level: PermissionLevel = PermissionLevel.STANDARD
    allowed_commands: list[str] | None = None
    blocked_patterns: list[str] = field(default_factory=lambda: [
        # Destructive file operations
        r"\brm\s+-[rf]{1,2}\b",
        r"\bdel\s+/[fq]\b",
        r"\brmdir\s+/s\b",
        r"(?:^|[;&|]\s*)format\b",
        r"\b(mkfs|diskpart)\b",
        r"\bdd\s+if=",
        r">\s*/dev/sd",
        # System control
        r"\b(shutdown|reboot|poweroff|halt|init\s+0|init\s+6)\b",
        # Network attacks
        r":\(\)\s*\{.*\};\s*:",  # Fork bomb
        r"\bwget\s+.*\|\s*bash",
        r"\bcurl\s+.*\|\s*sh",
        r"\bwget\s+.*\|\s*sh",
        r"\bcurl\s+.*\|\s*bash",
        # Command injection
        r"`[^`]*`",
        r"\$\([^)]*\)",
        # Sudo and privilege escalation
        r"\bsudo\b",
        r"\bsu\s+-",
        # Dangerous redirects
        r">\s*/dev/(null|zero|random|urandom)",
        r">\s*/proc/",
        r">\s*/sys/",
        # Network scanning
        r"\b(nmap|masscan|zmap)\b",
        # Password and shadow files
        r"\b(cat|less|more|head|tail)\s+/etc/(passwd|shadow|group|gshadow)\b",
        # SSH keys
        r"\b(cat|less|more|head|tail)\s+.*ssh/id_",
        # Environment variable exposure
        r"\benv\b",
        r"\bprintenv\b",
        r"\bset\b",
        # History files
        r"\b(cat|less|more|head|tail)\s+.*history",
    ])
    audit_all_commands: bool = True
    max_command_length: int = 1000
    max_output_size: int = 10000


class CommandAuditLogger:
    """Audit logger for command execution."""

    def __init__(self, audit_file: str | None = None):
        self._audit_file = audit_file

    async def log_execution(
        self,
        command: str,
        user_id: str | None = None,
        working_dir: str | None = None,
        status: str = "executed",
        details: dict | None = None
    ) -> None:
        """Log command execution."""
        from datetime import datetime
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "command": command,
            "user_id": user_id,
            "working_dir": working_dir,
            "status": status,
            "details": details or {}
        }
        if self._audit_file:
            try:
                import json
                # Ensure audit directory exists
                Path(self._audit_file).parent.mkdir(parents=True, exist_ok=True)
                with open(self._audit_file, "a") as f:
                    f.write(json.dumps(log_entry) + "\n")
            except Exception as e:
                logger.warning("Failed to write audit log: {}", e)

        # Sanitize command for logging (truncate if too long)
        safe_command = command[:200] + "..." if len(command) > 200 else command
        logger.info(
            "[AUDIT] command={} user={} dir={} status={}",
            safe_command, user_id, working_dir, status
        )

    async def log_blocked(
        self,
        command: str,
        user_id: str | None = None,
        reason: str = "unknown"
    ) -> None:
        """Log blocked command."""
        await self.log_execution(command, user_id, status=f"blocked: {reason}")


class ExecTool(Tool):
    """Tool to execute shell commands with enhanced security."""

    COMMAND_WHITELIST = {
        PermissionLevel.READ_ONLY: [
            "ls", "cat", "head", "tail", "grep", "find", "pwd", "echo", 
            "which", "file", "stat", "wc", "sort", "uniq", "diff"
        ],
        PermissionLevel.LIMITED: [
            "ls", "cat", "head", "tail", "grep", "find", "pwd", "echo", 
            "mkdir", "touch", "cp", "mv", "rm", "which", "file", "stat", 
            "chmod", "chown", "wc", "sort", "uniq", "diff"
        ],
        PermissionLevel.STANDARD: [
            "ls", "cat", "head", "tail", "grep", "find", "pwd", "echo", 
            "mkdir", "touch", "cp", "mv", "rm", "git", "python", "pip", 
            "npm", "node", "which", "file", "stat", "chmod", "chown", 
            "curl", "wget", "tar", "zip", "unzip", "wc", "sort", "uniq", 
            "diff", "tee"
        ],
        PermissionLevel.ELEVATED: None,  # All commands allowed
    }

    # Additional dangerous subcommands that should be blocked
    DANGEROUS_SUBCOMMANDS = {
        'git': ['push', 'force', '--force', '-f', 'clean', 'reset', 'checkout', 'revert'],
        'rm': ['-rf', '-fr', '-r', '-f', '--force', '--recursive'],
        'curl': ['-o', '--output', '-O', '--remote-name'],
        'wget': ['-O', '--output-document'],
    }

    def __init__(
        self,
        timeout: int = 60,
        working_dir: str | None = None,
        deny_patterns: list[str] | None = None,
        allow_patterns: list[str] | None = None,
        restrict_to_workspace: bool = False,
        path_append: str = "",
        permission_level: PermissionLevel = PermissionLevel.STANDARD,
        audit_file: str | None = None,
        max_concurrent_commands: int = 5,
    ):
        self.timeout = min(timeout, 300)  # Max 5 minutes
        self.working_dir = working_dir
        self.deny_patterns = deny_patterns or SecurityPolicy().blocked_patterns
        self.allow_patterns = allow_patterns or []
        self.restrict_to_workspace = restrict_to_workspace
        self.path_append = path_append
        self._permission_level = permission_level
        self._audit_logger = CommandAuditLogger(audit_file)
        self._max_concurrent_commands = max_concurrent_commands
        self._semaphore = asyncio.Semaphore(max_concurrent_commands)
        self._command_history: list[dict] = []
        self._max_history_size = 100

    @property
    def name(self) -> str:
        return "exec"

    @property
    def description(self) -> str:
        return "Execute a shell command and return its output. Use with caution."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute"
                },
                "working_dir": {
                    "type": "string",
                    "description": "Optional working directory for the command"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Command timeout in seconds (max 300)"
                }
            },
            "required": ["command"]
        }
    
    async def execute(self, command: str, working_dir: str | None = None, 
                     timeout: int | None = None, **kwargs: Any) -> str:
        # Validate command length
        if len(command) > SecurityPolicy().max_command_length:
            return f"Error: Command too long (max {SecurityPolicy().max_command_length} characters)"
        
        # Use semaphore to limit concurrent commands
        async with self._semaphore:
            return await self._execute_command(command, working_dir, timeout)
    
    async def _execute_command(self, command: str, working_dir: str | None = None,
                              timeout: int | None = None) -> str:
        cwd = working_dir or self.working_dir or os.getcwd()
        actual_timeout = min(timeout or self.timeout, 300)
        
        # Security checks
        guard_error = self._guard_command(command, cwd)
        if guard_error:
            await self._audit_logger.log_blocked(command, reason=guard_error)
            return guard_error

        if not self._is_command_allowed(command):
            error_msg = f"Error: Command not in allowlist for permission level {self._permission_level.name}"
            await self._audit_logger.log_blocked(command, reason="not_in_allowlist")
            return error_msg

        # Check for dangerous subcommands
        subcommand_error = self._check_dangerous_subcommands(command)
        if subcommand_error:
            await self._audit_logger.log_blocked(command, reason=subcommand_error)
            return f"Error: {subcommand_error}"

        # Log execution start
        await self._audit_logger.log_execution(command, working_dir=cwd, status="executing")
        
        # Add to command history
        self._add_to_history(command, cwd)

        # Prepare environment
        env = os.environ.copy()
        if self.path_append:
            env["PATH"] = env.get("PATH", "") + os.pathsep + self.path_append
        
        # Remove sensitive environment variables
        sensitive_vars = ['API_KEY', 'TOKEN', 'SECRET', 'PASSWORD', 'PRIVATE_KEY']
        for var in list(env.keys()):
            if any(s in var.upper() for s in sensitive_vars):
                del env[var]

        try:
            # Use safer execution method
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env,
                limit=1024 * 1024,  # 1MB buffer limit
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=actual_timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                try:
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    pass
                await self._audit_logger.log_execution(
                    command, working_dir=cwd, status="timeout",
                    details={"timeout": actual_timeout}
                )
                return f"Error: Command timed out after {actual_timeout} seconds"
            
            # Build output
            output_parts = []
            
            if stdout:
                stdout_text = stdout.decode("utf-8", errors="replace")
                output_parts.append(stdout_text)
            
            if stderr:
                stderr_text = stderr.decode("utf-8", errors="replace")
                if stderr_text.strip():
                    output_parts.append(f"STDERR:\n{stderr_text}")
            
            if process.returncode != 0:
                output_parts.append(f"\nExit code: {process.returncode}")
            
            result = "\n".join(output_parts) if output_parts else "(no output)"
            
            # Truncate output
            max_len = SecurityPolicy().max_output_size
            if len(result) > max_len:
                result = result[:max_len] + f"\n... (truncated, {len(result) - max_len} more chars)"
            
            # Log successful execution
            await self._audit_logger.log_execution(
                command, working_dir=cwd, status="success",
                details={
                    "return_code": process.returncode,
                    "output_length": len(result)
                }
            )
            
            return result
            
        except Exception as e:
            await self._audit_logger.log_execution(
                command, working_dir=cwd, status="error",
                details={"error": str(e)}
            )
            return f"Error executing command: {str(e)}"

    def _guard_command(self, command: str, cwd: str) -> str | None:
        """Best-effort safety guard for potentially destructive commands."""
        cmd = command.strip()
        lower = cmd.lower()

        # Check for blocked patterns
        for pattern in self.deny_patterns:
            try:
                if re.search(pattern, lower):
                    return f"Error: Command blocked by safety guard (dangerous pattern: {pattern})"
            except re.error:
                continue

        # Check allow patterns
        if self.allow_patterns:
            if not any(re.search(p, lower) for p in self.allow_patterns):
                return "Error: Command blocked by safety guard (not in allowlist)"

        # Path traversal protection
        if self.restrict_to_workspace:
            # Check for path traversal attempts
            if "..\\" in cmd or "../" in cmd or ".." in cmd.split():
                return "Error: Command blocked by safety guard (path traversal detected)"

            try:
                cwd_path = Path(cwd).resolve()
                
                for raw in self._extract_absolute_paths(cmd):
                    try:
                        p = Path(raw.strip()).resolve()
                    except Exception:
                        continue
                    if p.is_absolute():
                        try:
                            p.relative_to(cwd_path)
                        except ValueError:
                            return f"Error: Command blocked by safety guard (path outside working dir: {raw})"
            except Exception as e:
                logger.warning(f"Error checking path restrictions: {e}")

        # Check for chained commands that might bypass security
        dangerous_chains = [';', '&&', '||', '|']
        for chain in dangerous_chains:
            if chain in cmd:
                parts = cmd.split(chain)
                for part in parts[1:]:  # Check parts after the chain
                    part = part.strip()
                    if part:
                        # Recursively check each part
                        sub_error = self._guard_command(part, cwd)
                        if sub_error:
                            return f"Error: Command blocked in chained command: {sub_error}"

        return None

    def _is_command_allowed(self, command: str) -> bool:
        """Check if command is in the allowlist for the current permission level."""
        if self.allow_patterns:
            return any(re.search(p, command.lower()) for p in self.allow_patterns)

        allowed = self.COMMAND_WHITELIST.get(self._permission_level)
        if allowed is None:
            return True

        # Parse command to get base command
        try:
            # Simple parsing - get first word
            cmd_base = command.strip().split()[0] if command.strip() else ""
            # Remove any path components
            cmd_name = cmd_base.lower().replace("\\", "/").split("/")[-1]
            # Remove any file extension
            cmd_name = cmd_name.split('.')[0]
            
            return cmd_name in allowed
        except Exception:
            return False

    def _check_dangerous_subcommands(self, command: str) -> str | None:
        """Check for dangerous subcommands in specific tools."""
        cmd_lower = command.lower().strip()
        
        for tool, dangerous_flags in self.DANGEROUS_SUBCOMMANDS.items():
            if cmd_lower.startswith(tool + ' '):
                for flag in dangerous_flags:
                    # Check for flag as separate word or with space
                    if f' {flag}' in cmd_lower or cmd_lower.endswith(f' {flag}'):
                        return f"Dangerous subcommand '{flag}' detected in {tool}"
        
        return None

    def _extract_absolute_paths(self, command: str) -> list[str]:
        """Extract absolute paths from command."""
        # Windows paths: C:\...
        win_paths = re.findall(r"[A-Za-z]:\\[^\s\"'|><;]+", command)
        # POSIX paths: /absolute/...
        posix_paths = re.findall(r"(?:^|[\s|>])(/[^\s\"'>]+)", command)
        return win_paths + posix_paths

    def _add_to_history(self, command: str, cwd: str) -> None:
        """Add command to history for rate limiting and monitoring."""
        from datetime import datetime
        
        self._command_history.append({
            "timestamp": datetime.now(),
            "command": command[:100],  # Truncate for memory
            "cwd": cwd
        })
        
        # Trim history if too large
        if len(self._command_history) > self._max_history_size:
            self._command_history = self._command_history[-self._max_history_size:]

    def get_command_history(self) -> list[dict]:
        """Get recent command history."""
        return self._command_history.copy()

    def clear_history(self) -> None:
        """Clear command history."""
        self._command_history.clear()

"""Secure audit logging for security events."""

import hashlib
import json
import os
import stat
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from loguru import logger


class AuditEventType(Enum):
    """Types of audit events."""
    AUTH_SUCCESS = "auth_success"
    AUTH_FAILURE = "auth_failure"
    ACCESS_DENIED = "access_denied"
    RATE_LIMIT_HIT = "rate_limit_hit"
    COMMAND_EXECUTED = "command_executed"
    COMMAND_BLOCKED = "command_blocked"
    FILE_ACCESSED = "file_accessed"
    FILE_MODIFIED = "file_modified"
    CONFIG_CHANGED = "config_changed"
    API_KEY_USED = "api_key_used"
    SENSITIVE_DATA = "sensitive_data"
    SECURITY_VIOLATION = "security_violation"
    LLM_CALL = "llm_call"


@dataclass
class AuditEvent:
    """Audit event record."""
    event_type: AuditEventType
    timestamp: float
    actor_id: str | None = None
    action: str | None = None
    resource: str | None = None
    result: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    session_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
            "actor_id": self._sanitize_id(self.actor_id),
            "action": self.action,
            "resource": self._sanitize_resource(self.resource),
            "result": self.result,
            "details": self._sanitize_details(self.details),
            "session_id": self.session_id,
            "ip_address": self._mask_ip(self.ip_address),
            "user_agent": self.user_agent,
        }

    def _sanitize_id(self, id_str: str | None) -> str | None:
        """Sanitize ID for logging."""
        if not id_str:
            return None
        # Hash the ID for privacy
        return hashlib.sha256(id_str.encode()).hexdigest()[:16]

    def _sanitize_resource(self, resource: str | None) -> str | None:
        """Sanitize resource path."""
        if not resource:
            return None
        # Remove sensitive parts from paths
        home = str(Path.home())
        resource = resource.replace(home, "~")
        return resource

    def _sanitize_details(self, details: dict[str, Any]) -> dict[str, Any]:
        """Sanitize sensitive details."""
        sanitized = {}
        sensitive_keys = {'password', 'secret', 'token', 'key', 'api_key', 'credential', 'auth'}

        for key, value in details.items():
            if any(s in key.lower() for s in sensitive_keys):
                sanitized[key] = "***REDACTED***"
            elif isinstance(value, str) and len(value) > 1000:
                sanitized[key] = value[:1000] + "... [truncated]"
            else:
                sanitized[key] = value

        return sanitized

    def _mask_ip(self, ip: str | None) -> str | None:
        """Mask IP address for privacy."""
        if not ip:
            return None
        parts = ip.split('.')
        if len(parts) == 4:
            return f"{parts[0]}.{parts[1]}.***.***"
        return "***masked***"


class SecureAuditLogger:
    """Secure audit logger with integrity protection."""

    def __init__(
        self,
        log_dir: Path | str | None = None,
        max_file_size: int = 10 * 1024 * 1024,  # 10MB
        max_files: int = 10,
        enable_console: bool = False,
    ):
        self.log_dir = Path(log_dir) if log_dir else Path.home() / '.crabclaw' / 'audit'
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.max_file_size = max_file_size
        self.max_files = max_files
        self.enable_console = enable_console

        self._lock = threading.Lock()
        self._current_file: Path | None = None
        self._current_size = 0
        self._event_count = 0
        self._last_rotation = time.time()

        # Initialize log file
        self._rotate_if_needed()

        # Set secure permissions on log directory
        self._set_secure_permissions()

    def _set_secure_permissions(self) -> None:
        """Set secure permissions on log directory and files."""
        try:
            # Set directory permissions to 700 (owner only)
            os.chmod(self.log_dir, stat.S_IRWXU)

            # Set permissions on existing log files
            for log_file in self.log_dir.glob("audit_*.log"):
                os.chmod(log_file, stat.S_IRUSR | stat.S_IWUSR)  # 600
        except Exception as e:
            logger.warning(f"Failed to set secure permissions on audit log: {e}")

    def _get_log_file(self) -> Path:
        """Get current log file path."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return self.log_dir / f"audit_{timestamp}.log"

    def _rotate_if_needed(self) -> None:
        """Rotate log file if needed."""
        need_rotation = (
            self._current_file is None or
            self._current_size >= self.max_file_size or
            (time.time() - self._last_rotation) > 86400  # Rotate daily
        )

        if need_rotation:
            self._current_file = self._get_log_file()
            self._current_size = 0
            self._last_rotation = time.time()
            self._cleanup_old_files()

    def _cleanup_old_files(self) -> None:
        """Remove old log files."""
        try:
            log_files = sorted(
                self.log_dir.glob("audit_*.log"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )

            for old_file in log_files[self.max_files:]:
                old_file.unlink()
                logger.debug(f"Removed old audit log: {old_file}")
        except Exception as e:
            logger.warning(f"Failed to cleanup old audit logs: {e}")

    def log(self, event: AuditEvent) -> None:
        """Log an audit event."""
        with self._lock:
            self._rotate_if_needed()

            # Write event to log file
            event_dict = event.to_dict()
            event_json = json.dumps(event_dict, ensure_ascii=False)

            try:
                with open(self._current_file, 'a', encoding='utf-8') as f:
                    f.write(event_json + '\n')

                self._current_size += len(event_json) + 1
                self._event_count += 1

                # Also log to console if enabled
                if self.enable_console:
                    logger.info(f"AUDIT: {event.event_type.value} - {event.action}")

            except Exception as e:
                logger.error(f"Failed to write audit log: {e}")

    def log_security_event(
        self,
        event_type: AuditEventType,
        actor_id: str | None = None,
        action: str | None = None,
        resource: str | None = None,
        result: str | None = None,
        details: dict[str, Any] | None = None,
        **kwargs
    ) -> None:
        """Convenience method for logging security events."""
        event = AuditEvent(
            event_type=event_type,
            timestamp=time.time(),
            actor_id=actor_id,
            action=action,
            resource=resource,
            result=result,
            details=details or {},
            **kwargs
        )
        self.log(event)

    def get_recent_events(
        self,
        event_type: AuditEventType | None = None,
        limit: int = 100,
        since: float | None = None,
    ) -> list[AuditEvent]:
        """Get recent audit events."""
        events = []

        try:
            log_files = sorted(
                self.log_dir.glob("audit_*.log"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )

            for log_file in log_files:
                with open(log_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            event_dict = json.loads(line.strip())

                            # Filter by type
                            if event_type and event_dict.get('event_type') != event_type.value:
                                continue

                            # Filter by time
                            if since and event_dict.get('timestamp', 0) < since:
                                continue

                            events.append(event_dict)

                            if len(events) >= limit:
                                return events

                        except json.JSONDecodeError:
                            continue

        except Exception as e:
            logger.error(f"Failed to read audit logs: {e}")

        return events

    def get_stats(self) -> dict[str, Any]:
        """Get audit logger statistics."""
        return {
            "total_events": self._event_count,
            "current_file": str(self._current_file) if self._current_file else None,
            "current_size": self._current_size,
            "log_dir": str(self.log_dir),
            "max_file_size": self.max_file_size,
            "max_files": self.max_files,
        }


# Global audit logger instance
_audit_logger: SecureAuditLogger | None = None
_audit_loggers: dict[str, SecureAuditLogger] = {}


def get_audit_logger() -> SecureAuditLogger:
    """Get global audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = SecureAuditLogger()
    return _audit_logger


def get_audit_logger_for_dir(log_dir: Path | str) -> SecureAuditLogger:
    p = str(Path(log_dir))
    existing = _audit_loggers.get(p)
    if existing is not None:
        return existing
    logger = SecureAuditLogger(log_dir=log_dir)
    _audit_loggers[p] = logger
    return logger


def configure_audit_logger(
    log_dir: Path | str | None = None,
    max_file_size: int = 10 * 1024 * 1024,
    max_files: int = 10,
    enable_console: bool = False,
) -> SecureAuditLogger:
    """Configure global audit logger."""
    global _audit_logger
    _audit_logger = SecureAuditLogger(
        log_dir=log_dir,
        max_file_size=max_file_size,
        max_files=max_files,
        enable_console=enable_console,
    )
    return _audit_logger


def audit_log(
    event_type: AuditEventType,
    actor_id: str | None = None,
    action: str | None = None,
    resource: str | None = None,
    result: str | None = None,
    details: dict[str, Any] | None = None,
    **kwargs
) -> None:
    """Convenience function for audit logging."""
    logger = get_audit_logger()
    logger.log_security_event(
        event_type=event_type,
        actor_id=actor_id,
        action=action,
        resource=resource,
        result=result,
        details=details,
        **kwargs
    )


class SensitiveDataFilter:
    """Filter for masking sensitive data in logs."""

    SENSITIVE_PATTERNS = [
        (r'api[_-]?key[=:]\s*["\']?[\w-]+["\']?', 'api_key=***'),
        (r'password[=:]\s*["\']?[^"\'\s]+["\']?', 'password=***'),
        (r'secret[=:]\s*["\']?[^"\'\s]+["\']?', 'secret=***'),
        (r'token[=:]\s*["\']?[^"\'\s]+["\']?', 'token=***'),
        (r'Bearer\s+[\w-]+', 'Bearer ***'),
        (r'Basic\s+[A-Za-z0-9+/=]+', 'Basic ***'),
        (r'sk-[a-zA-Z0-9]{20,}', 'sk-***'),
    ]

    @classmethod
    def filter(cls, message: str) -> str:
        """Filter sensitive data from message."""
        import re
        filtered = message
        for pattern, replacement in cls.SENSITIVE_PATTERNS:
            filtered = re.sub(pattern, replacement, filtered, flags=re.IGNORECASE)
        return filtered

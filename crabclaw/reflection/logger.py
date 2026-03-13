"""
HABOS Architecture - Foundation of the Meta-Cognition Layer

This module defines the structured AuditLogger, which records all key behaviors of the Agent in a machine-readable format,
providing a data foundation for subsequent autonomous reflection and optimization.
"""
import json
import logging
from logging.handlers import RotatingFileHandler
from typing import Any, Callable, Dict, Optional


class AuditLogger:
    """
    一个专门用于记录结构化审计日志的记录器。
    """

    def __init__(
        self,
        log_file_path: str,
        logger_name: str = "AuditLogger",
        on_event: Optional[Callable[[dict], None]] = None,
    ):
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(logging.INFO)
        self._on_event = on_event

        # Prevent duplicate handlers
        if not self.logger.handlers:
            # Use RotatingFileHandler to prevent unlimited log file growth
            handler = RotatingFileHandler(
                log_file_path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
            )
            # We only care about the original JSON message, so the formatter is simple
            formatter = logging.Formatter("%(message)s")
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def log(self, event_type: str, engine: str, details: Dict[str, Any]):
        """
        Record a structured audit event.

        Args:
            event_type: The type of event (e.g., 'LLMCall_Start', 'ActionSelected').
            engine: The engine that generated the event ('reactive', 'proactive', 'reflection').
            details: A dictionary containing specific event information.
        """
        log_entry = {
            "timestamp": logging.time.time(),
            "event_type": event_type,
            "engine": engine,
            "details": details,
        }
        try:
            self.logger.info(json.dumps(log_entry, ensure_ascii=False))
            if self._on_event:
                try:
                    self._on_event(log_entry)
                except Exception:
                    # Never break agent flow because of dashboard hooks
                    pass
        except TypeError as e:
            # Handle objects that cannot be serialized to JSON
            self.logger.error(f"JSON serialization error: {e}", exc_info=True)
            # Try using repr() as a fallback
            log_entry["details"] = repr(details)
            self.logger.info(json.dumps(log_entry, ensure_ascii=False))
            if self._on_event:
                try:
                    self._on_event(log_entry)
                except Exception:
                    pass


# A global instance can be created for easy calling throughout the project
# audit_logger = AuditLogger("path/to/audit.log.jsonl")

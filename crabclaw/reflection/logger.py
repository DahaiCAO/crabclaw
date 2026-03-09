"""
HABOS 架构 - 反思层 (Meta-Cognition Layer) 的基础

此模块定义了结构化审计日志 (AuditLogger)，它以机器可读的格式记录 Agent 的所有关键行为，
为后续的自主反思和优化提供数据基础。
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

        # 防止重复添加 handler
        if not self.logger.handlers:
            # 使用 RotatingFileHandler 来防止日志文件无限增大
            handler = RotatingFileHandler(
                log_file_path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
            )
            # 我们只关心原始的 JSON 消息，所以格式化器很简单
            formatter = logging.Formatter("%(message)s")
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def log(self, event_type: str, engine: str, details: Dict[str, Any]):
        """
        记录一个结构化的审计事件。

        Args:
            event_type: 事件的类型 (e.g., 'LLMCall_Start', 'ActionSelected').
            engine: 产生事件的引擎 ('reactive', 'proactive', 'reflection').
            details: 包含事件具体信息的字典。
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
            # 处理无法序列化为 JSON 的对象
            self.logger.error(f"JSON serialization error: {e}", exc_info=True)
            # 尝试使用 repr() 作为备用方案
            log_entry["details"] = repr(details)
            self.logger.info(json.dumps(log_entry, ensure_ascii=False))
            if self._on_event:
                try:
                    self._on_event(log_entry)
                except Exception:
                    pass


# 可以创建一个全局实例，方便在项目各处调用
# audit_logger = AuditLogger("path/to/audit.log.jsonl")

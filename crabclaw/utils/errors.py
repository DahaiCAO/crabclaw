"""Unified error handling and result types for Crabclaw."""

from dataclasses import dataclass
from enum import Enum
from typing import Generic, TypeVar

T = TypeVar("T")
E = TypeVar("E")


class ErrorCode(Enum):
    """Standard error codes for Crabclaw."""
    UNKNOWN = "unknown"
    INVALID_INPUT = "invalid_input"
    NOT_FOUND = "not_found"
    PERMISSION_DENIED = "permission_denied"
    TIMEOUT = "timeout"
    NETWORK_ERROR = "network_error"
    EXTERNAL_SERVICE_ERROR = "external_service_error"
    CONFIGURATION_ERROR = "configuration_error"
    TOOL_EXECUTION_ERROR = "tool_execution_error"
    SECURITY_VIOLATION = "security_violation"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"


@dataclass
class CrabclawError(Exception):
    """Base exception for Crabclaw errors."""
    code: ErrorCode = ErrorCode.UNKNOWN
    message: str = ""
    details: dict | None = None

    def __init__(self, message: str, code: ErrorCode = ErrorCode.UNKNOWN, details: dict | None = None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict:
        return {
            "code": self.code.value,
            "message": self.message,
            "details": self.details
        }


class InvalidInputError(CrabclawError):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message, ErrorCode.INVALID_INPUT, details)


class NotFoundError(CrabclawError):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message, ErrorCode.NOT_FOUND, details)


class PermissionDeniedError(CrabclawError):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message, ErrorCode.PERMISSION_DENIED, details)


class TimeoutError(CrabclawError):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message, ErrorCode.TIMEOUT, details)


class NetworkError(CrabclawError):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message, ErrorCode.NETWORK_ERROR, details)


class ExternalServiceError(CrabclawError):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message, ErrorCode.EXTERNAL_SERVICE_ERROR, details)


class ConfigurationError(CrabclawError):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message, ErrorCode.CONFIGURATION_ERROR, details)


class ToolExecutionError(CrabclawError):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message, ErrorCode.TOOL_EXECUTION_ERROR, details)


class SecurityViolationError(CrabclawError):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message, ErrorCode.SECURITY_VIOLATION, details)


class RateLimitExceededError(CrabclawError):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message, ErrorCode.RATE_LIMIT_EXCEEDED, details)


class Result(Generic[T]):
    """Result type for explicit error handling without exceptions."""

    def __init__(self, value: T | None = None, error: CrabclawError | None = None):
        self._value = value
        self._error = error

    @property
    def is_success(self) -> bool:
        return self._error is None

    @property
    def is_error(self) -> bool:
        return self._error is not None

    @property
    def value(self) -> T:
        if self._error:
            raise ValueError(f"Cannot get value from error result: {self._error.message}")
        return self._value  # type: ignore

    @property
    def error(self) -> CrabclawError | None:
        return self._error

    def unwrap(self) -> T:
        """Unwrap the value or raise the error."""
        if self._error:
            raise self._error
        return self._value  # type: ignore

    def unwrap_or(self, default: T) -> T:
        """Return value or default if error."""
        return self._value if self._error is None else default

    def map(self, func: callable) -> "Result":
        """Map the value if success."""
        if self.is_success and self._value is not None:
            try:
                return Result(value=func(self._value))
            except Exception as e:
                return Result(error=CrabclawError(str(e)))
        return self

    def map_error(self, func: callable) -> "Result":
        """Map the error if error."""
        if self.is_error:
            try:
                return Result(error=func(self._error))
            except Exception:
                return self
        return self

    @classmethod
    def success(cls, value: T) -> "Result[T]":
        return cls(value=value)

    @classmethod
    def failure(cls, error: CrabclawError | str) -> "Result":
        if isinstance(error, str):
            error = CrabclawError(error)
        return cls(error=error)

    def __repr__(self) -> str:
        if self.is_success:
            return f"Result.success({self._value!r})"
        return f"Result.failure({self._error!r})"

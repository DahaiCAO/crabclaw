"""File system tools with enhanced security sandbox."""

import difflib
import hashlib
import mimetypes
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

from crabclaw.agent.tools.base import Tool


# Allowed file extensions for read/write operations
ALLOWED_EXTENSIONS = {
    # Text files
    ".txt", ".md", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg",
    # Code files
    ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".scss",
    ".sh", ".bash", ".zsh", ".bat", ".ps1", ".sql",
    # Data files
    ".csv", ".xml", ".log",
    # Config files
    ".env", ".gitignore", ".dockerignore",
    # Documentation
    ".rst", ".adoc",
}

# Blocked extensions - never allow these
BLOCKED_EXTENSIONS = {
    # Executables
    ".exe", ".dll", ".so", ".dylib", ".bin",
    # Windows executables
    ".bat", ".cmd", ".com", ".msi", ".scr", ".pif",
    # Java
    ".jar", ".class", ".war", ".ear",
    # Scripts that can be dangerous
    ".vbs", ".js", ".jse", ".wsf", ".wsh",
    # System files
    ".reg", ".msc", ".cpl", ".gadget", ".application",
    # Archives that might contain executables
    ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar",
    # Binary data
    ".dat", ".db", ".sqlite", ".sqlite3",
}

# Maximum file sizes
MAX_FILE_SIZE_READ = 10 * 1024 * 1024  # 10MB for reading
MAX_FILE_SIZE_WRITE = 5 * 1024 * 1024   # 5MB for writing

# Dangerous patterns in file content
DANGEROUS_CONTENT_PATTERNS = [
    rb'<script[^>]*>.*?</script>',  # Scripts
    rb'javascript:',  # JavaScript URLs
    rb'on\w+\s*=',  # Event handlers
    rb'eval\s*\(',  # eval()
    rb'exec\s*\(',  # exec()
    rb'system\s*\(',  # system()
    rb'import\s+os\s*;\s*os\.system',  # Python system calls
    rb'subprocess\.call',  # Python subprocess
    rb'Runtime\.getRuntime\(\)\.exec',  # Java exec
    rb'ProcessBuilder',  # Java process builder
]


@dataclass
class FileSystemPolicy:
    """Security policy for file system operations."""
    allowed_dir: Path | None = None
    max_file_size_read: int = MAX_FILE_SIZE_READ
    max_file_size_write: int = MAX_FILE_SIZE_WRITE
    allowed_extensions: set[str] = field(default_factory=lambda: ALLOWED_EXTENSIONS)
    blocked_extensions: set[str] = field(default_factory=lambda: BLOCKED_EXTENSIONS)
    audit_enabled: bool = True
    restrict_path_traversal: bool = True
    check_content_safety: bool = True
    max_path_length: int = 4096
    max_filename_length: int = 255


class FileSystemAuditLogger:
    """Audit logger for file system operations."""

    def __init__(self, audit_file: str | None = None):
        self._audit_file = audit_file

    async def log_operation(
        self,
        operation: str,
        path: str,
        user_id: str | None = None,
        status: str = "success",
        details: dict | None = None
    ) -> None:
        """Log file system operation."""
        from datetime import datetime
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "path": path,
            "user_id": user_id,
            "status": status,
            "details": details or {}
        }
        if self._audit_file:
            try:
                import json
                Path(self._audit_file).parent.mkdir(parents=True, exist_ok=True)
                with open(self._audit_file, "a") as f:
                    f.write(json.dumps(log_entry) + "\n")
            except Exception as e:
                logger.warning("Failed to write audit log: {}", e)

        logger.info(
            "[AUDIT] operation={} path={} user={} status={}",
            operation, path, user_id, status
        )

    async def log_blocked(
        self,
        operation: str,
        path: str,
        reason: str,
        user_id: str | None = None
    ) -> None:
        """Log blocked file system operation."""
        await self.log_operation(operation, path, user_id, f"blocked: {reason}")


def _is_under(path: Path, directory: Path) -> bool:
    """Check if a path is under a directory."""
    try:
        path.relative_to(directory.resolve())
        return True
    except ValueError:
        return False


def _resolve_path(
    path: str, 
    workspace: Path | None = None, 
    allowed_dir: Path | None = None,
    extra_allowed_dirs: list[Path] | None = None,
    restrict_traversal: bool = True
) -> Path:
    """Resolve path against workspace (if relative) and enforce directory restriction."""
    # Check path length
    if len(path) > FileSystemPolicy().max_path_length:
        raise PermissionError(f"Path too long: {len(path)} characters (max {FileSystemPolicy().max_path_length})")
    
    # Check for null bytes
    if '\x00' in path:
        raise PermissionError("Path contains null bytes")
    
    # Check for path traversal
    if restrict_traversal:
        # Normalize path for traversal detection
        normalized = path.replace('\\', '/')
        if '/../' in normalized or normalized.startswith('../') or normalized.endswith('/..'):
            raise PermissionError(f"Path traversal detected: {path}")
        
        # Check for encoded traversal attempts
        if '%2e%2e' in path.lower() or '..%2f' in path.lower():
            raise PermissionError(f"Encoded path traversal detected: {path}")

    try:
        p = Path(path).expanduser()
    except Exception as e:
        raise PermissionError(f"Invalid path: {path}") from e
    
    # Resolve relative paths against workspace
    if not p.is_absolute() and workspace:
        p = workspace / p

    try:
        resolved = p.resolve()
    except Exception as e:
        raise PermissionError(f"Cannot resolve path: {path}") from e
    
    # Enforce allowed directory restriction
    if allowed_dir:
        try:
            all_dirs = [allowed_dir] + (extra_allowed_dirs or [])
            if not any(_is_under(resolved, d) for d in all_dirs):
                raise PermissionError(f"Path {path} is outside allowed directory {allowed_dir}")
        except Exception as e:
            raise PermissionError(f"Error checking path restriction: {e}") from e
    
    # Check filename length
    if len(resolved.name) > FileSystemPolicy().max_filename_length:
        raise PermissionError(f"Filename too long: {len(resolved.name)} characters")
    
    return resolved


def _validate_extension(path: Path, policy: FileSystemPolicy) -> None:
    """Validate file extension against policy."""
    ext = path.suffix.lower()

    if ext in policy.blocked_extensions:
        raise PermissionError(f"File extension {ext} is blocked for security reasons")

    if policy.allowed_extensions and ext not in policy.allowed_extensions:
        raise PermissionError(f"File extension {ext} is not in the allowed list")


def _validate_size(path: Path, policy: FileSystemPolicy, for_write: bool = False) -> None:
    """Validate file size against policy."""
    max_size = policy.max_file_size_write if for_write else policy.max_file_size_read
    
    if path.exists() and path.is_file():
        size = path.stat().st_size
        if size > max_size:
            raise PermissionError(f"File size {size} exceeds maximum allowed {max_size}")


def _check_content_safety(content: str | bytes) -> str | None:
    """Check file content for dangerous patterns."""
    if not content:
        return None
    
    # Convert to bytes if string
    if isinstance(content, str):
        content_bytes = content.encode('utf-8', errors='ignore')
    else:
        content_bytes = content
    
    # Check for dangerous patterns
    for pattern in DANGEROUS_CONTENT_PATTERNS:
        try:
            if re.search(pattern, content_bytes, re.IGNORECASE):
                return f"Content contains potentially dangerous pattern: {pattern.decode('utf-8', errors='ignore')}"
        except re.error:
            continue
    
    return None


def _compute_file_hash(path: Path) -> str:
    """Compute SHA-256 hash of file for integrity checking."""
    try:
        sha256_hash = hashlib.sha256()
        with open(path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except Exception:
        return ""


class ReadFileTool(Tool):
    """Tool to read file contents."""

    def __init__(self, workspace: Path | None = None, allowed_dir: Path | None = None, extra_allowed_dirs: list[Path] | None = None):
        self._workspace = workspace
        self._allowed_dir = allowed_dir
        self._extra_allowed_dirs = extra_allowed_dirs
        self._policy = FileSystemPolicy(allowed_dir=allowed_dir)

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "Read the contents of a file at the given path."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "The file path to read"}},
            "required": ["path"],
        }

    async def execute(self, path: str, **kwargs: Any) -> str:
        try:
            file_path = _resolve_path(path, self._workspace, self._allowed_dir, self._extra_allowed_dirs)
            
            if not file_path.exists():
                return f"Error: File not found: {path}"
            if not file_path.is_file():
                return f"Error: Not a file: {path}"
            
            # Validate extension
            _validate_extension(file_path, self._policy)
            
            # Validate size
            _validate_size(file_path, self._policy)
            
            # Read content
            content = file_path.read_text(encoding="utf-8")
            
            # Check content safety
            safety_error = _check_content_safety(content)
            if safety_error:
                logger.warning(f"File {path} contains potentially unsafe content: {safety_error}")
                # Don't block, just warn
            
            return content
        except PermissionError as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Error reading file: {str(e)}"


class WriteFileTool(Tool):
    """Tool to write content to a file."""

    def __init__(self, workspace: Path | None = None, allowed_dir: Path | None = None, extra_allowed_dirs: list[Path] | None = None):
        self._workspace = workspace
        self._allowed_dir = allowed_dir
        self._extra_allowed_dirs = extra_allowed_dirs
        self._policy = FileSystemPolicy(allowed_dir=allowed_dir)

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return "Write content to a file at the given path. Creates parent directories if needed."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "The file path to write to"},
                "content": {"type": "string", "description": "The content to write"},
            },
            "required": ["path", "content"],
        }

    async def execute(self, path: str, content: str, **kwargs: Any) -> str:
        try:
            # Validate content size
            content_bytes = content.encode('utf-8')
            if len(content_bytes) > self._policy.max_file_size_write:
                return f"Error: Content size {len(content_bytes)} exceeds maximum allowed {self._policy.max_file_size_write}"
            
            file_path = _resolve_path(path, self._workspace, self._allowed_dir, self._extra_allowed_dirs)
            
            # Validate extension
            _validate_extension(file_path, self._policy)
            
            # Check content safety
            safety_error = _check_content_safety(content)
            if safety_error:
                return f"Error: Content safety check failed: {safety_error}"
            
            # Create parent directories
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file
            file_path.write_text(content, encoding="utf-8")
            
            return f"Successfully wrote {len(content)} bytes to {file_path}"
        except PermissionError as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Error writing file: {str(e)}"


class EditFileTool(Tool):
    """Tool to edit a file by replacing text."""

    def __init__(self, workspace: Path | None = None, allowed_dir: Path | None = None, extra_allowed_dirs: list[Path] | None = None):
        self._workspace = workspace
        self._allowed_dir = allowed_dir
        self._extra_allowed_dirs = extra_allowed_dirs
        self._policy = FileSystemPolicy(allowed_dir=allowed_dir)

    @property
    def name(self) -> str:
        return "edit_file"

    @property
    def description(self) -> str:
        return "Edit a file by replacing old_text with new_text. The old_text must exist exactly in the file."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "The file path to edit"},
                "old_text": {"type": "string", "description": "The exact text to find and replace"},
                "new_text": {"type": "string", "description": "The text to replace with"},
            },
            "required": ["path", "old_text", "new_text"],
        }

    async def execute(self, path: str, old_text: str, new_text: str, **kwargs: Any) -> str:
        try:
            file_path = _resolve_path(path, self._workspace, self._allowed_dir, self._extra_allowed_dirs)
            
            if not file_path.exists():
                return f"Error: File not found: {path}"
            if not file_path.is_file():
                return f"Error: Not a file: {path}"
            
            # Validate extension
            _validate_extension(file_path, self._policy)
            
            # Validate size
            _validate_size(file_path, self._policy)
            
            # Read content
            content = file_path.read_text(encoding="utf-8")

            if old_text not in content:
                return self._not_found_message(old_text, content, path)

            # Count occurrences
            count = content.count(old_text)
            if count > 1:
                return f"Warning: old_text appears {count} times. Please provide more context to make it unique."

            # Check new text safety
            safety_error = _check_content_safety(new_text)
            if safety_error:
                return f"Error: New content safety check failed: {safety_error}"

            # Perform replacement
            new_content = content.replace(old_text, new_text, 1)
            
            # Validate new content size
            new_content_bytes = new_content.encode('utf-8')
            if len(new_content_bytes) > self._policy.max_file_size_write:
                return f"Error: New content size {len(new_content_bytes)} exceeds maximum allowed {self._policy.max_file_size_write}"
            
            # Write back
            file_path.write_text(new_content, encoding="utf-8")

            return f"Successfully edited {file_path}"
        except PermissionError as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Error editing file: {str(e)}"

    @staticmethod
    def _not_found_message(old_text: str, content: str, path: str) -> str:
        """Build a helpful error when old_text is not found."""
        lines = content.splitlines(keepends=True)
        old_lines = old_text.splitlines(keepends=True)
        window = len(old_lines)

        best_ratio, best_start = 0.0, 0
        for i in range(max(1, len(lines) - window + 1)):
            ratio = difflib.SequenceMatcher(None, old_lines, lines[i : i + window]).ratio()
            if ratio > best_ratio:
                best_ratio, best_start = ratio, best_start

        if best_ratio > 0.5:
            diff = "\n".join(
                difflib.unified_diff(
                    old_lines,
                    lines[best_start : best_start + window],
                    fromfile="old_text (provided)",
                    tofile=f"{path} (actual, line {best_start + 1})",
                    lineterm="",
                )
            )
            return f"Error: old_text not found in {path}.\nBest match ({best_ratio:.0%} similar) at line {best_start + 1}:\n{diff}"
        return (
            f"Error: old_text not found in {path}. No similar text found. Verify the file content."
        )


class ListDirTool(Tool):
    """Tool to list directory contents."""

    def __init__(self, workspace: Path | None = None, allowed_dir: Path | None = None, extra_allowed_dirs: list[Path] | None = None):
        self._workspace = workspace
        self._allowed_dir = allowed_dir
        self._extra_allowed_dirs = extra_allowed_dirs
        self._policy = FileSystemPolicy(allowed_dir=allowed_dir)

    @property
    def name(self) -> str:
        return "list_dir"

    @property
    def description(self) -> str:
        return "List the contents of a directory."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "The directory path to list"}},
            "required": ["path"],
        }

    async def execute(self, path: str, **kwargs: Any) -> str:
        try:
            dir_path = _resolve_path(path, self._workspace, self._allowed_dir, self._extra_allowed_dirs)
            
            if not dir_path.exists():
                return f"Error: Directory not found: {path}"
            if not dir_path.is_dir():
                return f"Error: Not a directory: {path}"

            items = []
            for item in sorted(dir_path.iterdir()):
                prefix = "📁 " if item.is_dir() else "📄 "
                # Sanitize item name
                name = item.name.replace('\n', ' ').replace('\r', '')
                items.append(f"{prefix}{name}")

            if not items:
                return f"Directory {path} is empty"

            return "\n".join(items)
        except PermissionError as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Error listing directory: {str(e)}"


class FileInfoTool(Tool):
    """Tool to get file information."""

    def __init__(self, workspace: Path | None = None, allowed_dir: Path | None = None, extra_allowed_dirs: list[Path] | None = None):
        self._workspace = workspace
        self._allowed_dir = allowed_dir
        self._extra_allowed_dirs = extra_allowed_dirs
        self._policy = FileSystemPolicy(allowed_dir=allowed_dir)

    @property
    def name(self) -> str:
        return "file_info"

    @property
    def description(self) -> str:
        return "Get information about a file or directory."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "The file or directory path"}},
            "required": ["path"],
        }

    async def execute(self, path: str, **kwargs: Any) -> str:
        try:
            file_path = _resolve_path(path, self._workspace, self._allowed_dir, self._extra_allowed_dirs)
            
            if not file_path.exists():
                return f"Error: Path not found: {path}"
            
            info = {
                "path": str(file_path),
                "exists": True,
                "is_file": file_path.is_file(),
                "is_dir": file_path.is_dir(),
                "is_symlink": file_path.is_symlink(),
            }
            
            if file_path.is_file():
                stat = file_path.stat()
                info["size"] = stat.st_size
                info["modified"] = stat.st_mtime
                info["extension"] = file_path.suffix
                
                # Validate extension
                try:
                    _validate_extension(file_path, self._policy)
                    info["extension_allowed"] = True
                except PermissionError:
                    info["extension_allowed"] = False
            
            return "\n".join(f"{k}: {v}" for k, v in info.items())
        except PermissionError as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Error getting file info: {str(e)}"

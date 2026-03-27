"""Utility functions for Crabclaw."""

import re
from datetime import datetime
from pathlib import Path


def ensure_dir(path: Path) -> Path:
    """Ensure directory exists, return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_data_path() -> Path:
    """~/.crabclaw data directory."""
    return ensure_dir(Path.home() / ".crabclaw")


def get_workspace_path(workspace: str | None = None) -> Path:
    """Resolve and ensure workspace path. Defaults to config directory / workspace."""
    from crabclaw.config.secure_loader import get_data_dir
    path = Path(workspace).expanduser() if workspace else get_data_dir() / "workspace"
    return ensure_dir(path)


def timestamp() -> str:
    """Current ISO timestamp."""
    return datetime.now().isoformat()


def generate_agent_id(country_code: str = "CHN") -> str:
    """Generate a globally unique Agent ID: AGT + YYYYMMDDHHMMSSsss + ISO-3166-1 (3 letters) + 4 random digits."""
    import random
    now = datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]
    rand = random.randint(1000, 9999)
    return f"AGT{now}{country_code[:3].upper()}{rand}"


_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*]')

def safe_filename(name: str) -> str:
    """Replace unsafe path characters with underscores."""
    return _UNSAFE_CHARS.sub("_", name).strip()


def split_message(text: str, max_length: int) -> list[str]:
    """Split a long message into chunks that fit within max_length.
    
    This function tries to split at word boundaries to preserve readability.
    
    Args:
        text: The message text to split.
        max_length: Maximum length for each chunk.
        
    Returns:
        List of message chunks, each <= max_length.
    """
    if len(text) <= max_length:
        return [text]
    
    chunks = []
    current_chunk = ""
    
    # Split by newlines first to preserve paragraph structure
    paragraphs = text.split('\n')
    
    for paragraph in paragraphs:
        # If adding this paragraph would exceed max_length,
        # start a new chunk
        if current_chunk and len(current_chunk) + len(paragraph) + 1 > max_length:
            chunks.append(current_chunk)
            current_chunk = ""
        
        # If the paragraph itself is too long, split it
        if len(paragraph) > max_length:
            # Save current chunk if it exists
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = ""
            
            # Split long paragraph by words
            words = paragraph.split(' ')
            for word in words:
                if len(current_chunk) + len(word) + 1 > max_length:
                    chunks.append(current_chunk)
                    current_chunk = word
                else:
                    if current_chunk:
                        current_chunk += ' ' + word
                    else:
                        current_chunk = word
        else:
            # Add paragraph to current chunk
            if current_chunk:
                current_chunk += '\n' + paragraph
            else:
                current_chunk = paragraph
    
    # Add the last chunk if it exists
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks


def sync_workspace_templates(workspace: Path, silent: bool = False) -> list[str]:
    """Sync bundled templates to workspace. Only creates missing files."""
    from importlib.resources import files as pkg_files
    try:
        tpl = pkg_files("crabclaw") / "templates"
    except Exception:
        return []
    if not tpl.is_dir():
        return []

    added: list[str] = []

    def _write(src, dest: Path):
        if dest.exists():
            return
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(src.read_text(encoding="utf-8") if src else "", encoding="utf-8")
        added.append(str(dest.relative_to(workspace)))

    for item in tpl.rglob("*.md"):
        rel = item.relative_to(tpl)
        parts = rel.parts
        if not parts:
            continue
        section = parts[0]
        if section == "prompts":
            _write(item, workspace / "prompts" / rel.name)
            continue
        if section == "memory":
            if rel.name == "MEMORY.md":
                _write(item, workspace / "memory" / "MEMORY.md")
            continue
        if section in {"nature", "social"}:
            _write(item, workspace / section / rel.name)
            continue
        _write(item, workspace / rel.name)

    _write(None, workspace / "memory" / "HISTORY.md")
    
    # Ensure all global workspace scaffold directories exist
    global_dirs = [
        "skills",
        "cron",
        "history",
        "memory",
        "sessions",
        "identities",
        "portfolios",
        "prompts",
        "nature",
        "social",
        "tools"
    ]
    for d in global_dirs:
        (workspace / d).mkdir(parents=True, exist_ok=True)

    if added and not silent:
        from rich.console import Console
        for name in added:
            Console().print(f"  [dim]Created {name}[/dim]")
    return added

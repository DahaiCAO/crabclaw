"""Path utilities for Crabclaw."""

from pathlib import Path

from crabclaw.config.secure_loader import get_data_dir


def get_media_dir(channel_name: str) -> Path:
    """Get the media directory for a specific channel.
    
    Args:
        channel_name: Name of the channel (e.g., 'feishu', 'telegram', etc.)
        
    Returns:
        Path to the channel's media directory.
    """
    media_dir = get_data_dir() / "media" / channel_name
    media_dir.mkdir(parents=True, exist_ok=True)
    return media_dir


def get_runtime_subdir(channel_name: str) -> Path:
    """Get the runtime subdirectory for a specific channel.
    
    Args:
        channel_name: Name of the channel (e.g., 'mochat', etc.)
        
    Returns:
        Path to the channel's runtime subdirectory.
    """
    runtime_dir = get_data_dir() / "runtime" / channel_name
    runtime_dir.mkdir(parents=True, exist_ok=True)
    return runtime_dir

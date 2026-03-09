"""Configuration loading utilities (legacy compatibility - redirects to secure_loader)."""

from pathlib import Path

# Import from secure_loader to maintain backward compatibility
from crabclaw.config.secure_loader import (
    get_config_path,
    get_data_dir,
    load_config,
    save_config,
    _migrate_config,
    validate_config_security,
    sanitize_config_for_display,
)

# Re-export for backward compatibility
__all__ = [
    'get_config_path',
    'get_data_dir', 
    'load_config',
    'save_config',
    '_migrate_config',
    'validate_config_security',
    'sanitize_config_for_display',
]

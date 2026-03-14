"""Configuration loading utilities (legacy compatibility - redirects to secure_loader)."""


# Import from secure_loader to maintain backward compatibility
from crabclaw.config.secure_loader import (
    _migrate_config,
    get_config_path,
    get_data_dir,
    load_config,
    sanitize_config_for_display,
    save_config,
    set_config_path,
    validate_config_security,
)

# Re-export for backward compatibility
__all__ = [
    'get_config_path',
    'get_data_dir',
    'load_config',
    'save_config',
    'set_config_path',
    '_migrate_config',
    'validate_config_security',
    'sanitize_config_for_display',
]

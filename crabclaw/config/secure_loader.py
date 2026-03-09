"""Secure configuration loading utilities with encryption and access control."""

import json
import os
import stat
from pathlib import Path
from typing import Any

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    import base64
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

from crabclaw.config.schema import Config
from loguru import logger


# Sensitive fields that should be encrypted
SENSITIVE_FIELDS = {
    'api_key', 'apiKey', 'token', 'secret', 'password', 'client_secret',
    'app_secret', 'access_token', 'claw_token', 'imap_password', 'smtp_password'
}


def _get_encryption_key() -> bytes | None:
    """Get or create encryption key from environment or key file."""
    # First try environment variable
    env_key = os.environ.get('CRABCLAW_CONFIG_KEY')
    if env_key:
        return base64.urlsafe_b64decode(env_key.encode())
    
    # Try to load from key file
    key_file = Path.home() / '.crabclaw' / '.config_key'
    if key_file.exists():
        try:
            with open(key_file, 'rb') as f:
                return f.read()
        except Exception:
            pass
    
    # Generate new key if cryptography is available
    if CRYPTO_AVAILABLE:
        key = Fernet.generate_key()
        try:
            key_file.parent.mkdir(parents=True, exist_ok=True)
            with open(key_file, 'wb') as f:
                f.write(key)
            # Set restrictive permissions
            os.chmod(key_file, stat.S_IRUSR | stat.S_IWUSR)  # 0o600
            logger.info("Generated new encryption key for config file")
            return key
        except Exception as e:
            logger.warning(f"Failed to save encryption key: {e}")
    
    return None


def _encrypt_sensitive_data(data: dict, key: bytes) -> dict:
    """Encrypt sensitive fields in configuration data."""
    if not CRYPTO_AVAILABLE or not key:
        return data
    
    f = Fernet(key)
    encrypted_data = {}
    
    for k, v in data.items():
        if isinstance(v, dict):
            encrypted_data[k] = _encrypt_sensitive_data(v, key)
        elif isinstance(v, list):
            encrypted_data[k] = [
                _encrypt_sensitive_data(item, key) if isinstance(item, dict) else item
                for item in v
            ]
        elif isinstance(v, str) and any(field in k.lower() for field in SENSITIVE_FIELDS):
            if v and not v.startswith('enc:'):  # Don't double encrypt
                try:
                    encrypted = f.encrypt(v.encode()).decode()
                    encrypted_data[k] = f'enc:{encrypted}'
                except Exception as e:
                    logger.warning(f"Failed to encrypt field {k}: {e}")
                    encrypted_data[k] = v
            else:
                encrypted_data[k] = v
        else:
            encrypted_data[k] = v
    
    return encrypted_data


def _decrypt_sensitive_data(data: dict, key: bytes) -> dict:
    """Decrypt sensitive fields in configuration data."""
    if not CRYPTO_AVAILABLE or not key:
        return data
    
    f = Fernet(key)
    decrypted_data = {}
    
    for k, v in data.items():
        if isinstance(v, dict):
            decrypted_data[k] = _decrypt_sensitive_data(v, key)
        elif isinstance(v, list):
            decrypted_data[k] = [
                _decrypt_sensitive_data(item, key) if isinstance(item, dict) else item
                for item in v
            ]
        elif isinstance(v, str) and v.startswith('enc:'):
            try:
                encrypted_value = v[4:]  # Remove 'enc:' prefix
                decrypted = f.decrypt(encrypted_value.encode()).decode()
                decrypted_data[k] = decrypted
            except Exception as e:
                logger.warning(f"Failed to decrypt field {k}: {e}")
                decrypted_data[k] = v
        else:
            decrypted_data[k] = v
    
    return decrypted_data


def _set_secure_permissions(path: Path) -> None:
    """Set secure file permissions (owner read/write only)."""
    try:
        if os.name == 'posix':  # Unix-like systems
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)  # 0o600
        elif os.name == 'nt':  # Windows
            import ctypes
            from ctypes import wintypes
            
            # Windows security settings
            SECURITY_DESCRIPTOR_REVISION = 1
            DACL_SECURITY_INFORMATION = 0x00000004
            
            # Get current user SID
            user_sid = ctypes.windll.advapi32.GetTokenInformation(
                ctypes.windll.kernel32.GetCurrentProcess(),
                1,  # TokenUser
                None,
                0,
                ctypes.byref(wintypes.DWORD())
            )
    except Exception as e:
        logger.warning(f"Failed to set secure permissions on {path}: {e}")


def get_config_path() -> Path:
    """Get the default configuration file path."""
    return Path.home() / '.crabclaw' / 'config.json'


def get_data_dir() -> Path:
    """Get the crabclaw data directory."""
    from crabclaw.utils.helpers import get_data_path
    return get_data_path()


def load_config(config_path: Path | None = None) -> Config:
    """
    Load configuration from file or create default.
    
    Args:
        config_path: Optional path to config file. Uses default if not provided.
        
    Returns:
        Loaded configuration object.
    """
    path = config_path or get_config_path()
    
    if path.exists():
        try:
            with open(path, encoding='utf-8') as f:
                data = json.load(f)
            
            # Decrypt sensitive fields
            key = _get_encryption_key()
            if key and CRYPTO_AVAILABLE:
                data = _decrypt_sensitive_data(data, key)
            
            data = _migrate_config(data)
            return Config.model_validate(data)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to load config from {path}: {e}")
            logger.warning("Using default configuration.")
    
    return Config()


def save_config(config: Config, config_path: Path | None = None) -> None:
    """
    Save configuration to file with encryption and secure permissions.
    
    Args:
        config: Configuration to save.
        config_path: Optional path to save to. Uses default if not provided.
    """
    path = config_path or get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    
    data = config.model_dump(by_alias=True)
    
    # Encrypt sensitive fields
    key = _get_encryption_key()
    if key and CRYPTO_AVAILABLE:
        data = _encrypt_sensitive_data(data, key)
    elif not CRYPTO_AVAILABLE:
        logger.warning("cryptography library not available. Config will be saved unencrypted.")
        logger.warning("Install with: pip install cryptography")
    
    # Write to temporary file first, then move (atomic operation)
    temp_path = path.with_suffix('.tmp')
    try:
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        # Set secure permissions before moving
        _set_secure_permissions(temp_path)
        
        # Atomic move
        temp_path.replace(path)
        
        logger.info(f"Configuration saved securely to {path}")
    except Exception as e:
        logger.error(f"Failed to save config: {e}")
        if temp_path.exists():
            temp_path.unlink()
        raise


def _migrate_config(data: dict) -> dict:
    """Migrate old config formats to current."""
    # Move tools.exec.restrictToWorkspace → tools.restrictToWorkspace
    tools = data.get('tools', {})
    exec_cfg = tools.get('exec', {})
    if 'restrictToWorkspace' in exec_cfg and 'restrictToWorkspace' not in tools:
        tools['restrictToWorkspace'] = exec_cfg.pop('restrictToWorkspace')
    return data


def validate_config_security(config: Config) -> list[str]:
    """
    Validate configuration for security issues.
    
    Returns:
        List of security warnings.
    """
    warnings = []
    
    # Check for empty allowFrom lists
    channels_config = config.channels
    for channel_name in ['telegram', 'whatsapp', 'discord', 'feishu', 'dingtalk', 'slack', 'qq', 'matrix']:
        channel_config = getattr(channels_config, channel_name, None)
        if channel_config and channel_config.enabled:
            allow_from = getattr(channel_config, 'allow_from', None)
            if allow_from == []:
                warnings.append(
                    f"Security Warning: {channel_name} channel has empty allowFrom list. "
                    f"This denies all access. Use ['*'] to allow everyone, or add specific user IDs."
                )
            elif allow_from == ['*']:
                warnings.append(
                    f"Security Warning: {channel_name} channel allows access from everyone (allowFrom: ['*']). "
                    f"Consider restricting to specific user IDs for better security."
                )
    
    # Check for plaintext sensitive data
    providers = config.providers
    for provider_name in dir(providers):
        if not provider_name.startswith('_'):
            provider_config = getattr(providers, provider_name, None)
            if provider_config and hasattr(provider_config, 'api_key'):
                api_key = provider_config.api_key
                if api_key and len(api_key) > 10:
                    # Check if key looks like a real API key (not a placeholder)
                    if not api_key.startswith(('sk-', 'pk-', 'enc:')):
                        warnings.append(
                            f"Security Warning: {provider_name} provider API key may be stored in plaintext. "
                            f"Consider using environment variables or enabling config encryption."
                        )
    
    # Check for insecure tools configuration
    tools_config = config.tools
    if not tools_config.restrict_to_workspace:
        warnings.append(
            "Security Warning: tools.restrictToWorkspace is disabled. "
            "File operations can access files outside the workspace directory."
        )
    
    return warnings


def sanitize_config_for_display(config: Config) -> dict:
    """
    Create a sanitized version of config for display/logging (masks sensitive data).
    
    Returns:
        Sanitized configuration dictionary.
    """
    data = config.model_dump(by_alias=True)
    
    def _sanitize_recursive(obj: Any) -> Any:
        if isinstance(obj, dict):
            result = {}
            for k, v in obj.items():
                if any(field in k.lower() for field in SENSITIVE_FIELDS):
                    if isinstance(v, str) and v:
                        # Mask all but first 4 and last 4 characters
                        if len(v) > 8:
                            result[k] = v[:4] + '*' * (len(v) - 8) + v[-4:]
                        else:
                            result[k] = '*' * len(v)
                    else:
                        result[k] = v
                else:
                    result[k] = _sanitize_recursive(v)
            return result
        elif isinstance(obj, list):
            return [_sanitize_recursive(item) for item in obj]
        else:
            return obj
    
    return _sanitize_recursive(data)
